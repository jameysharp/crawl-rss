import httpx
from pytest_httpx import HTTPXMock  # type: ignore
from typing import Mapping

from .common import FeedDocument
from .rfc5005 import from_rfc5005


def make_feed(
    links: Mapping[str, str] = {},
) -> str:
    return f"""
    <feed xmlns="http://www.w3.org/2005/Atom">
    {"".join(f"<link href={href!r} rel={rel!r}/>" for rel, href in links.items())}
    </feed>
    """


def test_new_feed(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://rfc5005.example/feed.xml",
        data=make_feed(
            links={
                "prev-archive": "https://rfc5005.example/feed-1.xml",
            }
        ),
    )

    httpx_mock.add_response(
        url="https://rfc5005.example/feed-1.xml",
        data=make_feed(),
    )

    with httpx.Client() as http:
        update = from_rfc5005(
            FeedDocument(http, "https://rfc5005.example/feed.xml"), []
        )

    assert update is not None
    assert update.keep_existing == 0
    assert len(update.new_pages) == 2
