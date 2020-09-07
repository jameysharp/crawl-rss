import httpx

from .common import FeedDocument
from .wordpress import from_wordpress


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

    mock_atom_feed(
        "https://wp.example/feed/?feed=atom&order=ASC&orderby=modified",
        entries=[1],
    )

    httpx_mock.add_response(
        url="https://wp.example/feed/?feed=atom&order=ASC&orderby=modified&paged=2",
        status_code=404,
    )

    with httpx.Client() as http:
        update = from_wordpress(FeedDocument(http, "https://wp.example/feed/"), [])

    assert update is not None
    assert update.keep_existing == 0
    assert len(update.new_pages) == 1

    page = update.new_pages[0]
    assert page.url == "https://wp.example/feed/?feed=atom&order=ASC&orderby=modified"
    assert sorted(page.entries.keys()) == ["urn:example:post-1"]
