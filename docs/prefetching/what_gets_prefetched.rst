What Gets Pre-fetched
=====================

``ReferenceField`` (e.g. ``article.editor``)
    Pre-fetched via ``$lookup``; nested references are also recursed
    (e.g. ``editor__company`` adds a second ``$lookup`` stage).

``ListField(ReferenceField)`` (e.g. ``employee.roles``)
    The entire list is hydrated in one aggregation; nested references inside
    each list element are also pre-fetched via ``$map``.

``EmbeddedDocumentField`` (e.g. ``professor.metadata``)
    Always co-located in the document — no extra query needed.

``GenericReferenceField`` (e.g. ``feed.item``)
    Union resolved; each registered choice is pre-fetched.
