from schema import schema


class GraphQLResource:
    async def on_get(self, req, resp):
        query = req.params.get("query")
        result = await schema.execute_async(query)
        errors = [{"message": str(e)} for e in result.errors] if result.errors else None
        resp.media = {"data": result.data, "errors": errors}

    async def on_post(self, req, resp):
        body = await req.get_media()
        result = await schema.execute_async(
            body.get("query"),
            variable_values=body.get("variables"),
            operation_name=body.get("operationName"),
        )
        errors = [{"message": str(e)} for e in result.errors] if result.errors else None
        resp.media = {"data": result.data, "errors": errors}