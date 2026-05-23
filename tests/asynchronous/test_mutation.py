import graphene
from graphene.relay import Node

from ..models import Article, Editor
from .nodes import ArticleAsyncNode, EditorAsyncNode
from .utils import execute_count


async def test_should_create(fixtures):
    class CreateArticle(graphene.Mutation):
        class Arguments:
            headline = graphene.String()

        article = graphene.Field(ArticleAsyncNode)

        async def mutate(self, info, headline):
            article = Article(headline=headline)
            await article.asave()
            return CreateArticle(article=article)

    class Query(graphene.ObjectType):
        node = Node.Field()

    class Mutation(graphene.ObjectType):
        create_article = CreateArticle.Field()

    query = """
        mutation ArticleCreator {
            createArticle(
                headline: "My Article"
            ) {
                article {
                    headline
                }
            }
        }
    """
    expected = {"createArticle": {"article": {"headline": "My Article"}}}
    schema = graphene.Schema(query=Query, mutation=Mutation)
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count >= 1


async def test_should_update(fixtures):
    class UpdateEditor(graphene.Mutation):
        class Arguments:
            id = graphene.ID()
            first_name = graphene.String()

        editor = graphene.Field(EditorAsyncNode)

        async def mutate(self, info, id, first_name):
            editor = await Editor.aobjects.get(id=id)
            editor.first_name = first_name
            await editor.asave()
            return UpdateEditor(editor=editor)

    class Query(graphene.ObjectType):
        node = Node.Field()

    class Mutation(graphene.ObjectType):
        update_editor = UpdateEditor.Field()

    query = """
        mutation EditorUpdater {
            updateEditor(
                id: "1"
                firstName: "Tony"
            ) {
                editor {
                    firstName
                }
            }
        }
    """
    expected = {"updateEditor": {"editor": {"firstName": "Tony"}}}
    schema = graphene.Schema(query=Query, mutation=Mutation)
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count >= 1