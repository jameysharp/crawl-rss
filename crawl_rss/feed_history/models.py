from sqlalchemy import (
    Column,
    Integer,
    Text,
    UnicodeText,
    DateTime,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy import orm
from sqlalchemy.orm.collections import attribute_mapped_collection
from sqlalchemy.ext.orderinglist import ordering_list

from .. import app


__all__ = (
    "Feed",
    "FeedArchivePage",
    "FeedPageEntry",
)


class Feed(app.Base):
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True)
    url = Column(Text, unique=True, nullable=False)
    properties = Column(JSON, nullable=False)

    archive_pages = orm.relationship(
        "FeedArchivePage",
        backref="feed",
        cascade="all, delete-orphan",
        order_by="FeedArchivePage.order",
        collection_class=ordering_list("order"),
    )


class FeedArchivePage(app.Base):
    __tablename__ = "feed_archive_pages"

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey(Feed.__table__.c.id), nullable=False)
    order = Column(Integer, nullable=False)
    url = Column(Text, nullable=False)

    entries = orm.relationship(
        "FeedPageEntry",
        backref="archive_page",
        cascade="all, delete-orphan",
        collection_class=attribute_mapped_collection("guid"),
    )

    __table_args__ = (
        UniqueConstraint(feed_id, order),
        UniqueConstraint(url, feed_id),
    )


class FeedPageEntry(app.Base):
    __tablename__ = "feed_page_entries"

    id = Column(Integer, primary_key=True)
    archive_page_id = Column(
        Integer, ForeignKey(FeedArchivePage.__table__.c.id), nullable=False
    )
    guid = Column(Text, nullable=False)
    title = Column(UnicodeText, nullable=False)
    link = Column(Text, nullable=False)
    published = Column(DateTime, nullable=False)
    updated = Column(DateTime)

    __table_args__ = (UniqueConstraint(archive_page_id, guid),)
