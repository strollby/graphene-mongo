from models import Author, Book


def init_db():
    Author.drop_collection()
    Book.drop_collection()

    orwell = Author(name="George Orwell", birth_year=1903, nationality="British").save()
    huxley = Author(name="Aldous Huxley", birth_year=1894, nationality="British").save()
    kafka = Author(name="Franz Kafka", birth_year=1883, nationality="Czech").save()

    Book(
        title="Nineteen Eighty-Four",
        published_year=1949,
        genre="Dystopian",
        author=orwell,
        tags=["classic", "politics", "dystopia"],
    ).save()
    Book(
        title="Animal Farm",
        published_year=1945,
        genre="Satire",
        author=orwell,
        tags=["classic", "politics"],
    ).save()
    Book(
        title="Brave New World",
        published_year=1932,
        genre="Dystopian",
        author=huxley,
        tags=["classic", "dystopia", "science"],
    ).save()
    Book(
        title="The Trial",
        published_year=1925,
        genre="Philosophical Fiction",
        author=kafka,
        tags=["classic", "absurdism"],
    ).save()
