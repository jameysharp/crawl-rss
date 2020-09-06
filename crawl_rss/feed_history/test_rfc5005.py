import httpx

from .common import FeedDocument
from .models import FeedArchivePage
from .rfc5005 import from_rfc5005


def test_incomplete_feed(mock_atom_feed):
    """
    If the feed is not complete and does not have archived pages, it is not an
    RFC5005 feed.
    """

    mock_atom_feed("https://rfc5005.example/feed.xml")

    with httpx.Client() as http:
        update = from_rfc5005(
            FeedDocument(http, "https://rfc5005.example/feed.xml"), []
        )

    assert update is None


def test_updated_complete_feed(mock_atom_feed):
    """
    A feed that is marked complete should generate an update that replaces
    whatever we had before with the contents of the updated feed.
    """

    mock_atom_feed(
        "https://rfc5005.example/feed.xml",
        complete=True,
        entries=[1],
    )

    with httpx.Client() as http:
        update = from_rfc5005(
            FeedDocument(http, "https://rfc5005.example/feed.xml"),
            [FeedArchivePage(url="https://rfc5005.example/feed.xml")],
        )

    assert update is not None
    assert update.keep_existing == 0
    assert len(update.new_pages) == 1

    page = update.new_pages[0]
    assert page.url == "https://rfc5005.example/feed.xml"
    assert sorted(page.entries.keys()) == ["urn:example:post-1"]


def test_new_archived_feed(mock_atom_feed):
    """
    A feed we haven't seen before that has archived pages should cause us to
    fetch all the pages and add all their entries.
    """

    mock_atom_feed(
        "https://rfc5005.example/feed.xml",
        links={
            "prev-archive": "https://rfc5005.example/feed-1.xml",
        },
        entries=[3, 2],
    )

    mock_atom_feed(
        "https://rfc5005.example/feed-1.xml",
        archive=True,
        links={
            "current": "https://rfc5005.example/feed.xml",
        },
        entries=[2, 1],
    )

    with httpx.Client() as http:
        update = from_rfc5005(
            FeedDocument(http, "https://rfc5005.example/feed.xml"), []
        )

    assert update is not None
    assert update.keep_existing == 0
    assert len(update.new_pages) == 2

    page = update.new_pages[0]
    assert page.url == "https://rfc5005.example/feed-1.xml"
    assert sorted(page.entries.keys()) == [
        "urn:example:post-1",
        "urn:example:post-2",
    ]

    page = update.new_pages[1]
    assert page.url == "https://rfc5005.example/feed.xml"
    assert sorted(page.entries.keys()) == [
        "urn:example:post-2",
        "urn:example:post-3",
    ]


def test_extended_archived_feed(mock_atom_feed):
    """
    When a new archive page is added, we fetch it, but not any unchanged
    earlier pages.
    """

    mock_atom_feed(
        "https://rfc5005.example/feed.xml",
        links={
            "prev-archive": "https://rfc5005.example/feed-2.xml",
        },
        entries=[5, 4],
    )

    mock_atom_feed(
        "https://rfc5005.example/feed-2.xml",
        archive=True,
        links={
            "current": "https://rfc5005.example/feed.xml",
            "prev-archive": "https://rfc5005.example/feed-1.xml",
        },
        entries=[4, 3],
    )

    with httpx.Client() as http:
        update = from_rfc5005(
            FeedDocument(http, "https://rfc5005.example/feed.xml"),
            [
                FeedArchivePage(url="https://rfc5005.example/feed-1.xml"),
                FeedArchivePage(url="https://rfc5005.example/feed.xml"),
            ],
        )

    assert update is not None
    assert update.keep_existing == 1
    assert len(update.new_pages) == 2

    page = update.new_pages[0]
    assert page.url == "https://rfc5005.example/feed-2.xml"
    assert sorted(page.entries.keys()) == [
        "urn:example:post-3",
        "urn:example:post-4",
    ]

    page = update.new_pages[1]
    assert page.url == "https://rfc5005.example/feed.xml"
    assert sorted(page.entries.keys()) == [
        "urn:example:post-4",
        "urn:example:post-5",
    ]


def test_revised_archived_feed(mock_atom_feed):
    """
    When an existing archive page is revised and its URL changes, we replace
    the old version with the new one.
    """

    mock_atom_feed(
        "https://rfc5005.example/feed.xml",
        links={
            "prev-archive": "https://rfc5005.example/feed-2bis.xml",
        },
        entries=[5, 4],
    )

    mock_atom_feed(
        "https://rfc5005.example/feed-2bis.xml",
        archive=True,
        links={
            "current": "https://rfc5005.example/feed.xml",
            "prev-archive": "https://rfc5005.example/feed-1.xml",
        },
        entries=[4, 3],
    )

    with httpx.Client() as http:
        update = from_rfc5005(
            FeedDocument(http, "https://rfc5005.example/feed.xml"),
            [
                FeedArchivePage(url="https://rfc5005.example/feed-1.xml"),
                FeedArchivePage(url="https://rfc5005.example/feed-2.xml"),
                FeedArchivePage(url="https://rfc5005.example/feed.xml"),
            ],
        )

    assert update is not None
    assert update.keep_existing == 1
    assert len(update.new_pages) == 2

    page = update.new_pages[0]
    assert page.url == "https://rfc5005.example/feed-2bis.xml"
    assert sorted(page.entries.keys()) == [
        "urn:example:post-3",
        "urn:example:post-4",
    ]

    page = update.new_pages[1]
    assert page.url == "https://rfc5005.example/feed.xml"
    assert sorted(page.entries.keys()) == [
        "urn:example:post-4",
        "urn:example:post-5",
    ]
