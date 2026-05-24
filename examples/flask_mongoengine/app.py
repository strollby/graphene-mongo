from database import init_db
from flask import Flask, jsonify, request
from schema import schema
from telemetry import setup_telemetry

app = Flask(__name__)
setup_telemetry(app)


@app.post("/graphql")
async def graphql_view():
    body = request.get_json()
    result = await schema.execute_async(
        body["query"],
        variable_values=body.get("variables"),
        operation_name=body.get("operationName"),
    )
    errors = [{"message": str(e)} for e in result.errors] if result.errors else None
    return jsonify({"data": result.data, "errors": errors})


if __name__ == "__main__":
    init_db()
    app.run()