import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mongoengine
import pytest
from httpx import ASGITransport, AsyncClient
from mongomock import gridfs

from app import app
from database import init_db


@pytest.fixture(scope="session", autouse=True)
async def setup():
    gridfs.enable_gridfs_integration()
    mongoengine.connect("library-test", host="mongomock://localhost")
    mongoengine.async_connect("library-test", host="mongomock://localhost")
    init_db()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
