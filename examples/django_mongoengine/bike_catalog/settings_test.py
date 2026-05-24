from .settings import *  # noqa: F403, F405

mongoengine.connect("graphene-mongo-test", host="mongomock://localhost", alias="default")  # noqa: F405
