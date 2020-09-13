import httpx
from sqlalchemy import create_engine
from typing import Text

from . import app
from .feed_history.common import crawl_feed_history
from .feed_history.rfc5005 import from_rfc5005
from .feed_history.wordpress import from_wordpress


engine = create_engine("sqlite:///db.sqlite", echo=True)


def http_session() -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": "jamey@minilop.net",
        }
    )


def crawl(url: Text) -> int:
    app.metadata.create_all(engine)
    crawlers = (from_rfc5005, from_wordpress)

    with http_session() as http, engine.begin() as connection:
        return crawl_feed_history(connection, http, crawlers, url)


if __name__ == "__main__":
    import sys

    for url in sys.argv[1:]:
        crawl(url)
