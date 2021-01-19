from collections import defaultdict
from sqlalchemy.sql import and_, bindparam, func, select
from sqlalchemy.engine import Connection, RowProxy
from typing import DefaultDict, Dict, List, Mapping, Optional, Set, Text, Tuple
from . import models
from .feeds import FeedDocument, PostMetadata


class DiffPosts:
    def __init__(self) -> None:
        self.first_replaced_page: int = 0
        self.old_posts: Dict[Text, Tuple[int, int, PostMetadata]] = {}
        self.new_posts: Dict[Text, Tuple[str, Optional[int], PostMetadata]] = {}
        self.new_pages: List[str] = []
        self.matched: Set[Text] = set()
        self.updated: DefaultDict[str, List[Tuple[int, PostMetadata]]] = defaultdict(
            list
        )

    def _match(
        self,
        guid: Text,
        old: Tuple[int, int, PostMetadata],
        new: Tuple[str, Optional[int], PostMetadata],
    ) -> None:
        self.matched.add(guid)
        if old[1:] != new[1:]:
            self.updated[new[0]].append((old[0], new[2]))

    def old_post(self, post: RowProxy) -> None:
        guid = post[models.post.c.guid]
        assert guid not in self.matched and guid not in self.old_posts

        old_post = (
            post[models.post.c.id],
            post[models.post.c.page_id],
            PostMetadata.from_db(post),
        )
        new_post = self.new_posts.pop(guid, None)
        if new_post is None:
            self.old_posts[guid] = old_post
        else:
            self._match(guid, old_post, new_post)

    def new_page(
        self, page_url: str, page_id: Optional[int], posts: Mapping[Text, PostMetadata]
    ) -> None:
        self.new_pages.append(page_url)

        for guid, post in posts.items():
            if guid in self.matched or guid in self.new_posts:
                continue
            new_post = (page_url, page_id, post)
            old_post = self.old_posts.pop(guid, None)
            if old_post is None:
                self.new_posts[guid] = new_post
            else:
                self._match(guid, old_post, new_post)

    def apply(self, feed_id: int, connection: Connection) -> None:
        # First, ensure all the URLs in self.new_pages have corresponding rows
        # in the database. (Re-)number them to use negative indexes so they
        # can't conflict with any existing page indexes. We can't delete the
        # conflicting pages until we've reassigned or deleted all their posts,
        # which we can't do until the new pages have IDs assigned.

        page_ids = dict(
            connection.execute(
                select([models.page.c.url, models.page.c.id])
                .where(models.page.c.feed_id == feed_id)
                .where(models.page.c.idx >= self.first_replaced_page)
            ).fetchall()
        )

        add_page = models.page.insert()
        update_pages = []
        for idx, page in enumerate(reversed(self.new_pages), 1):
            old_page_id = page_ids.get(page)
            if old_page_id is not None:
                update_pages.append({"idx": -idx, "page_id": old_page_id})
            else:
                result = connection.execute(
                    add_page, idx=-idx, url=page, feed_id=feed_id
                )
                page_ids[page] = result.inserted_primary_key[0]

        if update_pages:
            connection.execute(
                models.page.update().where(models.page.c.id == bindparam("page_id")),
                update_pages,
            )

        # Now ensure that all the right posts exist and that they use the new
        # page IDs.

        update_posts = []
        for page, posts in self.updated.items():
            page_id = page_ids[page]
            for post_id, post in posts:
                update_posts.append(
                    {"page_id": page_id, "post_id": post_id, **post._asdict()}
                )

        if update_posts:
            connection.execute(
                models.post.update().where(models.post.c.id == bindparam("post_id")),
                update_posts,
            )

        if self.new_posts:
            connection.execute(
                models.post.insert(),
                [
                    {
                        "guid": guid,
                        "page_id": page_ids[page_url],
                        "feed_id": feed_id,
                        **page._asdict(),
                    }
                    for guid, (page_url, page_id, page) in self.new_posts.items()
                ],
            )

        if self.old_posts:
            connection.execute(
                models.post.delete().where(models.post.c.id == bindparam("id")),
                [{"id": old[1]} for old in self.old_posts.values()],
            )

        # Finally, delete any now-unreferenced pages and renumber the used
        # pages to their final indexes.

        connection.execute(
            models.page.delete()
            .where(models.page.c.feed_id == feed_id)
            .where(models.page.c.idx >= self.first_replaced_page)
        )

        connection.execute(
            models.page.update()
            .where(models.page.c.feed_id == feed_id)
            .where(models.page.c.idx < 0)
            .values(idx=-models.page.c.idx + (self.first_replaced_page - 1))
        )


