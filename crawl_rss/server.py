import re
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, RedirectResponse
from starlette.requests import Request
from starlette.routing import Route
from . import models
from .app import engine
from .crawl import crawl, DiffPosts


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
        posts = connection.execute(
            models.post.select()
            .where(models.post.c.feed_id == feed_id)
            .order_by(*order_clause)
            .limit(per_page)
            .offset(page * per_page)
        ).fetchall()

        if not posts:
            raise HTTPException(404, "page does not exist")

        page_ids = {post[models.post.c.page_id] for post in posts}
        pages = {
            page[models.page.c.id]: page[models.page.c.url]
            for page in connection.execute(
                models.page.select().where(models.page.c.id.in_(page_ids))
            )
        }

    return JSONResponse(
        {
            "posts": [
                {
                    "guid": post[models.post.c.guid],
                    "page": pages[post[models.post.c.page_id]],
                    "published": post[models.post.c.published].isoformat(),
                    "updated": post[models.post.c.updated].isoformat(),
                    "season": post[models.post.c.season],
                    "episode": post[models.post.c.episode],
                }
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
