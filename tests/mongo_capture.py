"""
Pymongo command capture for projection/query assertion in tests.

Register the listener at import time (before mongoengine.connect creates
the MongoClient) so every wire command is captured.
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
    """Context manager — yields itself; after the block, `.events` holds all
    pymongo StartedEvent objects issued inside the block."""

    def __enter__(self):
        self._start = len(_capture._log)
        return self

    def __exit__(self, *_):
        self.events = _capture._log[self._start:]

    def projected_fields(self) -> set[str]:
        """
        Return every field name that was positively projected across all
        `find` and `aggregate` commands captured inside the block.

        - find: reads cmd['projection']
        - aggregate: reads every {'$project': ...} stage in cmd['pipeline']
        """
        fields: set[str] = set()
        for event in self.events:
            cmd = event.command
            if event.command_name == "find":
                fields.update(k for k, v in cmd.get("projection", {}).items() if v)
            elif event.command_name == "aggregate":
                for stage in cmd.get("pipeline", []):
                    if "$project" in stage:
                        fields.update(
                            k for k, v in stage["$project"].items() if v
                        )
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
                        fields.update(
                            k for k, v in stage["$project"].items() if v
                        )
        return fields