import pytest
from xml.sax.saxutils import quoteattr


@pytest.fixture
def mock_atom_feed(httpx_mock):
    def make(
        url,
        *,
        links={},
        complete=False,
        archive=False,
        entries=[],
    ):
        data = [
            '<feed xmlns="http://www.w3.org/2005/Atom">' "<id>urn:example:feed-id</id>"
        ]

        data.extend(
            f"<link href={quoteattr(href)} rel={quoteattr(rel)}/>"
            for rel, href in {"self": url, **links}.items()
        )

        if complete:
            data.extend(
                '<fh:complete xmlns:fh="http://purl.org/syndication/history/1.0"/>'
            )
        if archive:
            data.extend(
                '<fh:archive xmlns:fh="http://purl.org/syndication/history/1.0"/>'
            )

        data.extend(
            "<entry>"
            f"<id>urn:example:post-{entry}</id>"
            f"<title>post #{entry}</title>"
            f"<published>2020-01-{entry:02}T00:00:00Z</published>"
            "</entry>"
            for entry in entries
        )

        data.append("</feed>")
        httpx_mock.add_response(url=url, data="".join(data))

    return make


def pytest_collection_modifyitems(items):
    "Don't type-check source files which only contain tests."

    from pytest_mypy import MypyFileItem

    def is_not_mypy_testfile_item(item):
        return not (
            isinstance(item, MypyFileItem) and item.fspath.basename.startswith("test_")
        )

    filter_in_place(is_not_mypy_testfile_item, items)


def filter_in_place(pred, items):
    """
    Like list(filter(pred, items)) but modifies the original list instead of
    returning a new one.
    """

    dst = src = 0
    while src < len(items):
        item = items[src]
        if pred(item):
            items[dst] = item
            dst += 1
        src += 1
    del items[dst:]
