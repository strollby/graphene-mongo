from contextlib import asynccontextmanager

import mongoengine
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from database import init_db
from schema import schema

GRAPHQL_PLAYGROUND = """<!DOCTYPE html>
<html>
  <head>
    <title>GraphQL Playground</title>
    <link rel="stylesheet"
      href="https://unpkg.com/graphql-playground-react/build/static/css/index.css" />
  </head>
  <body>
    <div id="root"></div>
    <script src="https://unpkg.com/graphql-playground-react/build/static/js/middleware.js"></script>
    <script>
      window.addEventListener('load', function () {
        GraphQLPlayground.init(document.getElementById('root'), { endpoint: '/graphql' })
      })
    </script>
  </body>
</html>"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongoengine.connect("library_db")
    await mongoengine.async_connect("library_db")
    init_db()
    yield
    mongoengine.disconnect()


app = FastAPI(title="Library GraphQL API", lifespan=lifespan)


@app.get("/graphql", response_class=HTMLResponse)
async def graphql_playground():
    return GRAPHQL_PLAYGROUND


@app.post("/graphql")
async def graphql(request: Request):
    body = await request.json()
    result = await schema.execute_async(
        body["query"],
        variable_values=body.get("variables"),
        operation_name=body.get("operationName"),
    )
    errors = [{"message": str(e)} for e in result.errors] if result.errors else None
    return JSONResponse({"data": result.data, "errors": errors})