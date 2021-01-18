import datetime
from .feeds import FeedDocument, PostMetadata


def test_feed_parsing(httpx_mock):
    """
    Given an Atom feed, we can extract all the necessary feed and post
    metadata.
    """

    url = "http://feed.example/feed.xml"
    data = """
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:itunes="http://www.itunes.com/DTDs/PodCast-1.0.dtd">
    <link rel="self" href="http://feed.example/feed.xml"/>
    <link rel="urn:example:spec" href="http://spec.example/"/>
    <entry>
        <id>urn:example:empty</id>
    </entry>
    <entry>
        <id>urn:example:pub</id>
        <published>2020-01-01T00:00:00Z</published>
    </entry>
    <entry>
        <id>urn:example:upd</id>
        <updated>2020-02-01T00:00:00Z</updated>
    </entry>
    <entry>
        <id>urn:example:epi</id>
        <itunes:episode>1</itunes:episode>
    </entry>
    <entry>
        <id>urn:example:sea</id>
        <itunes:season>2</itunes:season>
        <itunes:episode>3</itunes:episode>
    </entry>
    <entry>
        <id>urn:example:pub-sea</id>
        <published>2020-03-01T00:00:00Z</published>
        <itunes:season>4</itunes:season>
        <itunes:episode>5</itunes:episode>
    </entry>
    </feed>
    """

    httpx_mock.add_response(url=url, data=data)
    doc = FeedDocument(url)

    assert doc.get_link("self") == url
    assert doc.get_link("urn:example:spec") == "http://spec.example/"

    posts = doc.posts()

    assert posts.pop("urn:example:empty") == PostMetadata()
    assert posts.pop("urn:example:pub") == PostMetadata(
        published=datetime.datetime(2020, 1, 1),
        updated=datetime.datetime(2020, 1, 1),
    )
    assert posts.pop("urn:example:upd") == PostMetadata(
        updated=datetime.datetime(2020, 2, 1)
    )
    assert posts.pop("urn:example:epi") == PostMetadata(episode=1)
    assert posts.pop("urn:example:sea") == PostMetadata(season=2, episode=3)
    assert posts.pop("urn:example:pub-sea") == PostMetadata(
        published=datetime.datetime(2020, 3, 1),
        updated=datetime.datetime(2020, 3, 1),
        season=4,
        episode=5,
    )

    assert not posts


def test_with_proxy(httpx_mock):
    """
    Requesting a feed through a transforming proxy uses the Content-Location
    response header to resolve relative links.
    """

    data = """
    <feed xmlns="http://www.w3.org/2005/Atom">
    <link rel="self" href="/feed.xml"/>
    </feed>
    """

    url = "http://feed.example"
    proxy = "http://proxy.example/"
    httpx_mock.add_response(
        url=proxy + url,
        data=data,
        headers={"Content-Location": "http://other.example/feed.atom"},
    )
    doc = FeedDocument(url, proxy)
    assert doc.get_link("self") == "http://other.example/feed.xml"
