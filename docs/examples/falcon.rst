Falcon
======

Full source: ``examples/falcon_mongoengine``

Bookmarks domain: ``Category`` and ``Bookmark`` documents.

.. code:: bash

    cd examples/falcon_mongoengine
    pip install -e ".[dev]"
    uvicorn app:app --reload --port 9000

.. code:: bash

    curl -X POST http://localhost:9000/graphql \
      -H "Content-Type: application/json" \
      -d '{"query": "{ categories { edges { node { name color } } } }"}'

Running tests:

.. code:: bash

    cd examples/falcon_mongoengine
    pytest -v
