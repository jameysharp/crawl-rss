from sqlalchemy.sql import select
from starlette.applications import Starlette
from starlette.responses import JSONResponse, RedirectResponse
from starlette.requests import Request
from starlette.routing import Route

from .fetch import crawl, engine
from .feed_history import models


def crawl_feed(request: Request) -> RedirectResponse:
    feed_id = crawl(request.path_params["url"])
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
