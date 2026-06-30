import mongoengine


class Author(mongoengine.Document):
    name = mongoengine.StringField(required=True, max_length=100)
    birth_year = mongoengine.IntField()
    nationality = mongoengine.StringField()

    meta = {"collection": "authors"}


class Book(mongoengine.Document):
    title = mongoengine.StringField(required=True, max_length=200)
    published_year = mongoengine.IntField()
    genre = mongoengine.StringField()
    author = mongoengine.ReferenceField(Author, reverse_delete_rule=mongoengine.NULLIFY)
    tags = mongoengine.ListField(mongoengine.StringField())

    meta = {"collection": "books"}
