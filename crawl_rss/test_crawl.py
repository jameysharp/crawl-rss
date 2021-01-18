from itertools import islice
import pytest
from sqlalchemy.sql import bindparam
from . import models
from .crawl import crawl, DiffPosts
from .feeds import PostMetadata


post_page_query = models.page.join(models.post).select()


@pytest.fixture
def feed_id(connection):
    result = connection.execute(
        models.feed.insert(),
        url="http://feed.example",
    )
    return result.inserted_primary_key[0]


def set_pages(connection, feed_id, pages):
    page_query = models.page.insert().values(feed_id=feed_id)
    post_query = models.post.insert().values(feed_id=feed_id)
    page_ids = {}
    for idx, (url, page) in enumerate(pages):
        result = connection.execute(page_query, url=url, idx=idx)
        page_id = result.inserted_primary_key[0]
        page_ids[url] = page_id
        if page:
            connection.execute(
                post_query,
                [
                    {"page_id": page_id, "guid": guid, **post._asdict()}
                    for guid, post in page.items()
                ],
            )
    return page_ids


def get_pages(connection, feed_id):
    page_query = (
        models.page.select()
        .where(models.page.c.feed_id == feed_id)
        .order_by(models.page.c.idx)
    )
    post_query = models.post.select().where(
        models.post.c.page_id == bindparam("page_id")
    )
    pages = []
    for idx, page in enumerate(connection.execute(page_query)):
        assert page[models.page.c.idx] == idx
        posts = {}
        for post in connection.execute(post_query, page_id=page[models.page.c.id]):
            assert post[models.post.c.feed_id] == feed_id
            posts[post[models.post.c.guid]] = PostMetadata.from_db(post)
        pages.append((page[models.page.c.url], posts))
    return pages


def test_diff_empty(connection, feed_id):
    diff = DiffPosts()
    diff.apply(feed_id, connection)
    assert get_pages(connection, feed_id) == []


def test_diff_add_all(connection, feed_id):
    pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example", {"urn:example:2": PostMetadata(episode=2)}),
    ]

    diff = DiffPosts()
    for url, posts in reversed(pages):
        diff.new_page(url, None, posts)
    diff.apply(feed_id, connection)

    assert get_pages(connection, feed_id) == pages


def test_diff_remove_all(connection, feed_id):
    pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example", {"urn:example:2": PostMetadata(episode=2)}),
    ]
    set_pages(connection, feed_id, pages)

    diff = DiffPosts()
    for post in connection.execute(post_page_query):
        diff.old_post(post)
    diff.apply(feed_id, connection)

    assert get_pages(connection, feed_id) == []


def test_diff_unchanged(connection, feed_id):
    pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example", {"urn:example:2": PostMetadata(episode=2)}),
    ]
    page_ids = set_pages(connection, feed_id, pages)

    diff = DiffPosts()
    diff.new_page(pages[1][0], page_ids[pages[1][0]], pages[1][1])
    for post in connection.execute(post_page_query):
        diff.old_post(post)
    diff.new_page(pages[0][0], page_ids[pages[0][0]], pages[0][1])
    diff.apply(feed_id, connection)

    assert get_pages(connection, feed_id) == pages


def test_diff_changed(connection, feed_id):
    pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example", {"urn:example:2": PostMetadata(episode=2)}),
    ]
    page_ids = set_pages(connection, feed_id, pages)

    pages[0][1]["urn:example:1"] = PostMetadata(episode=0)

    diff = DiffPosts()
    for post in connection.execute(post_page_query):
        diff.old_post(post)
    for url, posts in reversed(pages):
        diff.new_page(url, page_ids[url], posts)
    diff.apply(feed_id, connection)

    assert get_pages(connection, feed_id) == pages


