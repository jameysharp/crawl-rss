import cachecontrol
from cachecontrol.caches import FileCache
from cachecontrol.heuristics import LastModified
from contextlib import closing
from http.client import HTTPConnection
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Text

from . import app
from .feed_history.common import crawl_feed_history


HTTPConnection.debuglevel = 1
engine = create_engine('sqlite:///:memory:', echo=True)
Session = sessionmaker(bind=engine)


def crawl(url: Text) -> None:
    app.Base.metadata.create_all(engine)

    with requests.Session() as http, closing(Session()) as db:
        cache = cachecontrol.CacheControlAdapter(
            cache=FileCache('.httpcache'),
            heuristic=LastModified(),
        )
        http.mount('https://', cache)
        http.mount('http://', cache)

        http.headers['User-Agent'] = b'jamey@minilop.net'

        crawl_feed_history(db, http, url)
        db.commit()


if __name__ == '__main__':
    import sys
    for url in sys.argv[1:]:
        crawl(url)