import itertools
import operator
import requests
from typing import Iterator, List, Optional, Text, Tuple
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .common import crawler_registry, FeedDocument, UpdateFeedHistory
from .models import FeedArchivePage


@crawler_registry
def from_wordpress(
    http: requests.Session,
    base: FeedDocument,
    old_pages: List[FeedArchivePage],
) -> Optional[UpdateFeedHistory]:
    if not is_wordpress_generated(base):
        return None

    # try synthesizing from WordPress query args; base is not used as a
    # FeedArchivePage in this case. refetch the oldest page to validate that
    # WordPress-style pagination will work
    base = FeedDocument(http, query_string_replace(
        base.url,
        feed="atom",
        order="ASC",
        orderby="modified",
    ))

    urls = wordpress_pagination_urls(base.url)
    new_pages = []

    if all(old.url == new for old, new in zip(old_pages, urls)):
        # if we have existing pages, re-fetch them, starting from the newest
        # and working backward, until we find one where the last-updated entry
        # hasn't changed.
        keep_existing = len(old_pages)
        key = operator.attrgetter('updated', 'link')
        for old_page, new_page in refresh_wordpress_pages(http, base, old_pages):
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
            new_pages.append(FeedDocument(http, page_url).as_archive_page())
    except requests.HTTPError as e:
        # 404 terminates the loop but isn't fatal
        if e.response.status_code != 404:
            raise

    if not keep_existing and not new_pages:
        return None

    return UpdateFeedHistory(keep_existing, new_pages)


def is_wordpress_generated(feed: FeedDocument) -> bool:
    for link in requests.utils.parse_header_links(feed.doc.headers['Link']):
        if link.get('rel') == 'https://api.w.org/':
            return True

    generator = feed.doc.get('generator_detail') or {}
    for ident in generator.values():
        ident = ident.lower()
        if "wordpress.com" in ident or "wordpress.org" in ident:
            return True

    return False


def wordpress_pagination_urls(url: Text) -> Iterator[Text]:
    yield url
    for page in itertools.count(2):
        yield query_string_replace(url, paged=page)


def query_string_replace(url: Text, **kwargs) -> Text:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in kwargs]
    query.extend(sorted(kwargs.items()))
    return urlunsplit(parts._replace(query=urlencode(query)))


def refresh_wordpress_pages(
    http: requests.Session,
    base: FeedDocument,
    old_pages: List[FeedArchivePage],
) -> Iterator[Tuple[FeedArchivePage, Optional[FeedArchivePage]]]:
    if not old_pages:
        return

    found_later = False
    for old_page in reversed(old_pages[1:]):
        new_page = None
        try:
            new_page = FeedDocument(http, old_page.url).as_archive_page()
            found_later = True
        except requests.HTTPError as e:
            # 404 is okay because it just means the history got shorter, unless
            # we've already found later pages, in which case even 404 is bad
            if found_later or e.response.status_code != 404:
                raise
        yield old_page, new_page

    yield old_pages[0], base.as_archive_page()