def test_diff_moved(connection, feed_id):
    pages = [
        (
            "http://feed.example",
            {
                "urn:example:1": PostMetadata(episode=1),
                "urn:example:2": PostMetadata(episode=2),
            },
        ),
    ]
    page_ids = set_pages(connection, feed_id, pages)

    pages.insert(
        0,
        ("http://feed.example/1", {"urn:example:1": pages[0][1].pop("urn:example:1")}),
    )

    diff = DiffPosts()
    for post in connection.execute(post_page_query):
        diff.old_post(post)
    for url, posts in reversed(pages):
        diff.new_page(url, page_ids.get(url), posts)
    diff.apply(feed_id, connection)

    assert get_pages(connection, feed_id) == pages


def test_diff_add_empty_page(connection, feed_id):
    pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example/2", {}),
        ("http://feed.example", {"urn:example:2": PostMetadata(episode=2)}),
    ]

    diff = DiffPosts()
    for url, posts in reversed(pages):
        diff.new_page(url, None, posts)
    diff.apply(feed_id, connection)

    assert get_pages(connection, feed_id) == pages


def test_diff_add_duplicate(connection, feed_id):
    diff = DiffPosts()
    diff.new_page(
        "http://feed.example", None, {"urn:example:1": PostMetadata(episode=1)}
    )
    diff.new_page(
        "http://feed.example/1", None, {"urn:example:1": PostMetadata(episode=1)}
    )
    diff.apply(feed_id, connection)

    assert get_pages(connection, feed_id) == [
        ("http://feed.example/1", {}),
        ("http://feed.example", {"urn:example:1": PostMetadata(episode=1)}),
    ]


def test_diff_partial_rewrite(connection, feed_id):
    pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example", {"urn:example:2": PostMetadata(episode=2)}),
    ]
    page_ids = set_pages(connection, feed_id, pages)

    pages[1:] = [
        ("http://feed.example/2", {"urn:example:2": PostMetadata(episode=2)}),
        ("http://feed.example", {"urn:example:3": PostMetadata(episode=3)}),
    ]

    diff = DiffPosts()
    diff.new_page(pages[2][0], page_ids[pages[2][0]], pages[2][1])
    for post in connection.execute(post_page_query.where(models.page.c.idx > 0)):
        diff.old_post(post)
    diff.new_page(pages[1][0], None, pages[1][1])
    diff.first_replaced_page = 1
    diff.apply(feed_id, connection)

    assert get_pages(connection, feed_id) == pages


class MockDiffPosts(DiffPosts):
    def __init__(self, httpx_mock, connection, feed_id, old_pages, new_pages, common=0):
        super().__init__()

        page_ids = set_pages(connection, feed_id, old_pages)
        self.mock_old_posts = {
            guid: (page_ids[url], post)
            for url, posts in old_pages[common:]
            for guid, post in posts.items()
        }

        mock_feeds(httpx_mock, new_pages, skip=common)
        self.mock_new_pages = new_pages[common:]

        crawl(feed_id, connection, self)
        assert self.mock_old_posts == {}
        assert self.mock_new_pages == []
        assert self.first_replaced_page == common

    def old_post(self, post):
        assert self.mock_old_posts.pop(post[models.post.c.guid]) == (
            post[models.post.c.page_id],
            PostMetadata.from_db(post),
        )
        super().old_post(post)

    def new_page(self, page_url, page_id, posts):
        assert self.mock_new_pages.pop() == (page_url, posts)
        super().new_page(page_url, page_id, posts)


def mock_feeds(httpx_mock, pages, skip=0):
    pairs = zip([(None, None)] + pages, pages)
    for (prev, _), (url, posts) in islice(pairs, skip, None):
        data = [
            '<feed xmlns="http://www.w3.org/2005/Atom"'
            ' xmlns:itunes="http://www.itunes.com/DTDs/PodCast-1.0.dtd">'
        ]

        if prev is not None:
            data.append(f'<link rel="prev-archive" href="{prev}"/>')

        for guid, post in posts.items():
            data.append(f"<entry><id>{guid}</id>")
            if post.season is not None:
                data.append(f"<itunes:season>{post.season}</itunes:season>")
            if post.episode is not None:
                data.append(f"<itunes:episode>{post.episode}</itunes:episode>")
            data.append("</entry>")

        data.append("</feed>")
        httpx_mock.add_response(url=url, data="".join(data))


