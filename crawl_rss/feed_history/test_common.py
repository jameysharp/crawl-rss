import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import select

from .. import app
from . import models
from .common import FeedError, FeedPage, UpdateFeedHistory, crawl_feed_history


@pytest.fixture
def db():
    engine = create_engine("sqlite:///")
    app.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def test_archive_missing_current(mock_atom_feed):
    mock_atom_feed("https://crawl.example/feed-1", archive=True)
    with httpx.Client() as http, pytest.raises(FeedError):
        crawl_feed_history(None, http, (), "https://crawl.example/feed-1")


def test_no_crawler(db, mock_atom_feed):
    mock_atom_feed("https://crawl.example/feed")
    with httpx.Client() as http, pytest.raises(FeedError):
        crawl_feed_history(db, http, (), "https://crawl.example/feed")


class MockCrawler:
    def __init__(self, url):
        self.url = url
        self.crawl_count = 0
        self.update_count = 0

    def crawl(self, base, old_pages):
        self.crawl_count += 1
        assert base.url == self.url
        return self.update

    def update(self, db, feed_id):
        self.update_count += 1
        self.db = db
        self.feed_id = feed_id


def test_new_mock_crawler(db, mock_atom_feed):
    mock_atom_feed("https://crawl.example/feed")
    crawler = MockCrawler("https://crawl.example/feed")

    with httpx.Client() as http:
        crawl_feed_history(db, http, [crawler.crawl], "https://crawl.example/feed")

    assert crawler.crawl_count == 1
    assert crawler.update_count == 1
    assert crawler.db is db


def test_updated_mock_crawler(db, mock_atom_feed):
    mock_atom_feed("https://crawl.example/feed")
    crawler = MockCrawler("https://crawl.example/feed")

    result = db.execute(
        models.Feed.__table__.insert(),
        {"url": "https://crawl.example/feed", "properties": {}},
    )
    feed_id = result.inserted_primary_key[0]

    with httpx.Client() as http:
        crawl_feed_history(db, http, [crawler.crawl], "https://crawl.example/feed")

    assert crawler.crawl_count == 1
    assert crawler.update_count == 1
    assert crawler.db is db
    assert crawler.feed_id is feed_id


def test_update_feed_history(db):
    page_urls = [f"https://crawl.example/feed-{idx}" for idx in range(3)]

    result = db.execute(
        models.Feed.__table__.insert(),
        {"url": "https://crawl.example/feed", "properties": {}},
    )
    feed_id = result.inserted_primary_key[0]

    page = models.FeedArchivePage.__table__
    db.execute(
        page.insert(),
        [
            {"feed_id": feed_id, "order": order, "url": url}
            for order, url in enumerate(page_urls[:2])
        ],
    )

    update = UpdateFeedHistory(1, [FeedPage(url=url) for url in page_urls[2:]])
    update(db, feed_id)

    urls = db.execute(
        select([page.c.url]).where(page.c.feed_id == feed_id).order_by(page.c.order)
    )
    assert list(urls) == [(page_urls[0],), (page_urls[2],)]
