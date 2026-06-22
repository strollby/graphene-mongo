Flask
=====

Full source: ``examples/flask_mongoengine``

HR domain: ``Department``, ``Employee``, ``Role``, and ``Task`` documents.

.. code:: bash

    cd examples/flask_mongoengine
    pip install -e ".[dev]"
    python app.py

Open the playground at `http://localhost:5000/graphql <http://localhost:5000/graphql>`_.

Sample queries:

.. code:: graphql

    query {
        allEmployees {
            edges {
                node {
                    id
                    name
                    department { id name }
                    roles { edges { node { id name } } }
                    tasks { edges { node { name deadline } } }
                }
            }
        }
    }

Running tests:

.. code:: bash

    cd examples/flask_mongoengine
    pytest -v
