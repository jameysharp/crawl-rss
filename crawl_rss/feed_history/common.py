from dataclasses import dataclass
import datetime
from enum import Enum
import feedparser
import httpx
from sqlalchemy import orm
from sqlalchemy.sql import select
from typing import Any, Callable, Dict, Iterable, List, Optional, Text, cast
from urllib.parse import urljoin

from . import models


class FeedError(Exception):
    pass


class FeedType(Enum):
    COMPLETE = object()
    ARCHIVE = object()
    UNSPECIFIED = object()


class FeedDocument(object):
    def __init__(self, http: httpx.Client, url: Text, headers: Dict[Text, Text] = {}):
        self.http = http
        response = http.get(url, headers=headers)
        response.raise_for_status()

        if "content-location" not in response.headers and response.url:
            response.headers["content-location"] = str(response.url)

        self.doc: feedparser.FeedParserDict = feedparser.parse(
            response.content, response_headers=response.headers
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
                return cast(Text, link.href)
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

    def follow(self, url: Text, headers: Dict[Text, Text] = {}) -> "FeedDocument":
        base_url = self.url
        headers = {"Referer": base_url, **headers}
        return FeedDocument(self.http, urljoin(base_url, url), headers)


@dataclass(frozen=True)
class UpdateFeedHistory:
    keep_existing: int
    new_pages: List[models.FeedArchivePage]

    def __call__(self, db: orm.Session, feed_id: int) -> None:
        # FIXME: try to reuse existing page and entry objects?
        # delete existing pages that have changed
        pages = models.FeedArchivePage.__table__
        db.execute(
            pages.delete()
            .where(pages.c.feed_id == feed_id)
            .where(pages.c.order >= self.keep_existing)
        )

        # append the new archive pages
        new_entries: List[Dict[str, Any]] = []
        add_page = pages.insert()
        for order, page in enumerate(self.new_pages, self.keep_existing):
            result = db.execute(
                add_page, {"feed_id": feed_id, "order": order, "url": page.url}
            )
            page_id = result.inserted_primary_key[0]
            assert page_id is not None

            page_entries = page.entries.values()  # type: ignore
            new_entries.extend(
                {
                    "archive_page_id": page_id,
                    "guid": entry.guid,
                    "title": entry.title,
                    "link": entry.link,
                    "published": entry.published,
                    "updated": entry.updated,
                }
                for entry in page_entries
            )

        # attach all the entries for each of the new pages
        if new_entries:
            db.execute(models.FeedPageEntry.__table__.insert(), new_entries)


Crawler = Callable[
    [FeedDocument, List[models.FeedArchivePage]],
    Optional[UpdateFeedHistory],
]


def crawl_feed_history(
    db: orm.Session, http: httpx.Client, crawlers: Iterable[Crawler], url: Text
) -> int:
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

    # XXX: be more selective?
    properties = base.doc.feed

    feed_table = models.Feed.__table__
    feed = db.execute(
        select([feed_table]).with_for_update().where(feed_table.c.url == url)
    ).first()

    if feed is None:
        result = db.execute(feed_table.insert().values(url=url, properties=properties))
        feed_id = result.inserted_primary_key[0]
    else:
        feed_id = feed[feed_table.c.id]
        if feed[feed_table.c.properties] != properties:
            db.execute(
                feed_table.update()
                .where(feed_table.c.id == feed_id)
                .values(properties=properties)
            )

    archive_pages = (
        db.query(models.FeedArchivePage)
        .filter_by(feed_id=feed_id)
        .order_by(models.FeedArchivePage.order)
    )

    for crawler in crawlers:
        apply_changes = crawler(base, archive_pages)
        if apply_changes is not None:
            break
    else:
        raise FeedError("no history found for feed {!r}".format(url))

    apply_changes(db, feed_id)
    return feed_id
