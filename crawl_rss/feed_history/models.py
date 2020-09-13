from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Table,
    Text,
    UnicodeText,
    UniqueConstraint,
)

from .. import app


feeds = Table(
    "feeds",
    app.metadata,
    Column("id", Integer, primary_key=True),
    Column("url", Text, unique=True, nullable=False),
    Column("properties", JSON, nullable=False),
)

feed_archive_pages = Table(
    "feed_archive_pages",
    app.metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "feed_id", Integer, ForeignKey(feeds.c.id, ondelete="CASCADE"), nullable=False
    ),
    Column("order", Integer, nullable=False),
    Column("url", Text, nullable=False),
    UniqueConstraint("feed_id", "order"),
    UniqueConstraint("url", "feed_id"),
)

feed_page_entries = Table(
    "feed_page_entries",
    app.metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "archive_page_id",
        Integer,
        ForeignKey(feed_archive_pages.c.id, ondelete="CASCADE"),
        nullable=False,
    ),
    Column("guid", Text, nullable=False),
    Column("title", UnicodeText, nullable=False),
    Column("link", Text, nullable=False),
    Column("published", DateTime, nullable=False),
    Column("updated", DateTime),
    UniqueConstraint("archive_page_id", "guid"),
)
