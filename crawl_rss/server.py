from sqlalchemy.sql import select
from starlette.applications import Starlette
from starlette.responses import JSONResponse, RedirectResponse
from starlette.requests import Request
from starlette.routing import Route

from .app import engine, metadata
from .feed_history import models
from .feed_history.common import crawl_feed_history
from .feed_history.rfc5005 import from_rfc5005
from .feed_history.wordpress import from_wordpress


def crawl_feed(request: Request) -> RedirectResponse:
    metadata.create_all(engine)
    crawlers = (from_rfc5005, from_wordpress)

    with engine.begin() as connection:
        feed_id = crawl_feed_history(connection, crawlers, request.path_params["url"])

    return RedirectResponse(request.url_for("list_posts", feed_id=feed_id))


def list_posts(request: Request) -> JSONResponse:
    with engine.begin() as connection:
        page = models.feed_archive_pages
        entry = models.feed_page_entries
        posts = connection.execute(
            select([entry])
            .select_from(entry.join(page))
            .where(page.c.feed_id == request.path_params["feed_id"])
            .order_by(page.c.order, entry.c.published)
        )

        # remove duplicates
        by_guid = {}
        for post in posts:
            by_guid[post[entry.c.guid]] = post

    return JSONResponse(
        [
            post[entry.c.link]
            for post in sorted(
                by_guid.values(), key=lambda post: post[entry.c.published]
            )
        ]
    )


app = Starlette(
    routes=[
        Route("/crawl/{url:path}", crawl_feed, name="crawl_feed"),
        Route("/posts/{feed_id:int}", list_posts, name="list_posts"),
    ],
)
