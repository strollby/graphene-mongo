# Test Suite

**246 tests · 100% pass · sync and async mirrored**

---

## Running the tests

```bash
# All tests
uv run --group test pytest tests/ -q

# One file
uv run --group test pytest tests/synchronous/test_relay_query.py -v

# One test by name
uv run --group test pytest -k "test_enum_field_query" -v
```

---

## Layout

```
tests/
├── conftest.py              # shared fixtures and DB setup (module-scoped)
├── models.py                # all MongoEngine models used across every test
├── mongo_capture.py         # pymongo command listener — captures projections for assertion
├── types.py                 # plain (non-relay) graphene types shared by test_query tests
│
├── synchronous/
│   ├── nodes.py             # relay MongoengineObjectType nodes (interfaces = (Node,))
│   ├── utils.py             # execute_count() — runs schema.execute with query_counter
│   ├── test_converter.py    # field-type conversion: MongoEngine field → graphene type
│   ├── test_types.py        # schema registration: only_fields, exclude_fields, order_by
│   ├── test_fields.py       # filter/advance/required arg generation on connection fields
│   ├── test_utils.py        # get_model_fields, get_query_fields, get_select_related_paths
│   ├── test_query.py        # plain graphene.List queries (no relay, no connection field)
│   ├── test_relay_query.py  # MongoengineConnectionField — the main relay query tests
│   ├── test_relay_query_deep.py  # 10-level reference chain stress tests
│   ├── test_mutation.py     # relay mutations
│   └── test_inputs.py       # MongoengineInputType
│
└── asynchronous/
    ├── nodes.py             # relay AsyncMongoengineObjectType nodes
    ├── types.py             # non-relay async types (used by async test_query)
    ├── utils.py             # execute_count() — async variant using async_query_counter
    └── test_*.py            # mirrors every synchronous/ file above
```

The async suite is a deliberate line-for-line mirror of the sync suite. Every behaviour proven in sync is re-proven in
async to catch executor-specific regressions.

---

## Shared infrastructure

### `conftest.py`

One `fixtures` fixture (module-scoped) seeds all collections before each test module runs. Collections are dropped and
re-created at the start of the fixture so each module starts clean. The fixture covers:

- `Publisher`, `Editor`, `Article`, `Reporter`, `Player` — core document graph with references, embedded docs, GridFS,
  and generic references
- `Parent`, `Child`, `ParentWithRelationship`, `ChildRegisteredBefore/After` — inheritance and forward-reference
  registration
- `CellTower` — geo polygon fields
- `ProfessorVector` + `ProfessorMetadata` — embedded document with vector field
- `Bench`, `Exam`, `SchoolClass` — enum fields (`ListField(EnumField(GradeEnum))`) and generic embedded/reference fields
- `DeepL1` … `DeepL10` — 10-level reference chain for select_related stress tests
- `Event` — `ZonedDateTimeField` (two events in different IANA timezones)

### `mongo_capture.py`

A pymongo `CommandListener` registered at import time. Used in projection tests to assert that MongoDB actually fetches
only the fields the GraphQL query asked for — not all fields on the document.

```python
with captured_commands() as cap:  # or: async with captured_commands() as cap:
    schema.execute(query)

assert "fname" in cap.projected_fields()  # field was fetched
assert "avatar" not in cap.projected_fields()  # field was NOT fetched
assert cap.command_count == 1  # exactly one round-trip
```

---

## What each file covers

### `test_converter.py` (22 shared + 15 sync + 15 async = 52 tests)

Every MongoEngine field type → graphene type conversion. One test per field type. Covers scalar, numeric, date/time,
UUID, URL/email, ObjectId, list, embedded, reference, generic reference/embedded, geo (Point, Polygon, MultiPolygon),
file (GridFS), sequence, enum, and `ZonedDateTimeField`.

**Known gaps documented:** `SortedListField`, `BinaryField`, `TimeField`, `JSONField` — not supported by the converter;
attempting to use them will raise `MongoEngineConversionError`.

