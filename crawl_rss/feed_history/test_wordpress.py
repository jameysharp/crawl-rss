import datetime
import httpx
import pytest

from .common import FeedDocument, FeedEntry, FeedPage
from .wordpress import from_wordpress


def url_for(page):
    url = "https://wp.example/feed/?feed=atom&order=ASC&orderby=modified"
    if page > 1:
        url += f"&paged={page}"
    return url


@pytest.fixture
def mock_wp_feed(httpx_mock, mock_atom_feed):
    def make(pages):
        mock_atom_feed(
            "https://wp.example/feed/",
            headers={"Link": '<https://wp.example/wp-json/>; rel="https://api.w.org/"'},
        )

        for idx, page in enumerate(pages, 1):
            mock_atom_feed(url_for(idx), entries=page)

        httpx_mock.add_response(url=url_for(idx + 1), status_code=404)

    return make


def expected_page(entries):
    result = {}
    for entry in entries:
        guid = f"urn:example:post-{entry}"
        pubdate = datetime.datetime(2020, 1, entry, 0, 0)
        result[guid] = FeedEntry(
            guid=guid,
            link=guid,
            published=pubdate,
            updated=pubdate,
        )
    return result


def test_not_wordpress(mock_atom_feed):
    mock_atom_feed("https://rfc5005.example/feed.xml")

    with httpx.Client() as http:
        update = from_wordpress(
            FeedDocument(http, "https://rfc5005.example/feed.xml"), []
        )

    assert update is None


def test_identify_by_generator(httpx_mock, mock_atom_feed):
    httpx_mock.add_response(
        url="https://wp.example/feed/",
        data='<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0">'
        "<channel>"
        "<generator>https://wordpress.org/?v=5.3.2</generator>"
        "</channel>"
        "</rss>",
    )

    mock_atom_feed(url_for(1), entries=[1])
    httpx_mock.add_response(url=url_for(2), status_code=404)

    with httpx.Client() as http:
        update = from_wordpress(FeedDocument(http, "https://wp.example/feed/"), [])

    assert update is not None
    assert update.keep_existing == 0
    assert len(update.new_pages) == 1

    page = update.new_pages[0]
    assert page.url == url_for(1)
    assert page.entries.keys() == expected_page([1]).keys()


def test_new_feed(mock_wp_feed):
    mock_wp_feed([[1]])

    with httpx.Client() as http:
        update = from_wordpress(FeedDocument(http, "https://wp.example/feed/"), [])

    assert update is not None
    assert update.keep_existing == 0
    assert len(update.new_pages) == 1

    page = update.new_pages[0]
    assert page.url == url_for(1)
    assert page.entries.keys() == expected_page([1]).keys()


def test_new_page(mock_wp_feed):
    mock_wp_feed([[1], [2]])

    with httpx.Client() as http:
        update = from_wordpress(
            FeedDocument(http, "https://wp.example/feed/"),
            [FeedPage(url=url_for(1), entries=expected_page([1]))],
        )

    assert update is not None
    assert update.keep_existing == 1
    assert len(update.new_pages) == 1

    page = update.new_pages[0]
    assert page.url == url_for(2)
    assert page.entries.keys() == expected_page([2]).keys()


def test_dropped_page(mock_wp_feed):
    mock_wp_feed([[1]])

    with httpx.Client() as http:
        update = from_wordpress(
            FeedDocument(http, "https://wp.example/feed/"),
            [
                FeedPage(url=url_for(1), entries=expected_page([1])),
                FeedPage(url=url_for(2), entries=expected_page([2])),
            ],
        )

    assert update is not None
    assert update.keep_existing == 1
    assert len(update.new_pages) == 0


def test_changed_page(mock_wp_feed):
    mock_wp_feed([[1], [3]])

    with httpx.Client() as http:
        update = from_wordpress(
            FeedDocument(http, "https://wp.example/feed/"),
            [
                FeedPage(url=url_for(1), entries=expected_page([1])),
                FeedPage(url=url_for(2), entries=expected_page([2])),
            ],
        )

    assert update is not None
    assert update.keep_existing == 1
    assert len(update.new_pages) == 1

    page = update.new_pages[0]
    assert page.url == url_for(2)
    assert page.entries.keys() == expected_page([3]).keys()


def test_changed_links(mock_wp_feed):
    mock_wp_feed([[1], [2]])

    with httpx.Client() as http:
        update = from_wordpress(
            FeedDocument(http, "https://wp.example/feed/"),
            [
                FeedPage(url="https://wp.example/1/", entries=expected_page([1])),
                FeedPage(url="https://wp.example/2/", entries=expected_page([2])),
            ],
        )

    assert update is not None
    assert update.keep_existing == 0
    assert len(update.new_pages) == 2

    page = update.new_pages[0]
    assert page.url == url_for(1)
    assert page.entries.keys() == expected_page([1]).keys()

    page = update.new_pages[1]
    assert page.url == url_for(2)
    assert page.entries.keys() == expected_page([2]).keys()
