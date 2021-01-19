from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Table,
    Text,
    UnicodeText,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from . import appconfig


proxy = Table(
    "proxy",
    appconfig.metadata,
    Column("id", Integer, primary_key=True),
    Column("url", Text, unique=True, nullable=False),
    Column("name", UnicodeText, nullable=False),
    Column("priority", Integer, nullable=False),
)

feed = Table(
    "feed",
    appconfig.metadata,
    Column("id", Integer, primary_key=True),
    Column("url", Text, unique=True, nullable=False),
    Column("proxy_id", ForeignKey(proxy.c.id, ondelete="RESTRICT")),
    Column("properties", JSON, nullable=False, default={}),
    Column("next_check", DateTime, nullable=False, default=func.now()),
)

page = Table(
    "page",
    appconfig.metadata,
    Column("id", Integer, primary_key=True),
    Column("feed_id", ForeignKey(feed.c.id, ondelete="CASCADE"), nullable=False),
    Column("idx", Integer, nullable=False),
    Column("url", Text, unique=True, nullable=False),
    UniqueConstraint("feed_id", "idx"),
)

# Index of posts found from a given feed. This table should contain the bare
# minimum needed for sorting posts and looking them up in the original archive
# feed documents.
post = Table(
    "post",
    appconfig.metadata,
    Column("id", Integer, primary_key=True),
    Column("guid", Text, nullable=False),
    # Note that a GUID may appear on multiple pages of an archived feed. To
    # keep the schema simple, we only record whichever copy is "current"
    # according to RFC5005 deduplication. The feed crawler may have to rescan
    # older pages to ensure consistency if this post disappears from this page.
    Column("page_id", ForeignKey(page.c.id, ondelete="RESTRICT"), nullable=False),
    # Denormalized to support good indexes: must match page_id->feed_id
    Column("feed_id", ForeignKey(feed.c.id, ondelete="CASCADE"), nullable=False),
    UniqueConstraint("feed_id", "guid"),
    # Published/updated are in both RSS and Atom
    Column("published", DateTime),
    Index("ix_published", "feed_id", "published"),
    Column("updated", DateTime),
    Index("ix_updated", "feed_id", "updated"),
    # Season/episode from https://web.archive.org/web/20190315020506/https://help.apple.com/itc/podcasts_connect/#/itcb54353390
    Column("season", Integer),
    Column("episode", Integer),
    Index("ix_season_episode", "feed_id", "season", "episode"),
)

# A schema for https://tools.ietf.org/html/draft-snell-atompub-feed-index-10:
# rank_scheme = Table(
#    "rank_scheme",
#    appconfig.metadata,
#    Column("id", Integer, primary_key=True),
#    Column("uri", Text, unique=True, nullable=False),
# )
#
# rank_domain = Table(
#    "rank_domain",
#    appconfig.metadata,
#    Column("id", Integer, primary_key=True),
#    Column("uri", Text, unique=True, nullable=False),
# )
#
# rank = Table(
#    "rank",
#    appconfig.metadata,
#    Column("post_id", ForeignKey(post.c.id, ondelete="CASCADE"), nullable=False),
#    Column("scheme_id", ForeignKey(rank_scheme.c.id, ondelete="RESTRICT"), nullable=False),
#    Column("domain_id", ForeignKey(rank_domain.c.id, ondelete="RESTRICT"), nullable=False),
#    Column("rank", Float),
#    UniqueConstraint("post_id", "scheme_id", "domain_id"),
# )