### `test_types.py` (12 sync + 12 async = 24 tests)

Schema-level registration behaviour:

- `only_fields` / `exclude_fields` restrict which fields appear on the type
- `order_by` meta option sets default ordering
- Forward references (type A references type B defined later) are resolved by `rescan_fields`
- Invalid models and missing models raise at class definition time, not at query time
- Filter args on `ListField(ReferenceField)` produce connection fields
- Inheritance (`ChildRegisteredBefore`, `ChildRegisteredAfter`) registers correctly

### `test_fields.py` (5 sync + 2 async = 7 tests)

Argument generation on `MongoengineConnectionField`:

- `filter_fields` dict produces lookup-style args (`headline__icontains`, `first_name__istartswith`, `first_name__in`)
- Advance args are generated for geo fields (PointField → `point__near`)
- Required fields (`required_fields` meta option) always appear in the MongoDB projection

### `test_utils.py` (13 sync only)

Unit tests for the utility functions used internally by the field resolver:

| Function                     | Tests                                                                                                                                                            |
|------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `get_model_fields`           | no duplicates, excluding fields, base model fields                                                                                                               |
| `is_valid_mongoengine_model` | Document subclass vs non-model                                                                                                                                   |
| `get_query_fields`           | scalar, nested, fragment, alias, list field                                                                                                                      |
| `get_select_related_paths`   | top-level ref, nested ref (`editor__company`), list of refs, unknown fields ignored, self-referential (terminates at query depth), relay `edges→node` unwrapping |

### `test_query.py` (12 sync + 12 async = 24 tests)

Plain `graphene.Field` / `graphene.List` resolvers — **no relay, no connection field**. Verifies that the underlying
model and type graph is correct independently of the connection field machinery. Also covers `ZonedDateTimeField`
querying and filtering:

| Test                                     | What it covers                                                                   |
|------------------------------------------|----------------------------------------------------------------------------------|
| `test_should_query_zoned_datetime`       | Fetches `utc` + `tz` for both events; confirms both subfields are non-null       |
| `test_should_filter_zoned_datetime_by_utc` | Exact UTC equality filter returns only the matching event, with correct `tz`   |
| `test_should_filter_zoned_datetime_range`  | `gte`, `lte` range filters and `in` (list) all translate to the `utc` subfield |

### `test_relay_query.py` (51 sync + 53 async = 104 tests)

The core relay connection field tests. Grouped by behaviour:

#### Filtering and querying

| Test group                            | What it covers                                                                        |
|---------------------------------------|---------------------------------------------------------------------------------------|
| `should_filter*`                      | Scalar filters, list-contains, reference field (global ID), inheritance, filter-by-id |
| `should_query*`                       | Reporters with nested docs, embedded docs, lazy reference, self-referential           |
| `should_get_queryset_returns_*`       | Custom `get_queryset` callback returning a dict (MongoDB match), or a QuerySet        |
| `should_filter_mongoengine_queryset*` | Custom QuerySet passed directly to the field                                          |

#### Pagination

| Test                                                           | What it covers                                                 |
|----------------------------------------------------------------|----------------------------------------------------------------|
| `should_first_n`                                               | `first: N` returns N edges, `hasNextPage=True`                 |
| `should_last_n`                                                | `last: N` returns the last N edges                             |
| `should_after` / `should_before`                               | Cursor-based pagination, no `pageInfo` (1 query)               |
| `should_after_with_page_info` / `should_before_with_page_info` | `pageInfo` requested forces a count query (2 queries)          |
| `should_first_without_page_info`                               | No `pageInfo` → no count query (1 query)                       |
| `empty_result_pageinfo`                                        | Empty result set: `hasNextPage=False`, `hasPreviousPage=False` |

#### N+1 / query count guarantees

