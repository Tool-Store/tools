from contextlib import asynccontextmanager

import pytest

from errors import PageReadError
from linkedin import company as linkedin_company
from linkedin import sections
from linkedin.sections import Layout, SectionText


class _Reader:
    def __init__(self, landed_url):
        self.landed_url = landed_url
        self.read = []
        self.url = ""

    async def read_section(self, page, spec):
        self.main_spec = spec
        self.read.append((spec.name, spec.url, spec.layout))
        page.url = self.landed_url
        return SectionText("Microsoft\n\nSoftware Development\n\nRedmond, Washington")

    async def read_sections(self, page, specs, after_other_page=False):
        self.read.extend((spec.name, spec.url, spec.layout) for spec in specs)
        return {spec.name: SectionText(f"{spec.name} text") for spec in specs}


@pytest.fixture
def reader(monkeypatch):
    def install(landed_url):
        fake = _Reader(landed_url)

        @asynccontextmanager
        async def fake_user_page(user_id, site):
            yield fake

        monkeypatch.setattr(linkedin_company.browser_session, "user_page", fake_user_page)
        monkeypatch.setattr(sections, "read_section", fake.read_section)
        monkeypatch.setattr(sections, "read_sections", fake.read_sections)
        return fake

    return install


@pytest.mark.asyncio
async def test_about_page_then_requested_sections_under_the_name_linkedin_redirected_to(reader):
    fake = reader("https://www.linkedin.com/company/microsoft/about/")

    result = await linkedin_company.read_company("user-1", "1035", ["posts", "jobs"])

    assert fake.read == [
        ("about", "https://www.linkedin.com/company/1035/about/", Layout.STANDARD),
        ("posts", "https://www.linkedin.com/company/microsoft/posts/", Layout.ACTIVITY),
        ("jobs", "https://www.linkedin.com/company/microsoft/jobs/", Layout.STANDARD),
    ]
    assert result["url"] == "https://www.linkedin.com/company/microsoft/"
    assert list(result["sections"]) == ["about", "posts", "jobs"]


@pytest.mark.asyncio
@pytest.mark.parametrize("landed_on", ["https://www.linkedin.com/404/", "https://www.linkedin.com/feed/"])
async def test_unknown_company_is_reported_and_no_more_pages_are_loaded(reader, landed_on):
    fake = reader(landed_on)

    with pytest.raises(PageReadError, match="LinkedIn has no company page 'no-such-co'"):
        await linkedin_company.read_company("user-1", "no-such-co", ["posts"])
    assert len(fake.read) == 1


def test_every_offered_section_has_a_page():
    from constants import LINKEDIN_COMPANY_SECTIONS

    assert set(linkedin_company.SECTION_PAGES) == set(LINKEDIN_COMPANY_SECTIONS)


@pytest.mark.parametrize(
    ("page_text", "kept"),
    [
        (
            "Overview\n\nDetails\nWebsite\nhttps://news.microsoft.com/\n\n"
            "Interested in working with us in the future?\n\nPrivately share",
         "Overview\n\nDetails\nWebsite\nhttps://news.microsoft.com/"),
        ("Overview\n\nDetails\nIndustry\nSoftware\nCommitments\n\nFeatured\n\nEnvironmental sustainability",
         "Overview\n\nDetails\nIndustry\nSoftware"),
        ("Overview\n\nDetails\nHeadquarters\nRedmond\nLocations (45)\nInteract with the map",
         "Overview\n\nDetails\nHeadquarters\nRedmond"),
    ],
)
@pytest.mark.asyncio
async def test_about_page_ends_before_recruiting_commitments_and_locations(reader, page_text, kept):
    fake = reader("https://www.linkedin.com/company/microsoft/about/")

    await linkedin_company.read_company("user-1", "microsoft", [])

    starts = [match.start() for marker in fake.main_spec.end_markers if (match := marker.search(page_text))]
    assert page_text[: min(starts)].strip() == kept
