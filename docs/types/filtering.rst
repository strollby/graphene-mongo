Filtering
=========

graphene-mongo generates filter arguments automatically from the ``filter_fields``
Meta option. These arguments can be passed directly in GraphQL queries.

Declaring filter fields
-----------------------

.. code:: python

    class ArticleType(MongoengineObjectType):
        class Meta:
            model = Article
            interfaces = (Node,)
            filter_fields = {
                "title": ["exact", "icontains", "istartswith"],
                "published": ["exact"],
                "view_count": ["gte", "lte"],
            }

This generates query arguments like ``title``, ``titleIcontains``, ``titleIstartswith``,
``published``, ``viewCountGte``, ``viewCountLte``.

Using filters in a query
-------------------------

.. code:: graphql

    query {
        articles(titleIcontains: "graphql", published: true) {
            edges {
                node { title viewCount }
            }
        }
    }

Supported operators
-------------------

``exact``
    Exact match (``==``).

``iexact``
    Case-insensitive exact match.

``contains``
    Substring match (case-sensitive).

``icontains``
    Substring match (case-insensitive).

``startswith``
    Prefix match (case-sensitive).

``istartswith``
    Prefix match (case-insensitive).

``in``
    Value in a list.

``nin``
    Value not in a list.

``lt``
    Less than.

``lte``
    Less than or equal.

``gt``
    Greater than.

``gte``
    Greater than or equal.

``ne``
    Not equal.

Excluding fields from filters
-------------------------------

Use ``non_filter_fields`` to prevent auto-generation of filter arguments for
specific fields:

.. code:: python

    class UserType(MongoengineObjectType):
        class Meta:
            model = User
            interfaces = (Node,)
            non_filter_fields = ("password_hash", "internal_score")

Custom get_queryset
-------------------

For more complex filtering (access control, multi-field logic, etc.) supply a
``get_queryset`` callback:

.. code:: python

    def active_only(model, info, **args):
        return model.objects(active=True)

    users = MongoengineConnectionField(UserType, get_queryset=active_only)

The callback receives the model class, the GraphQL ``info`` object, and all
query arguments. Return a ``QuerySet`` (filters preserved) or a plain ``dict``
(used as filter kwargs). ``select_related`` is applied on top automatically.