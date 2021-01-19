import re
from sqlalchemy import select
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, RedirectResponse
from starlette.requests import Request
from starlette.routing import Route
from . import models
from .app import engine
from .crawl import crawl, DiffPosts
from .feeds import FeedDocument


POST_ORDERS = {
    "published": (models.post.c.published,),
    "updated": (models.post.c.updated,),
    "episode": (models.post.c.season, models.post.c.episode),
}


def crawl_feed(request: Request) -> RedirectResponse:
    url = request.path_params["url"]

    with engine.begin() as connection:
        feed = connection.execute(
            models.feed.select().where(models.feed.c.url == url)
        ).first()

        if feed is None:
            result = connection.execute(models.feed.insert().values(url=url))
            feed_id = result.inserted_primary_key[0]
        else:
            feed_id = feed[models.feed.c.id]

        diff = DiffPosts()
        crawl(feed_id, connection, diff)
        diff.apply(feed_id, connection)

    return RedirectResponse(request.url_for("list_posts", feed_id=feed_id))


def list_posts(request: Request) -> JSONResponse:
    feed_id = request.path_params["feed_id"]

    try:
        page = int(request.query_params.get("page", 0))
    except ValueError:
        raise HTTPException(404, "invalid page number")

    order = re.fullmatch(r"(-?)(.*)", request.query_params.get("order", "-published"))
    if order is None or order.group(2) not in POST_ORDERS:
        raise HTTPException(404, "unrecognized order")

    # Use database ID for a last-resort stable order
    order_columns = POST_ORDERS[order.group(2)] + (models.post.c.id,)
    if order.group(1) == "-":
        order_clause = [col.desc() for col in order_columns]
    else:
        order_clause = [col.asc() for col in order_columns]

    per_page = 25

    with engine.begin() as connection:
        feed = connection.execute(
            models.feed.outerjoin(models.proxy)
            .select()
            .where(models.feed.c.id == feed_id)
        ).first()

        if feed is None:
            raise HTTPException(404, "no such feed")

        posts = connection.execute(
            select([models.post.c.page_id, models.post.c.guid])
            .where(models.post.c.feed_id == feed_id)
            .order_by(*order_clause)
            .limit(per_page)
            .offset(page * per_page)
        ).fetchall()

        if not posts:
            raise HTTPException(404, "page does not exist")

        page_ids = {post[models.post.c.page_id] for post in posts}
        pages = connection.execute(
            select([models.page.c.id, models.page.c.url]).where(
                models.page.c.id.in_(page_ids)
            )
        ).fetchall()

    proxy = feed[models.proxy.c.url]
    full_posts = {}
    for page_id, page_url in pages:
        # Always fetch from cache if possible, for two reasons:
        # - The cached copy is more likely to match what we saw the last time
        #   we crawled this feed, so we have better odds of returning a result
        #   that was at least valid then.
        # - This is a latency-sensitive endpoint since a person is sitting on
        #   the other end waiting to read whatever we pull up, so we should
        #   retrieve the data they want from as close-by as possible.
        doc = FeedDocument(page_url, proxy, headers={"Cache-Control": "max-stale"})
        full_posts[page_id] = {
            post.id: post for post in doc.doc.entries if "id" in post
        }

    return JSONResponse(
        {
            "posts": [
                full_posts[post[models.post.c.page_id]][post[models.post.c.guid]]
                for post in posts
            ],
            "links": {
                "next": "{}?page={}&order={}".format(
                    request.url_for("list_posts", feed_id=feed_id),
                    page + 1,
                    order.group(0),
                )
            },
        }
    )


app = Starlette(
    routes=[
        Route("/crawl/{url:path}", crawl_feed, name="crawl_feed"),
        Route("/posts/{feed_id:int}", list_posts, name="list_posts"),
    ],
)
