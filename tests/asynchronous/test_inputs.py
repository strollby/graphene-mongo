import graphene
from graphene.relay import Node

from ..models import Article, Editor
from .nodes import ArticleAsyncNode, EditorAsyncNode
from ..types import ArticleInput, EditorInput


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
    result = await schema.execute_async(query)
    assert not result.errors
    assert result.data == expected


async def test_should_update(fixtures):
    class UpdateEditor(graphene.Mutation):
        class Arguments:
            id = graphene.ID(required=True)
            editor = EditorInput(required=True)

        editor = graphene.Field(EditorAsyncNode)

        async def mutate(self, info, id, editor):
            editor_to_update = await Editor.aobjects.get(id=id)
            for key, value in editor.items():
                if value:
                    setattr(editor_to_update, key, value)
            await editor_to_update.asave()
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
    result = await schema.execute_async(query)
    assert not result.errors
    assert result.data == expected