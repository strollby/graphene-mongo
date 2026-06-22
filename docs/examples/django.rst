Django
======

Full source: ``examples/django_mongoengine``

Bike shop domain: ``Bike`` and ``Shop`` documents.

.. code:: bash

    cd examples/django_mongoengine
    pip install -e ".[dev]"
    python manage.py migrate
    python manage.py runserver

Open the playground at `http://localhost:8000/graphql <http://localhost:8000/graphql>`_.

Sample queries:

.. code:: graphql

    query {
        bikes {
            edges {
                node { id name year brand speed }
            }
        }
    }

    mutation {
        createBike(name: "Trail Blazer", year: 2024, brand: "Trek", speed: 21) {
            bike { id name year brand }
        }
    }

Running tests:

.. code:: bash

    cd examples/django_mongoengine
    pytest -v
