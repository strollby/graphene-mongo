Mongoengine + Flask Tutorial
============================

This tutorial walks through building a GraphQL API with graphene-mongo and Flask.
The full source is in
`examples/flask_mongoengine <https://github.com/graphql-python/graphene-mongo/tree/master/examples/flask_mongoengine>`__.

For an async example using FastAPI see :doc:`async_tutorial`.

Setup
-----

.. code:: bash

    mkdir flask_graphene_mongo && cd flask_graphene_mongo
    uv init
    uv add Flask graphene-mongo mongoengine mongomock

Defining Models
---------------

.. code:: python

    # models.py
    from datetime import datetime
    import mongoengine

    class Department(mongoengine.Document):
        meta = {"collection": "department"}
        name = mongoengine.StringField(required=True)

    class Role(mongoengine.Document):
        meta = {"collection": "role"}
        name = mongoengine.StringField(required=True)

    class Task(mongoengine.EmbeddedDocument):
        name = mongoengine.StringField()
        deadline = mongoengine.DateTimeField()

    class Employee(mongoengine.Document):
        meta = {"collection": "employee"}
        name = mongoengine.StringField(required=True)
        hired_on = mongoengine.DateTimeField(default=datetime.now)
        department = mongoengine.ReferenceField(Department)
        roles = mongoengine.ListField(mongoengine.ReferenceField(Role))
        leader = mongoengine.ReferenceField("self")
        tasks = mongoengine.ListField(mongoengine.EmbeddedDocumentField(Task))

Schema
------

``MongoengineObjectType`` converts a Mongoengine Document into a Graphene type.
Adding the ``Node`` interface enables Relay-compatible pagination and global IDs.

.. code:: python

    # schema.py
    import graphene
    from graphene.relay import Node
    from graphene_mongo import MongoengineConnectionField, MongoengineObjectType
    from models import Department as DepartmentModel
    from models import Employee as EmployeeModel
    from models import Role as RoleModel
    from models import Task as TaskModel

    class Department(MongoengineObjectType):
        class Meta:
            model = DepartmentModel
            interfaces = (Node,)

    class Role(MongoengineObjectType):
        class Meta:
            model = RoleModel
            interfaces = (Node,)
            filter_fields = {"name": ["exact", "icontains", "istartswith"]}

    class Task(MongoengineObjectType):
        class Meta:
            model = TaskModel
            interfaces = (Node,)

    class Employee(MongoengineObjectType):
        class Meta:
            model = EmployeeModel
            interfaces = (Node,)
            filter_fields = {"name": ["exact", "icontains", "istartswith"]}

    class Query(graphene.ObjectType):
        node = Node.Field()
        all_employees = MongoengineConnectionField(Employee)
        all_roles = MongoengineConnectionField(Role)

    schema = graphene.Schema(query=Query, types=[Department, Employee, Role, Task])

Filtering and Pagination
~~~~~~~~~~~~~~~~~~~~~~~~

``filter_fields`` enables field-level filtering directly in the query:

.. code:: graphql

    # filter by name
    { allEmployees(name: "Peter") { edges { node { name } } } }

    # pagination
    { allEmployees(first: 5) { edges { node { name } } } }

    # cursor-based pagination
    { allEmployees(first: 5, after: "cursor==") { edges { node { name } } pageInfo { hasNextPage endCursor } } }

Mutations
---------

.. code:: python

    # mutations.py
    import graphene
    from models import Employee, Department, Role

    class CreateEmployee(graphene.Mutation):
        class Arguments:
            name = graphene.String(required=True)
            department_id = graphene.ID()

        employee = graphene.Field(lambda: EmployeeType)

        def mutate(self, info, name, department_id=None):
            from graphql_relay import from_global_id
            dept = None
            if department_id:
                dept = Department.objects.get(pk=from_global_id(department_id)[1])
            emp = Employee(name=name, department=dept).save()
            return CreateEmployee(employee=emp)

    class Mutation(graphene.ObjectType):
        create_employee = CreateEmployee.Field()

    schema = graphene.Schema(query=Query, mutation=Mutation)

Flask App
---------

Flask 3.x supports ``async def`` views natively, so no extra adapter is needed:

.. code:: python

    # app.py
    from database import init_db
    from flask import Flask, jsonify, request
    from schema import schema

    app = Flask(__name__)

    @app.post("/graphql")
    async def graphql_view():
        body = request.get_json()
        result = await schema.execute_async(
            body["query"],
            variable_values=body.get("variables"),
            operation_name=body.get("operationName"),
        )
        errors = [{"message": str(e)} for e in result.errors] if result.errors else None
        return jsonify({"data": result.data, "errors": errors})

    if __name__ == "__main__":
        init_db()
        app.run()

Seed Data
---------

.. code:: python

    # database.py
    import mongoengine
    from models import Department, Employee, Role, Task
    from datetime import datetime

    mongoengine.connect("graphene-mongo-example", host="mongomock://localhost")

    def init_db():
        engineering = Department(name="Engineering").save()
        hr = Department(name="Human Resources").save()

        manager = Role(name="manager").save()
        engineer = Role(name="engineer").save()

        peter = Employee(
            name="Peter", department=engineering, roles=[engineer],
            tasks=[Task(name="Fix bug", deadline=datetime(2025, 1, 1))]
        ).save()
        Employee(name="Roy", department=engineering, roles=[engineer], leader=peter).save()
        Employee(name="Tracy", department=hr, roles=[manager]).save()

Running
-------

.. code:: bash

    uv run python app.py

Then query at ``http://localhost:5000/graphql``:

.. code:: graphql

    {
      allEmployees {
        edges {
          node {
            name
            department { name }
            roles { edges { node { name } } }
          }
        }
      }
    }