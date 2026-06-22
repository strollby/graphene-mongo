Automatic Pre-fetching
=======================

The central design principle of graphene-mongo is: fetch exactly what the
GraphQL client asked for, in as few MongoDB round-trips as possible.

.. toctree::
   :maxdepth: 1

   how_it_works
   what_gets_prefetched
   utils
   get_queryset
   sync_vs_async
