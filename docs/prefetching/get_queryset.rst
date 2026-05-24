Custom get_queryset
===================

You can supply a ``get_queryset`` callback on a connection field to apply custom
filters. ``select_related`` is applied on top of whatever queryset you return:

.. code:: python

    def get_queryset(model, info, **args):
        return model.objects(published=True)  # filters only — select_related added automatically

    articles = MongoengineConnectionField(ArticleNode, get_queryset=get_queryset)

If you return a ``QuerySet`` or ``AsyncQuerySet``, ``select_related`` is applied
automatically — your filters are preserved and the referenced fields the client
asked for are pre-fetched on top, all in one aggregation. If you return a dict,
it is used as filter kwargs.
