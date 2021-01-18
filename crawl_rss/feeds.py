import datetime
import feedparser
from sqlalchemy.engine import RowProxy
from typing import cast, Dict, Mapping, NamedTuple, Optional, Text
from . import app
from . import models


class PostMetadata(NamedTuple):
    published: Optional[datetime.datetime] = None
    updated: Optional[datetime.datetime] = None
    season: Optional[int] = None
    episode: Optional[int] = None

    @classmethod
    def from_parsed(cls, entry: feedparser.FeedParserDict) -> "PostMetadata":
        published = entry.get("published_parsed")
        # feedparser defaults "updated" to match "published" if not otherwise
        # set, but emits a loud warning if trip that check. This does the same
        # thing but is explicit about it to avoid the warning.
        updated = entry["updated_parsed"] if "updated_parsed" in entry else published
        season = entry.get("itunes_season")
        episode = entry.get("itunes_episode")
        return cls(
            published=published and datetime.datetime(*published[:6]),
            updated=updated and datetime.datetime(*updated[:6]),
            season=season and int(season),
            episode=episode and int(episode),
        )

    @classmethod
    def from_db(cls, entry: RowProxy) -> "PostMetadata":
        return cls(
            published=entry[models.post.c.published],
            updated=entry[models.post.c.updated],
            season=entry[models.post.c.season],
            episode=entry[models.post.c.episode],
        )


class FeedDocument:
    def __init__(
        self, url: Text, proxy: Optional[Text] = None, headers: Dict[Text, Text] = {}
    ):
        response = app.http_client.get(
            url if proxy is None else proxy + url, headers=headers
        )
        response.raise_for_status()

        if "content-location" not in response.headers:
            assert response.url is not None
            response.headers["content-location"] = str(response.url)

        self.doc = feedparser.parse(response, response_headers=response.headers)

    def get_link(self, rel: Text) -> Optional[Text]:
        for link in self.doc.feed.get("links", ()):
            if link.rel == rel:
                return cast(Text, link.href)
        return None

    def posts(self) -> Mapping[Text, PostMetadata]:
        posts = {}
        for raw_entry in self.doc.entries:
            guid = cast(Text, raw_entry.get("id"))
            if guid:
                posts[guid] = PostMetadata.from_parsed(raw_entry)
        return posts
