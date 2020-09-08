from contextlib import closing
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Text

from . import app
from .feed_history.common import crawl_feed_history
from .feed_history.rfc5005 import from_rfc5005
from .feed_history.wordpress import from_wordpress


engine = create_engine("sqlite:///db.sqlite", echo=True)
Session = sessionmaker(bind=engine)


def http_session() -> httpx.Client:
    return httpx.Client(
        headers={
            "User-Agent": "jamey@minilop.net",
        }
    )


def crawl(url: Text) -> int:
    app.Base.metadata.create_all(engine)
    crawlers = (from_rfc5005, from_wordpress)

    with http_session() as http, closing(Session()) as db:
        feed_id = crawl_feed_history(db, http, crawlers, url).id
        db.commit()

    return feed_id


if __name__ == "__main__":
    import sys

    for url in sys.argv[1:]:
        crawl(url)
