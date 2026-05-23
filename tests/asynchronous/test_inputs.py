import graphene
from graphene.relay import Node

from ..models import Article, Editor
from .nodes import ArticleAsyncNode, EditorAsyncNode
from ..types import ArticleInput, EditorInput
from .utils import execute_count


async def test_should_create(fixtures):
    class CreateArticle(graphene.Mutation):
        class Arguments:
            article = ArticleInput(required=True)

        article = graphene.Field(ArticleAsyncNode)

        async def mutate(self, info, article):
            article = Article(**article)
            await article.asave()
            return CreateArticle(article=article)

    class Query(graphene.ObjectType):
        node = Node.Field()

    class Mutation(graphene.ObjectType):
        create_article = CreateArticle.Field()

    query = """
        mutation ArticleCreator {
            createArticle(
                article: {headline: "My Article"}
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
    assert count == 1


async def test_should_update(fixtures):
    class UpdateEditor(graphene.Mutation):
        class Arguments:
            id = graphene.ID(required=True)
            editor = EditorInput(required=True)

        editor = graphene.Field(EditorAsyncNode)

        async def mutate(self, info, id, editor):
            editor_to_update = await Editor.aobjects(id=id).modify(
                new=True, **{f"set__{k}": v for k, v in editor.items() if v}
            )
            return UpdateEditor(editor=editor_to_update)

    class Query(graphene.ObjectType):
        node = Node.Field()

    class Mutation(graphene.ObjectType):
        update_editor = UpdateEditor.Field()

    query = """
        mutation EditorUpdater {
            updateEditor(
                id: "1"
                editor: {
                    lastName: "Lane"
                }
            ) {
                editor {
                    firstName
                    lastName
                }
            }
        }
    """
    expected = {"updateEditor": {"editor": {"firstName": "Penny", "lastName": "Lane"}}}
    schema = graphene.Schema(query=Query, mutation=Mutation)
    result, count = await execute_count(schema, query)
    assert not result.errors
    assert result.data == expected
    assert count == 1