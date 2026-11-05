from contextlib import asynccontextmanager

import pytest

from caller import Caller
from errors import PageReadError
from linkedin import profile as linkedin_profile
from linkedin import sections
from linkedin.sections import Layout, SectionText

USER = Caller("user-1")


MAIN_TEXT = SectionText("Bill Gates\n\nChair, Gates Foundation")


class _Reader:
    """Stands in for the section reader: records what was read, answers with fixed text."""

    def __init__(self, landed_url, main=MAIN_TEXT):
        self.landed_url = landed_url
        self.main = main
        self.read = []
        self.url = ""

    async def read_section(self, page, spec):
        self.main_spec = spec
        self.read.append((spec.name, spec.url, spec.layout))
        page.url = self.landed_url
        return self.main

    async def read_sections(self, page, specs, after_other_page=False):
        assert after_other_page is True
        self.read.extend((spec.name, spec.url, spec.layout) for spec in specs)
        return {spec.name: SectionText(f"{spec.name} text") for spec in specs}


@pytest.fixture
def reader(monkeypatch):
    def install(landed_url, **kwargs):
        fake = _Reader(landed_url, **kwargs)
        opened = []

        @asynccontextmanager
        async def fake_user_page(user_id, site):
            opened.append((user_id, site))
            yield fake

        monkeypatch.setattr(linkedin_profile.browser_session, "user_page", fake_user_page)
        monkeypatch.setattr(sections, "read_section", fake.read_section)
        monkeypatch.setattr(sections, "read_sections", fake.read_sections)
        fake.opened = opened
        return fake

    return install


@pytest.mark.asyncio
async def test_main_page_then_each_requested_section_page_is_read(reader):
    fake = reader("https://www.linkedin.com/in/williamhgates/")

    gates = "https://www.linkedin.com/in/williamhgates/"
    result = await linkedin_profile.read_profile(USER, gates, ["experience", "posts", "contact_info"])

    assert fake.opened == [(USER, "linkedin")]
    assert fake.read == [
        ("main_profile", "https://www.linkedin.com/in/williamhgates/", Layout.STANDARD),
        ("experience", "https://www.linkedin.com/in/williamhgates/details/experience/", Layout.DETAILS),
        ("posts", "https://www.linkedin.com/in/williamhgates/recent-activity/all/", Layout.ACTIVITY),
        ("contact_info", "https://www.linkedin.com/in/williamhgates/overlay/contact-info/", Layout.OVERLAY),
    ]
    assert result == {
        "url": "https://www.linkedin.com/in/williamhgates/",
        "sections": {
            "main_profile": "Bill Gates\n\nChair, Gates Foundation",
            "experience": "experience text",
            "posts": "posts text",
            "contact_info": "contact_info text",
        },
    }


@pytest.mark.asyncio
async def test_own_profile_sections_use_the_handle_linkedin_redirected_to(reader):
    fake = reader("https://www.linkedin.com/in/adity-v-30a8a3448/?miniProfileUrn=x")

    result = await linkedin_profile.read_profile(USER, None, ["skills"])

    assert fake.read[0][1] == "https://www.linkedin.com/in/me/"
    assert fake.read[1][1] == "https://www.linkedin.com/in/adity-v-30a8a3448/details/skills/"
    assert result["url"] == "https://www.linkedin.com/in/adity-v-30a8a3448/"


@pytest.mark.asyncio
@pytest.mark.parametrize("landed_on", ["https://www.linkedin.com/404/", "https://www.linkedin.com/feed/"])
async def test_page_that_is_not_a_profile_is_reported_and_no_more_pages_are_loaded(reader, landed_on):
    fake = reader(landed_on)

    with pytest.raises(PageReadError, match="LinkedIn has no profile at https://www.linkedin.com/in/no-one/"):
        await linkedin_profile.read_profile(USER, "https://www.linkedin.com/in/no-one/", ["experience"])
    assert len(fake.read) == 1


@pytest.mark.asyncio
async def test_rate_limited_main_page_skips_the_other_sections(reader):
    fake = reader("https://www.linkedin.com/in/williamhgates/", main=SectionText("", error=sections.RATE_LIMITED))

    result = await linkedin_profile.read_profile(USER, "https://www.linkedin.com/in/williamhgates/", ["experience"])

    assert len(fake.read) == 1
    assert result["section_errors"] == {"main_profile": sections.RATE_LIMITED, "experience": sections.SKIPPED_AFTER_RATE_LIMIT}


def test_every_offered_section_has_a_page():
    from constants import LINKEDIN_PROFILE_SECTIONS

    assert set(linkedin_profile.SECTION_PAGES) == set(LINKEDIN_PROFILE_SECTIONS)


@pytest.mark.asyncio
async def test_main_page_ends_where_the_activity_feed_starts(reader):
    fake = reader("https://www.linkedin.com/in/williamhgates/")

    await linkedin_profile.read_profile(USER, "https://www.linkedin.com/in/williamhgates/", [])

    page_text = "About\n\nChair.\n\nActivity\n\n40,786,142 followers\n\nFollow\nPosts\n\nBill Gates\n\nUseful advice"
    [marker] = fake.main_spec.end_markers
    assert page_text[: marker.search(page_text).start()].strip() == "About\n\nChair."
    assert marker.search("Activity\n\n0 followers")
    assert not marker.search("About\n\nActivity is my favourite word")
