Mutations
=========

graphene-mongo works with standard Graphene mutations. MongoEngine documents are
created, updated, and deleted using the regular MongoEngine API inside the
``mutate`` (or ``async def mutate``) method.

Sync mutations
--------------

.. code:: python

    import graphene
    from graphql_relay import from_global_id
    from models import Employee, Department

    class CreateEmployee(graphene.Mutation):
        class Arguments:
            name = graphene.String(required=True)
            department_id = graphene.ID()

        employee = graphene.Field(lambda: EmployeeType)

        def mutate(self, info, name, department_id=None):
            dept = None
            if department_id:
                dept = Department.objects.get(pk=from_global_id(department_id)[1])
            emp = Employee(name=name, department=dept).save()
            return CreateEmployee(employee=emp)

    class UpdateEmployee(graphene.Mutation):
        class Arguments:
            id = graphene.ID(required=True)
            name = graphene.String()

        employee = graphene.Field(lambda: EmployeeType)

        def mutate(self, info, id, name=None):
            pk = from_global_id(id)[1]
            emp = Employee.objects.get(pk=pk)
            if name:
                emp.name = name
                emp.save()
            return UpdateEmployee(employee=emp)

    class DeleteEmployee(graphene.Mutation):
        class Arguments:
            id = graphene.ID(required=True)

        ok = graphene.Boolean()

        def mutate(self, info, id):
            pk = from_global_id(id)[1]
            Employee.objects.get(pk=pk).delete()
            return DeleteEmployee(ok=True)

    class Mutation(graphene.ObjectType):
        create_employee = CreateEmployee.Field()
        update_employee = UpdateEmployee.Field()
        delete_employee = DeleteEmployee.Field()

    schema = graphene.Schema(query=Query, mutation=Mutation)

Async mutations
---------------

Replace ``Employee.objects`` with ``Employee.aobjects`` and make ``mutate``
an ``async def``:

.. code:: python

    class CreateBook(graphene.Mutation):
        class Arguments:
            title = graphene.String(required=True)
            genre = graphene.String()

        book = graphene.Field(lambda: BookType)

        async def mutate(self, info, title, genre=None):
            book = Book(title=title, genre=genre)
            await book.asave()
            return CreateBook(book=book)

    class DeleteBook(graphene.Mutation):
        class Arguments:
            id = graphene.ID(required=True)

        ok = graphene.Boolean()

        async def mutate(self, info, id):
            from graphql_relay import from_global_id
            pk = from_global_id(id)[1]
            book = await Book.aobjects.get(pk=pk)
            await book.adelete()
            return DeleteBook(ok=True)

Input types
-----------

For complex mutations, use ``graphene.InputObjectType`` to group arguments:

.. code:: python

    class EmployeeInput(graphene.InputObjectType):
        name = graphene.String(required=True)
        department_id = graphene.ID()

    class CreateEmployee(graphene.Mutation):
        class Arguments:
            input = EmployeeInput(required=True)

        employee = graphene.Field(lambda: EmployeeType)

        def mutate(self, info, input):
            emp = Employee(name=input.name).save()
            return CreateEmployee(employee=emp)

Mutations in GraphQL
---------------------

.. code:: graphql

    mutation {
        createEmployee(name: "Alice", departmentId: "RGVwYXJ0bWVudFR5...") {
            employee { id name department { name } }
        }
    }

    mutation {
        updateEmployee(id: "RW1wbG95ZWVU...", name: "Alicia") {
            employee { id name }
        }
    }

    mutation {
        deleteEmployee(id: "RW1wbG95ZWVU...") {
            ok
        }
    }