def crawl(feed_id: int, connection: Connection, diff: DiffPosts) -> None:
    feed = connection.execute(
        models.feed.outerjoin(models.proxy)
        .outerjoin(
            models.page,
            and_(
                models.feed.c.id == models.page.c.feed_id,
                models.feed.c.url == models.page.c.url,
            ),
        )
        .select()
        .where(models.feed.c.id == feed_id)
    ).first()

    url = feed[models.feed.c.url]
    proxy = feed[models.proxy.c.url]

    doc = FeedDocument(url, proxy)

    subscription_page_id = feed[models.page.c.id]
    diff.new_page(url, subscription_page_id, doc.posts())

    if subscription_page_id is not None:
        diff.first_replaced_page = feed[models.page.c.idx]
        for post in connection.execute(
            models.post.select().where(models.post.c.page_id == subscription_page_id)
        ):
            diff.old_post(post)
    else:
        diff.first_replaced_page = connection.execute(
            select([func.count()])
            .select_from(models.page)
            .where(models.page.c.feed_id == feed_id)
        ).scalar()

    # At this point, if the subscription feed hasn't changed since the last
    # crawl, then DiffPosts has put all its GUIDs in the "matched" set and
    # represents a no-op. But we still have to check whether the prev-archive
    # link has changed.

    get_old_page = (
        models.page.select()
        .where(models.page.c.feed_id == feed_id)
        .where(models.page.c.url == bindparam("url"))
    )
    # XXX: do we get better query plans testing the feed_id in page, post, or both?
    get_old_posts = (
        select([models.post])
        .select_from(models.post.join(models.page))
        .where(models.page.c.feed_id == feed_id)
    )
    seen: Set[str] = set()
    url = doc.get_link("prev-archive")

    while url is not None and url not in seen:
        seen.add(url)

        old_page = connection.execute(get_old_page, url=url).first()
        page_id = None
        if old_page is not None:
            page_id = old_page[models.page.c.id]
            old_page_idx = old_page[models.page.c.idx]
            if old_page_idx + 1 < diff.first_replaced_page:
                for post in connection.execute(
                    get_old_posts.where(models.page.c.idx > old_page_idx).where(
                        models.page.c.idx < diff.first_replaced_page
                    )
                ):
                    diff.old_post(post)

                diff.first_replaced_page = old_page_idx + 1

            # We followed a prev-archive link to a page which we've seen in a
            # previous crawl. That should mean we don't have to check any
            # further. But if there are any posts which used to be somewhere
            # after this point, but that we haven't seen so far on this crawl,
            # then we need to check back further to figure out which page those
            # posts were on, if any.
            if not diff.old_posts:
                return

        # Archive feed documents aren't supposed to change without being moved
        # to a new URL, so if there's a copy in cache it's supposed to be okay
        # to just use it.
        doc = FeedDocument(url, proxy, headers={"Cache-Control": "max-stale"})
        diff.new_page(url, page_id, doc.posts())
        url = doc.get_link("prev-archive")

    # We've checked all the (possibly empty) archives without finding an
    # unchanged prefix, so we need to rewrite all pages.
    for post in connection.execute(
        get_old_posts.where(models.page.c.idx < diff.first_replaced_page)
    ):
        diff.old_post(post)

    diff.first_replaced_page = 0