def test_crawl_add_all(httpx_mock, connection, feed_id):
    """
    If we've never crawled this feed before, we should be able to add any
    number of archive pages, including duplicate posts, during the initial
    crawl.
    """

    new_pages = [
        (
            "http://feed.example/1",
            {
                "urn:example:1": PostMetadata(episode=1),
                "urn:example:2": PostMetadata(episode=0),
            },
        ),
        ("http://feed.example", {"urn:example:2": PostMetadata(episode=2)}),
    ]

    MockDiffPosts(httpx_mock, connection, feed_id, [], new_pages)


def test_crawl_remove_all(httpx_mock, connection, feed_id):
    """
    If all posts and all archive pages have been removed, we should be left
    with only an empty subscription feed.
    """

    old_pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example", {"urn:example:2": PostMetadata(episode=2)}),
    ]
    new_pages = [("http://feed.example", {})]
    MockDiffPosts(httpx_mock, connection, feed_id, old_pages, new_pages)


def test_crawl_unchanged(httpx_mock, connection, feed_id):
    """
    Even if no posts have changed, we should still re-check the subscription
    feed.
    """

    pages = [("http://feed.example", {"urn:example:1": PostMetadata(episode=1)})]
    MockDiffPosts(httpx_mock, connection, feed_id, pages, pages)


def test_crawl_changed(httpx_mock, connection, feed_id):
    """
    If a post has changed in the subscription feed, we should discover that.
    """

    old_pages = [("http://feed.example", {"urn:example:1": PostMetadata(episode=1)})]
    new_pages = [("http://feed.example", {"urn:example:1": PostMetadata(episode=2)})]
    MockDiffPosts(httpx_mock, connection, feed_id, old_pages, new_pages)


def test_crawl_unchanged_prefix(httpx_mock, connection, feed_id):
    """
    If some prefix of the sequence of archive pages hasn't changed URLs since
    we last crawled this feed, we shouldn't re-check those pages.
    """

    old_pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example/2", {"urn:example:2": PostMetadata(episode=2)}),
        ("http://feed.example", {"urn:example:3": PostMetadata(episode=0)}),
    ]

    new_pages = old_pages[:2] + [
        ("http://feed.example", {"urn:example:3": PostMetadata(episode=3)}),
    ]

    MockDiffPosts(httpx_mock, connection, feed_id, old_pages, new_pages, common=2)


def test_crawl_add_page(httpx_mock, connection, feed_id):
    """
    If a new archive page is added, we should fetch it, but not any unchanged
    earlier pages.
    """

    old_pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example", {"urn:example:2": PostMetadata(episode=2)}),
    ]

    new_pages = old_pages[:1] + [
        ("http://feed.example/2", {"urn:example:2": PostMetadata(episode=2)}),
        ("http://feed.example", {"urn:example:3": PostMetadata(episode=3)}),
    ]

    MockDiffPosts(httpx_mock, connection, feed_id, old_pages, new_pages, common=1)


def test_crawl_remove_page(httpx_mock, connection, feed_id):
    """
    If a post was archived, then the archive page is removed and its contents
    returned to the subscription feed, we should not have to rescan any older
    pages.
    """

    old_pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example/2", {"urn:example:2": PostMetadata(episode=2)}),
        ("http://feed.example", {"urn:example:3": PostMetadata(episode=3)}),
    ]

    new_pages = old_pages[:1] + [
        (
            "http://feed.example",
            {
                "urn:example:2": PostMetadata(episode=2),
                "urn:example:3": PostMetadata(episode=3),
            },
        ),
    ]

    MockDiffPosts(httpx_mock, connection, feed_id, old_pages, new_pages, common=1)


