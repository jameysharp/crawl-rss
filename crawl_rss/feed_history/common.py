from dataclasses import dataclass
import datetime
from enum import Enum
import feedparser
import requests
from sqlalchemy import orm
from typing import List, Mapping, Optional, Text

from . import models


class Registry(list):
    def __call__(self, x):
        self.append(x)
        return x


crawler_registry = Registry()


class FeedError(Exception):
    pass


class FeedType(Enum):
    COMPLETE = object()
    ARCHIVE = object()
    UNSPECIFIED = object()


class FeedDocument(object):
    def __init__(
        self, http: requests.Session, url: Text, headers: Mapping[Text, Text] = {}
    ):
        with http.get(url, stream=True, headers=headers) as response:
            response.raise_for_status()
            response.headers.setdefault("Content-Location", response.url)
            self.doc: feedparser.FeedParserDict = feedparser.parse(
                response.raw, response_headers=response.headers
            )

    @property
    def url(self) -> Text:
        return self.get_link("self") or self.doc.headers["Content-Location"]

    @property
    def feed_type(self) -> FeedType:
        for short, ns in self.doc.namespaces.items():
            if ns == "http://purl.org/syndication/history/1.0":
                if (short + "_complete") in self.doc.feed:
                    return FeedType.COMPLETE
                if (short + "_archive") in self.doc.feed:
                    return FeedType.ARCHIVE
        return FeedType.UNSPECIFIED

    def get_link(self, rel: Text) -> Optional[Text]:
        for link in self.doc.feed.get("links", ()):
            if link.rel == rel:
                return link.href
        return None

    def as_archive_page(self) -> models.FeedArchivePage:
        page = models.FeedArchivePage(url=self.url)
        for raw_entry in self.doc.entries:
            entry = models.FeedPageEntry(
                guid=raw_entry.get("id"),
                title=raw_entry.get("title", ""),
                link=raw_entry.get("link", ""),
                published=raw_entry.get("published_parsed")
                and datetime.datetime(*raw_entry.published_parsed[:6]),
                updated=raw_entry.get("updated_parsed")
                and datetime.datetime(*raw_entry.updated_parsed[:6]),
            )
            if entry.guid and entry.published:
                page.entries.set(entry)  # type: ignore
        return page


@dataclass(frozen=True)
class UpdateFeedHistory:
    keep_existing: int
    new_pages: List[models.FeedArchivePage]

    def __call__(self, db: orm.Session, feed: models.Feed) -> None:
        # FIXME: try to reuse existing page and entry objects?
        # delete existing pages that have changed
        del feed.archive_pages[self.keep_existing :]  # type: ignore

        db.flush()

        # append the new archive pages
        feed.archive_pages.extend(self.new_pages)  # type: ignore


def crawl_feed_history(
    db: orm.Session, http: requests.Session, url: Text
) -> models.Feed:
    while True:
        base = FeedDocument(http, url)

        self = base.url
        if self and self != url:
            url = self

        current = base.get_link("current")
        if current:
            if url != current:
                url = current
                continue
        elif base.feed_type == FeedType.ARCHIVE:
            raise FeedError(
                "document {!r} has an <archive> tag without a rel='current' link; please try again with the current feed instead".format(
                    url
                )
            )

        # found the right subscription document
        break

    feed = db.query(models.Feed).with_for_update().filter_by(url=url).one_or_none()
    if feed is None:
        feed = models.Feed(url=url)
        db.add(feed)

    # XXX: be more selective?
    feed.properties = base.doc.feed

    for crawler in crawler_registry:
        apply_changes = crawler(http, base, feed.archive_pages)
        if apply_changes is not None:
            break
    else:
        raise FeedError("no history found for feed {!r}".format(url))

    apply_changes(db, feed)
    return feed
