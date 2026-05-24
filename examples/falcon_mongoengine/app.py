import mongoengine
import falcon.asgi

from api import GraphQLResource
from telemetry import setup_telemetry


class MongoLifespan:
    async def process_startup(self, scope, event):
        mongoengine.connect("bookmarks_db")
        await mongoengine.async_connect("bookmarks_db")
        setup_telemetry()

    async def process_shutdown(self, scope, event):
        mongoengine.disconnect()


app = falcon.asgi.App(middleware=[MongoLifespan()])
app.add_route("/graphql", GraphQLResource())