def test_crawl_revised_archive_page(httpx_mock, connection, feed_id):
    """
    If an existing archive page is revised and its URL changes, we should
    discover the changed contents without rescanning older pages.
    """

    old_pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example/2", {"urn:example:2": PostMetadata(episode=0)}),
        ("http://feed.example", {"urn:example:3": PostMetadata(episode=3)}),
    ]

    new_pages = old_pages[:]
    new_pages[1] = ("http://feed.example/3", {"urn:example:2": PostMetadata(episode=2)})

    MockDiffPosts(httpx_mock, connection, feed_id, old_pages, new_pages, common=1)


def test_crawl_archive_post(httpx_mock, connection, feed_id):
    """
    If a post appeared in an older archive page as well as the subscription
    document, we'll only have recorded the most recent copy. If that copy
    disappears, we should scan back until we find the older page it appeared
    on. This test covers the common case where the older copy is in the
    immediately preceding page.
    """

    old_pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example/2", {"urn:example:2": PostMetadata(episode=2)}),
        ("http://feed.example", {"urn:example:3": PostMetadata(episode=3)}),
    ]

    new_pages = old_pages[:1] + [
        (
            "http://feed.example/2",
            {
                "urn:example:2": PostMetadata(episode=2),
                "urn:example:3": PostMetadata(episode=3),
            },
        ),
        (
            "http://feed.example",
            {
                "urn:example:4": PostMetadata(episode=4),
            },
        ),
    ]

    MockDiffPosts(httpx_mock, connection, feed_id, old_pages, new_pages, common=1)


def test_crawl_archive_older_post(httpx_mock, connection, feed_id):
    """
    If a post appeared in an older archive page as well as the subscription
    document, we'll only have recorded the most recent copy. If that copy
    disappears, we should scan back until we find the older page it appeared
    on. This test covers the less common case where the older copy is further
    back in the archives.
    """

    old_pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example/2", {"urn:example:2": PostMetadata(episode=2)}),
        ("http://feed.example/3", {"urn:example:4": PostMetadata(episode=4)}),
        ("http://feed.example", {"urn:example:3": PostMetadata(episode=3)}),
    ]

    new_pages = old_pages[:1] + [
        (
            "http://feed.example/2",
            {
                "urn:example:2": PostMetadata(episode=2),
                "urn:example:3": PostMetadata(episode=3),
            },
        ),
        ("http://feed.example/3", {"urn:example:4": PostMetadata(episode=4)}),
        ("http://feed.example", {"urn:example:5": PostMetadata(episode=5)}),
    ]

    MockDiffPosts(httpx_mock, connection, feed_id, old_pages, new_pages, common=1)


def test_crawl_remove_post(httpx_mock, connection, feed_id):
    """
    Like test_crawl_archive_post, if a post disappears then we should scan back
    until we find it. However, if it's been deleted entirely, then we should
    scan the entire archive just to be sure.
    """

    old_pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example/2", {"urn:example:2": PostMetadata(episode=2)}),
        ("http://feed.example", {"urn:example:3": PostMetadata(episode=3)}),
    ]

    new_pages = old_pages[:2] + [
        ("http://feed.example", {}),
    ]

    MockDiffPosts(httpx_mock, connection, feed_id, old_pages, new_pages)


def test_crawl_reorder_archives(httpx_mock, connection, feed_id):
    """
    An RFC-compliant publisher should not change the order of prev-archive
    links between archive pages without changing the URLs of those pages.
    However, if they do, we shouldn't let that cause database integrity errors;
    preferably, we should reflect the new order.
    """

    old_pages = [
        ("http://feed.example/1", {"urn:example:1": PostMetadata(episode=1)}),
        ("http://feed.example/2", {"urn:example:2": PostMetadata(episode=2)}),
        ("http://feed.example/3", {"urn:example:3": PostMetadata(episode=3)}),
        ("http://feed.example", {"urn:example:4": PostMetadata(episode=4)}),
    ]

    new_pages = [old_pages[0], old_pages[2], old_pages[1], old_pages[3]]

    MockDiffPosts(httpx_mock, connection, feed_id, old_pages, new_pages, common=1)
