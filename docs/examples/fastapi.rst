FastAPI
=======

Full source: ``examples/fastapi_mongoengine``

Library domain: ``Author`` and ``Book`` documents.

.. code:: bash

    cd examples/fastapi_mongoengine
    pip install -e ".[dev]"
    uvicorn app:app --reload

Open the playground at `http://localhost:8000/graphql <http://localhost:8000/graphql>`_.

Sample queries:

.. code:: graphql

    query {
        books {
            edges {
                node {
                    title
                    genre
                    publishedYear
                    author { name nationality }
                }
            }
        }
    }

    mutation {
        createBook(title: "Dune", publishedYear: 1965, genre: "Science Fiction") {
            book { id title }
        }
    }

Running tests:

.. code:: bash

    cd examples/fastapi_mongoengine
    pytest -v
