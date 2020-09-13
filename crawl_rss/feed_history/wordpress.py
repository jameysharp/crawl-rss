import itertools
import operator
import httpx
from typing import Iterator, List, Optional, Text, Tuple
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .common import FeedDocument, FeedPage, UpdateFeedHistory


def from_wordpress(
    base: FeedDocument,
    old_pages: List[FeedPage],
) -> Optional[UpdateFeedHistory]:
    if not is_wordpress_generated(base):
        return None

    # try synthesizing from WordPress query args; base is not used as a
    # FeedPage in this case. refetch the oldest page to validate that
    # WordPress-style pagination will work
    base = base.follow(
        query_string_replace(
            base.url,
            feed="atom",
            order="ASC",
            orderby="modified",
        )
    )

    urls = wordpress_pagination_urls(base.url)
    new_pages = []

    if all(old.url == new for old, new in zip(old_pages, urls)):
        # if we have existing pages, re-fetch them, starting from the newest
        # and working backward, until we find one where the last-updated entry
        # hasn't changed.
        keep_existing = len(old_pages)
        key = operator.attrgetter("updated", "link")
        for old_page, new_page in refresh_wordpress_pages(base, old_pages):
            if new_page is None:
                # if some of the old pages have disappeared, there's no point
                # looking for pages we never saw before
                urls = iter(())
            else:
                old_last = old_page.last_updated_entry()
                new_last = new_page.last_updated_entry()
                if old_last and new_last and key(old_last) == key(new_last):
                    break
                new_pages.append(new_page)
            keep_existing -= 1
        new_pages.reverse()

        # zip consumed exactly as many elements of `urls` as there were pages
        # in `old_pages`, so the loop below starts at the next page
    else:
        # url scheme seems different so start over from the beginning
        keep_existing = 0
        urls = wordpress_pagination_urls(base.url)

    # then walk forwards from the page after the newest one we have, or page 1 if we didn't have any
    try:
        for page_url in urls:
            new_pages.append(base.follow(page_url).as_page())
    except httpx.HTTPStatusError as e:
        # 404 terminates the loop but isn't fatal
        if e.response.status_code != 404:
            raise

    if not keep_existing and not new_pages:
        return None

    return UpdateFeedHistory(keep_existing, new_pages)


def is_wordpress_generated(feed: FeedDocument) -> bool:
    if 'rel="https://api.w.org/"' in feed.doc.headers.get("Link", ""):
        return True

    generator = feed.doc.feed.get("generator_detail") or {}
    for ident in generator.values():
        ident = ident.lower()
        if "wordpress.com" in ident or "wordpress.org" in ident:
            return True

    return False


def wordpress_pagination_urls(url: Text) -> Iterator[Text]:
    yield url
    for page in itertools.count(2):
        yield query_string_replace(url, paged=str(page))


def query_string_replace(url: Text, **kwargs: Text) -> Text:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in kwargs]
    query.extend(sorted(kwargs.items()))
    return urlunsplit(parts._replace(query=urlencode(query)))


def refresh_wordpress_pages(
    base: FeedDocument,
    old_pages: List[FeedPage],
) -> Iterator[Tuple[FeedPage, Optional[FeedPage]]]:
    if not old_pages:
        return

    found_later = False
    for old_page in reversed(old_pages[1:]):
        new_page = None
        try:
            new_page = base.follow(old_page.url).as_page()
            found_later = True
        except httpx.HTTPStatusError as e:
            # 404 is okay because it just means the history got shorter, unless
            # we've already found later pages, in which case even 404 is bad
            if found_later or e.response.status_code != 404:
                raise
        yield old_page, new_page

    yield old_pages[0], base.as_page()
