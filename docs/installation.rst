Installation
============

.. rubric:: Requirements

- Python 3.9+
- MongoEngine 0.27+
- Graphene 3.x

.. rubric:: Install

.. code:: bash

    pip install graphene-mongo

.. rubric:: Optional Extras

OpenTelemetry tracing support:

.. code:: bash

    pip install "graphene-mongo[telemetry]"

This installs ``opentelemetry-api``. You also need an SDK and exporter at runtime:

.. code:: bash

    pip install opentelemetry-sdk opentelemetry-exporter-otlp \
                opentelemetry-instrumentation-pymongo

.. rubric:: Development Install

.. code:: bash

    git clone https://github.com/graphql-python/graphene-mongo.git
    cd graphene-mongo
    pip install -e ".[dev]"

Run the test suite:

.. code:: bash

    make test