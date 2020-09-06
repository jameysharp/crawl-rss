from typing import List, Optional, Set, Text

from .common import crawler_registry, FeedDocument, FeedType, UpdateFeedHistory
from .models import FeedArchivePage


@crawler_registry
def from_rfc5005(
    base: FeedDocument,
    old_pages: List[FeedArchivePage],
) -> Optional[UpdateFeedHistory]:
    if base.feed_type == FeedType.COMPLETE:
        # feed gets one FeedArchivePage containing all of base's FeedPageEntries
        return UpdateFeedHistory(0, [base.as_archive_page()])

    # walk backwards until we hit an existing FeedArchivePage
    existing_pages = {page.url: keep for keep, page in enumerate(old_pages, 1)}
    seen: Set[Text] = set()
    keep_existing = 0
    new_pages = []
    page = base
    while True:
        prev_archive = page.get_link("prev-archive")
        if not prev_archive:
            break

        if prev_archive in seen:
            break

        seen.add(prev_archive)

        keep_existing = existing_pages.get(prev_archive, 0)
        if keep_existing:
            break

        page = page.follow(
            prev_archive,
            headers={
                # archive documents should always be taken from the cache
                "Cache-Control": "max-stale",
                "Referer": page.url,
            },
        )
        new_pages.append(page.as_archive_page())

    if not keep_existing and not new_pages:
        return None

    # found some RFC5005 archives
    new_pages.reverse()
    # base is the newest FeedArchivePage
    new_pages.append(base.as_archive_page())
    return UpdateFeedHistory(keep_existing, new_pages)
