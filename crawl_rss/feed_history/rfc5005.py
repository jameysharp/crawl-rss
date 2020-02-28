import requests
from typing import List

from .common import crawler_registry, FeedDocument, FeedType
from .models import FeedArchivePage


@crawler_registry
def from_rfc5005_complete(
    http: requests.Session,
    base: FeedDocument,
    old_pages: List[FeedArchivePage],
    new_pages: List[FeedArchivePage],
) -> int:
    if base.feed_type == FeedType.COMPLETE:
        # feed gets one FeedArchivePage containing all of base's FeedPageEntries
        new_pages.append(base.as_archive_page())
    return 0


@crawler_registry
def from_rfc5005_archived(
    http: requests.Session,
    base: FeedDocument,
    old_pages: List[FeedArchivePage],
    new_pages: List[FeedArchivePage],
) -> int:
    # walk backwards until we hit an existing FeedArchivePage
    existing_pages = {page.url: keep for keep, page in enumerate(old_pages, 1)}
    seen = set()
    page = base
    while True:
        prev_archive = page.get_link('prev-archive')
        if not prev_archive:
            break

        if prev_archive in seen:
            #progress.warn("cycle in archive links at {}".format(prev_archive))
            break

        seen.add(prev_archive)

        keep_existing = existing_pages.get(prev_archive, 0)
        if keep_existing:
            break

        page = FeedDocument(http, prev_archive, headers={
            # archive documents should always be taken from the cache
            "Cache-Control": "max-stale",
            "Referer": page.url,
        })
        new_pages.append(page.as_archive_page())

    if keep_existing or new_pages:
        # found some RFC5005 archives
        new_pages.reverse()
        # base is the newest FeedArchivePage
        new_pages.append(base.as_archive_page())

    return keep_existing
