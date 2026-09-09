"""
Pymongo command capture for projection/query assertion in tests.

The listener is registered at import time (before mongoengine.connect creates
the MongoClient) so every wire command is captured.

Isolation model
---------------
Each ``captured_commands`` / ``async_captured_commands`` block snapshots the
log length on enter and slices on exit — so concurrent or sequential blocks
never see each other's events even though they share the global log.

Parallel processes (pytest-xdist) are safe because each worker has its own
Python interpreter and its own listener instance.

Thread safety within a single process: CPython's GIL makes list.append
atomic, so the shared log is safe for concurrent in-process I/O threads
(e.g. Motor callbacks).  The start/end snapshot is taken on the calling
thread and is not affected by other threads appending to the log.
"""

import pymongo.monitoring as _pm


class _CommandCapture(_pm.CommandListener):
    def __init__(self):
        self._log: list = []

    def started(self, event) -> None:
        self._log.append(event)

    def succeeded(self, event) -> None:
        pass

    def failed(self, event) -> None:
        pass


_capture = _CommandCapture()
_pm.register(_capture)


class captured_commands:
    """Sync context manager — captures every pymongo wire command in the block.

    Usage::

        with captured_commands() as cap:
            schema.execute(query)

        assert cap.command_count == 1
        assert "name" in cap.projected_fields()

    Also supports ``async with`` for use inside ``async def`` test functions.
    """

    def __enter__(self):
        self._start = len(_capture._log)
        return self

    def __exit__(self, *_):
        self.events = _capture._log[self._start :]

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, *args):
        return self.__exit__(*args)

    @property
    def command_count(self) -> int:
        """Number of MongoDB commands (find + aggregate) issued in this block."""
        return sum(1 for e in self.events if e.command_name in ("find", "aggregate"))

    def projected_fields(self) -> set[str]:
        """
        Return every field name that was positively projected across all
        ``find`` and ``aggregate`` commands captured inside the block.

        - find: reads cmd['projection']
        - aggregate: reads every ``{'$project': ...}`` stage in cmd['pipeline']
        """
        fields: set[str] = set()
        for event in self.events:
            cmd = event.command
            if event.command_name == "find":
                fields.update(k for k, v in cmd.get("projection", {}).items() if v)
            elif event.command_name == "aggregate":
                for stage in cmd.get("pipeline", []):
                    if "$project" in stage:
                        fields.update(k for k, v in stage["$project"].items() if v)
        return fields

    def projected_fields_for(self, collection: str) -> set[str]:
        """
        Return every positively projected field name for a specific MongoDB collection.

        Useful for asserting that fetched reference/generic-reference documents
        project only the fields requested in the GraphQL query, not all fields.
        """
        fields: set[str] = set()
        for event in self.events:
            cmd = event.command
            if event.command_name == "find" and cmd.get("find") == collection:
                fields.update(k for k, v in cmd.get("projection", {}).items() if v)
            elif event.command_name == "aggregate" and cmd.get("aggregate") == collection:
                for stage in cmd.get("pipeline", []):
                    if "$project" in stage:
                        fields.update(k for k, v in stage["$project"].items() if v)
        return fields
