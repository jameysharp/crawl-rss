import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .. import app
from . import models
from .common import FeedError, UpdateFeedHistory, crawl_feed_history


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

    def update(self, db, feed):
        self.update_count += 1
        self.db = db
        self.feed = feed


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

    feed = models.Feed(url="https://crawl.example/feed", properties={})
    db.add(feed)

    with httpx.Client() as http:
        crawl_feed_history(db, http, [crawler.crawl], "https://crawl.example/feed")

    assert crawler.crawl_count == 1
    assert crawler.update_count == 1
    assert crawler.db is db
    assert crawler.feed is feed


def test_update_feed_history(db):
    pages = [
        models.FeedArchivePage(url=f"https://crawl.example/feed-{idx}")
        for idx in range(3)
    ]
    feed = models.Feed(
        url="https://crawl.example/feed", properties={}, archive_pages=pages[:2]
    )
    update = UpdateFeedHistory(1, pages[2:])
    update(db, feed)
    assert feed.archive_pages[0] is pages[0]
    assert feed.archive_pages[1] is pages[2]