| Test                                             | What it proves                                                       |
|--------------------------------------------------|----------------------------------------------------------------------|
| `editors_with_company_no_pagination`             | `editor → company` resolved in 1 aggregate                           |
| `articles_with_editor_and_company_no_pagination` | `article → editor → company` in 1 aggregate                          |
| `articles_with_multiple_refs_no_pagination`      | Multiple top-level references in 1 aggregate                         |
| `players_with_self_referential_no_pagination`    | Self-referential `players` list in 1 aggregate                       |
| `editors_paginated_*`                            | Paginated queries with references: 2 queries max (count + aggregate) |
| `articles_paginated_first_with_editor`           | `first: N` with reference: select_related still works                |

#### MongoDB projection (uses `mongo_capture.py`)

| Test                                          | What it proves                                                                |
|-----------------------------------------------|-------------------------------------------------------------------------------|
| `projection_only_queried_fields`              | Only `firstName` queried → only `fname` projected                             |
| `projection_multiple_fields`                  | Both `firstName` and `lastName` queried → both projected                      |
| `projection_with_reference_field`             | `company` queried → `company` projected, other editor fields not              |
| `projection_list_reference_field`             | `articles` list → `articles` field projected, article fields in sub-aggregate |
| `projection_generic_reference_field`          | Generic reference projected on parent, type-specific fields on child          |
| `projection_list_generic_reference_field`     | List of generic refs projected correctly across multiple types                |
| `only_fields_restricts_mongodb_projection`    | Meta `only_fields` actually limits MongoDB `$project`                         |
| `exclude_fields_restricts_mongodb_projection` | Meta `exclude_fields` actually drops field from `$project`                    |
| `required_fields_always_projected`            | Meta `required_fields` always in `$project` even when not queried             |

#### Enum fields

| Test                | What it proves                                                                 |
|---------------------|--------------------------------------------------------------------------------|
| `enum_field_query`  | `ListField(EnumField(GradeEnum))` serialises to `["A", "B"]` in relay response |
| `enum_field_filter` | Filtering with an enum value (`allowedGrades: A`) returns matching docs only   |

#### Geo filtering

| Test                              | What it proves                                                                      |
|-----------------------------------|-------------------------------------------------------------------------------------|
| `geo_near_filter_arg_exists`      | `filter_fields = {"loc": ["near"]}` generates `loc__near: PointFieldInputType` arg |
| `geo_near_filter_query`           | Live `$near` query returns only documents with a matching location                  |

#### `filter_fields` validation

| Test                                              | What it proves                                                         |
|---------------------------------------------------|------------------------------------------------------------------------|
| `filter_fields_invalid_lookup_schema_arg_exists`  | Unknown lookup name builds schema arg without error                    |
| `filter_fields_invalid_lookup_raises_at_query_time` | Querying with that arg fails at MongoEngine execution time           |

#### Error cases

| Test                                                               | What it proves                                                                     |
|--------------------------------------------------------------------|------------------------------------------------------------------------------------|
| `connection_field_resolver_returns_document_raises`                | Returning a single Document from a resolver raises `TypeError` with useful message |
| `connection_field_get_queryset_rejects_sync_queryset` (async only) | `get_queryset` callback returning a sync `QuerySet` raises `TypeError`             |

### `test_relay_query_deep.py` (6 sync + 6 async = 12 tests)

10-level reference chain stress tests. The model graph:

```
L1 → L2 → L3 → L4 → L5 → L6 → L7 → L8 → L9 → L10
      ↑              ↕              ↑
  L1.children   L3.extraRefs   L6.genericItem → L7
  (ListField)   L5.siblings    L8.extras → [L10]
                (self-ref)
```

| Test                    | What it covers                                                             |
|-------------------------|----------------------------------------------------------------------------|
| `data_correctness`      | All 10 levels resolve to the correct document names                        |
| `single_query`          | The entire graph is resolved in **exactly 1 MongoDB query** — no N+1       |
| `list_of_references`    | `ListField(ReferenceField)` at L1 and L3 resolve all items in 1 query      |
| `generic_references`    | `GenericReferenceField` at L3 and L6 resolve to the correct concrete types |
| `self_referential_list` | `ListField(ReferenceField('self'))` at L5 resolves correctly               |
| `list_at_depth_8`       | `ListField(ReferenceField)` at depth 8 resolves all items in 1 query       |

