from contextlib import closing
from http.client import HTTPConnection
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Text

from . import app
from .feed_history.common import crawl_feed_history


HTTPConnection.debuglevel = 1  # type: ignore
engine = create_engine('sqlite:///:memory:', echo=True)
Session = sessionmaker(bind=engine)


def http_session() -> requests.Session:
    http = requests.Session()
    http.headers['User-Agent'] = 'jamey@minilop.net'
    return http


def crawl(url: Text) -> None:
    app.Base.metadata.create_all(engine)

    with http_session() as http, closing(Session()) as db:
        crawl_feed_history(db, http, url)
        db.commit()


if __name__ == '__main__':
    import sys
    for url in sys.argv[1:]:
        crawl(url)
