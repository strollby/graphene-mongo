import graphene
from graphene.relay import Node

from graphene_mongo import AsyncMongoengineConnectionField, AsyncMongoengineObjectType

from models import Author as AuthorModel
from models import Book as BookModel


class AuthorType(AsyncMongoengineObjectType):
    class Meta:
        model = AuthorModel
        interfaces = (Node,)
        filter_fields = {
            "name": ["exact", "icontains", "istartswith"],
            "nationality": ["exact"],
        }


class BookType(AsyncMongoengineObjectType):
    class Meta:
        model = BookModel
        interfaces = (Node,)
        filter_fields = {
            "title": ["exact", "icontains"],
            "genre": ["exact"],
            "published_year": ["exact", "gte", "lte"],
        }


class CreateBookMutation(graphene.Mutation):
    book = graphene.Field(BookType)

    class Arguments:
        title = graphene.String(required=True)
        published_year = graphene.Int()
        genre = graphene.String()
        author_id = graphene.ID()
        tags = graphene.List(graphene.String)

    async def mutate(self, info, title, published_year=None, genre=None, author_id=None, tags=None):
        from graphql_relay import from_global_id
        author = None
        if author_id:
            author = await AuthorModel.aobjects.get(pk=from_global_id(author_id)[1])
        book = BookModel(
            title=title,
            published_year=published_year,
            genre=genre,
            author=author,
            tags=tags or [],
        )
        await book.asave()
        return CreateBookMutation(book=book)


class DeleteBookMutation(graphene.Mutation):
    success = graphene.Boolean()

    class Arguments:
        id = graphene.ID(required=True)

    async def mutate(self, info, id):
        from graphql_relay import from_global_id
        try:
            book = await BookModel.aobjects.get(pk=from_global_id(id)[1])
            await book.adelete()
            return DeleteBookMutation(success=True)
        except BookModel.DoesNotExist:
            return DeleteBookMutation(success=False)


class Mutation(graphene.ObjectType):
    create_book = CreateBookMutation.Field()
    delete_book = DeleteBookMutation.Field()


class Query(graphene.ObjectType):
    node = Node.Field()
    books = AsyncMongoengineConnectionField(BookType)
    authors = AsyncMongoengineConnectionField(AuthorType)


schema = graphene.Schema(query=Query, mutation=Mutation, types=[AuthorType, BookType])