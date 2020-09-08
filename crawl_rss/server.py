from contextlib import closing
from starlette.applications import Starlette
from starlette.responses import JSONResponse, RedirectResponse
from starlette.requests import Request
from starlette.routing import Route

from .fetch import crawl, Session
from .feed_history.models import FeedArchivePage, FeedPageEntry


def crawl_feed(request: Request) -> RedirectResponse:
    feed_id = crawl(request.path_params["url"])
    return RedirectResponse(request.url_for("list_posts", feed_id=feed_id))


def list_posts(request: Request) -> JSONResponse:
    with closing(Session()) as db:
        posts = (
            db.query(FeedPageEntry)
            .join(FeedArchivePage)
            .filter(FeedArchivePage.feed_id == request.path_params["feed_id"])
            .order_by(FeedArchivePage.order, FeedPageEntry.published)
        )

    # remove duplicates
    by_guid = {}
    for post in posts:
        by_guid[post.guid] = post

    return JSONResponse(
        [
            post.link
            for post in sorted(by_guid.values(), key=lambda post: post.published)
        ]
    )


app = Starlette(
    routes=[
        Route("/crawl/{url:path}", crawl_feed, name="crawl_feed"),
        Route("/posts/{feed_id:int}", list_posts, name="list_posts"),
    ],
)
