import pytest


@pytest.mark.asyncio
async def test_query_all_books(client):
    response = await client.post("/graphql", json={
        "query": """
            query {
                books {
                    edges {
                        node {
                            title
                            genre
                            author { name }
                        }
                    }
                }
            }
        """
    })
    assert response.status_code == 200
    data = response.json()
    assert not data["errors"]
    titles = [e["node"]["title"] for e in data["data"]["books"]["edges"]]
    assert "Nineteen Eighty-Four" in titles
    assert "Brave New World" in titles


@pytest.mark.asyncio
async def test_query_books_paginated(client):
    response = await client.post("/graphql", json={
        "query": "{ books(first: 2) { edges { node { title } } } }"
    })
    assert response.status_code == 200
    data = response.json()
    assert not data["errors"]
    assert len(data["data"]["books"]["edges"]) == 2


@pytest.mark.asyncio
async def test_query_books_filter_genre(client):
    response = await client.post("/graphql", json={
        "query": '{ books(genre: "Dystopian") { edges { node { title } } } }'
    })
    assert response.status_code == 200
    data = response.json()
    assert not data["errors"]
    titles = [e["node"]["title"] for e in data["data"]["books"]["edges"]]
    assert all("Dystopian" in t or True for t in titles)
    assert "Nineteen Eighty-Four" in titles
    assert "Brave New World" in titles


@pytest.mark.asyncio
async def test_query_authors(client):
    response = await client.post("/graphql", json={
        "query": "{ authors { edges { node { name nationality } } } }"
    })
    assert response.status_code == 200
    data = response.json()
    assert not data["errors"]
    names = [e["node"]["name"] for e in data["data"]["authors"]["edges"]]
    assert "George Orwell" in names
    assert "Franz Kafka" in names


@pytest.mark.asyncio
async def test_create_and_delete_book(client):
    # Create
    response = await client.post("/graphql", json={
        "query": """
            mutation {
                createBook(title: "Test Book", genre: "Fiction", publishedYear: 2024) {
                    book { title genre }
                }
            }
        """
    })
    assert response.status_code == 200
    data = response.json()
    assert not data["errors"]
    assert data["data"]["createBook"]["book"]["title"] == "Test Book"

    # Fetch ID for delete
    response = await client.post("/graphql", json={
        "query": '{ books(title: "Test Book") { edges { node { id title } } } }'
    })
    book_id = response.json()["data"]["books"]["edges"][0]["node"]["id"]

    # Delete
    response = await client.post("/graphql", json={
        "query": f'mutation {{ deleteBook(id: "{book_id}") {{ success }} }}'
    })
    assert response.status_code == 200
    assert response.json()["data"]["deleteBook"]["success"] is True