### `test_mutation.py` (2 sync + 2 async = 4 tests)

Relay mutations via `MongoengineCreateMutation` / `MongoengineUpdateMutation`. Covers basic create and update for
`Reporter`.

### `test_inputs.py` (3 sync + 3 async = 6 tests)

`MongoengineInputType` for mutation inputs. Covers `non_required_fields` making required fields optional, and nested
`EmbeddedDocumentField` inputs (`ProfessorMetadataInput` nested inside `ProfessorVectorInput`).

---

## `ZonedDateTimeField` support

`ZonedDateTimeField` (mongoengine v0.30.0-alpha.5+) stores a datetime as `{"utc": datetime, "tz": "IANA/Zone"}`.
graphene-mongo exposes it as `ZonedDateTimeType` with two subfields:

```graphql
startTime {
    utc   # DateTime — UTC-normalised instant, use for sorting and comparisons
    tz    # String  — IANA timezone name (e.g. "Asia/Kolkata", "America/New_York")
}
```

**Filtering** behaves identically to a plain `DateTime` field. Any MongoEngine operator declared in `filter_fields`
is transparently rewritten to compare against the stored `utc` subfield:

```python
class EventNode(MongoengineObjectType):
    class Meta:
        model = Event
        filter_fields = {"start_time": ["gte", "lte", "gt", "lt", "in"]}
```

```graphql
# camelCase note: start_time__gte → startTime_Gte (double-underscore separator preserved)
{ events(startTime_Gte: "2024-07-01T00:00:00+00:00") { edges { node { name } } } }
```

List operators (`in`, `nin`, `all`) accept a list of `DateTime` values — each element is individually
normalised to UTC before the query is sent.

---

## Coverage summary

| Area                                        | Status      | Notes                                                                                   |
|---------------------------------------------|-------------|-----------------------------------------------------------------------------------------|
| Field type conversion (all supported types) | Covered     | See `test_converter.py`                                                                 |
| Schema registration (only/exclude/order_by) | Covered     | See `test_types.py`                                                                     |
| Filter arg generation                       | Covered     | See `test_fields.py`                                                                    |
| Internal utility functions                  | Covered     | See `test_utils.py`                                                                     |
| Plain resolvers (no relay)                  | Covered     | See `test_query.py`                                                                     |
| Relay connection field — filtering          | Covered     | See `test_relay_query.py`                                                               |
| Relay connection field — pagination         | Covered     | Cursor, first, last, empty set                                                          |
| N+1 prevention (select_related)             | Covered     | Query count asserted ≤ 2                                                                |
| MongoDB projection accuracy                 | Covered     | Wire-level via `mongo_capture.py`                                                       |
| Enum fields (query + filter)                | Covered     | `GradeEnum` via `SchoolClass`                                                           |
| Deep nested references (10 levels)          | Covered     | See `test_relay_query_deep.py`                                                          |
| Self-referential references                 | Covered     | `Player.players`, `DeepL5.siblings`                                                     |
| Generic references                          | Covered     | `Reporter.generic_reference`, L3/L6 in deep tests                                       |
| Async execution (all of the above)          | Covered     | Full mirror under `tests/asynchronous/`                                                 |
| Mutations                                   | Minimal     | Create + update only                                                                    |
| Input types                                 | Covered     | `non_required_fields` + nested `EmbeddedDocumentField` input (`test_inputs.py`)         |
| Nested input objects                        | Covered     | `ProfessorMetadataInput` nested in `ProfessorVectorInput` (`test_inputs.py`)            |
| Geo field filtering (`__near`)              | Covered     | Arg existence + live `$near` query with 2dsphere index (`test_relay_query.py`)          |
| `filter_fields` validation errors           | Covered     | Invalid lookup: schema builds fine, query fails at execution (`test_relay_query.py`)    |
| `ZonedDateTimeField` (query + filter)       | Covered     | Read `utc`/`tz`, exact equality, range (`gte`/`lte`/`gt`/`lt`), list (`in`) operators  |