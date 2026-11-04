from contextlib import asynccontextmanager

import pytest

from linkedin import posts as linkedin_posts
from linkedin import sections
from linkedin.sections import Layout, SectionText


@pytest.fixture
def read(monkeypatch):
    calls = []

    @asynccontextmanager
    async def fake_user_page(user_id, site):
        calls.append(("opened", user_id, site))
        yield "page"

    async def fake_read_sections(page, specs, after_other_page=False):
        calls.extend(("read", spec.name, spec.url, spec.layout, spec.max_loads) for spec in specs)
        return {"search_results": SectionText("Feed post\n\nAI is changing marketing")}

    monkeypatch.setattr(linkedin_posts.browser_session, "user_page", fake_user_page)
    monkeypatch.setattr(sections, "read_sections", fake_read_sections)
    return calls


@pytest.mark.asyncio
async def test_search_reads_the_results_page_scrolling_per_requested_page(read):
    result = await linkedin_posts.search_posts("user-1", "AI marketing", None, None, pages=2)

    url = "https://www.linkedin.com/search/results/content/?keywords=AI+marketing&origin=FACETED_SEARCH"
    assert read == [("opened", "user-1", "linkedin"), ("read", "search_results", url, Layout.SEARCH, 10)]
    assert result == {"url": url, "sections": {"search_results": "Feed post\n\nAI is changing marketing"}}


@pytest.mark.parametrize(
    ("date_posted", "content_type", "filters"),
    [
        ("past-week", None, "&datePosted=%5B%22past-week%22%5D"),
        (None, "images", "&contentType=%5B%22photos%22%5D"),
        ("past-24h", "documents", "&datePosted=%5B%22past-24h%22%5D&contentType=%5B%22documents%22%5D"),
    ],
)
def test_filters_use_linkedins_own_tokens(date_posted, content_type, filters):
    url = linkedin_posts.search_url("AI & ML", date_posted, content_type)

    assert url == "https://www.linkedin.com/search/results/content/?keywords=AI+%26+ML&origin=FACETED_SEARCH" + filters
