import asyncio
import re

import pytest

from browser_session import BrowserError
from errors import NotLoggedInError
from linkedin import sections
from linkedin.sections import Layout, SectionSpec

EXPERIENCE = "Experience\n\nCo-founder\n\nMicrosoft\n\n1975 – Present"
MICROSOFT = {"href": "https://www.linkedin.com/company/1035/", "text": "Co-founder Microsoft 1975 – Present"}


class _FakePage:
    """Records what the reader does; each read of the content script returns the next queued page."""

    def __init__(self, contents, show_more_clicks=0, logged_out=False, fail_on=None):
        self.contents = list(contents)
        self.show_more_left = show_more_clicks
        self.logged_out = logged_out
        self.fail_on = fail_on
        self.visited, self.clicks, self.scrolls, self.read_roots = [], [], [], []
        self.url = ""

    async def goto(self, url):
        if url == self.fail_on:
            raise BrowserError("Timeout 30000ms exceeded")
        self.visited.append(url)
        self.url = url

    async def wait_until(self, condition, timeout_ms):
        return True

    async def click_first(self, selector, text_pattern=None, timeout_ms=2_000):
        if text_pattern is not None and self.show_more_left:
            self.show_more_left -= 1
            self.clicks.append("show more")
            return True
        return False

    async def auto_scroll(self, times, delay_ms):
        self.scrolls.append((times, delay_ms))

    async def run_script(self, name, argument=None):
        if name == "linkedin_auth_probe":
            return self.logged_out
        self.read_roots.append(argument["selectors"])
        return self.contents.pop(0)


@pytest.fixture(autouse=True)
def no_pauses(monkeypatch):
    async def no_sleep(seconds):
        pass

    monkeypatch.setattr(sections.asyncio, "sleep", no_sleep)


def _content(text, references=(), source="root"):
    return {"source": source, "text": text, "references": list(references)}


@pytest.mark.asyncio
async def test_detail_section_is_expanded_scrolled_and_read_with_its_links():
    page = _FakePage([_content(EXPERIENCE + "\n\nMore profiles for you\n\nSundar Pichai", [MICROSOFT])], show_more_clicks=2)

    section = await sections.read_section(page, SectionSpec("experience", "https://x/details/experience/", Layout.DETAILS))

    assert page.visited == ["https://x/details/experience/"]
    assert page.clicks == ["show more", "show more"]
    assert page.scrolls == [(5, 500)]
    assert section.text == EXPERIENCE
    assert [reference["url"] for reference in section.references] == ["/company/1035/"]
    assert section.error is None


@pytest.mark.asyncio
async def test_show_more_clicks_stop_at_the_limit():
    page = _FakePage([_content(EXPERIENCE)], show_more_clicks=50)

    await sections.read_section(page, SectionSpec("experience", "https://x/", Layout.DETAILS, max_loads=3))

    assert len(page.clicks) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("layout", "max_loads", "scrolls"),
    [(Layout.ACTIVITY, None, (10, 1_000)), (Layout.SEARCH, 15, (15, 500)), (Layout.STANDARD, None, (5, 500))],
)
async def test_each_layout_scrolls_its_own_amount(layout, max_loads, scrolls):
    page = _FakePage([_content("Posts\n\nSome post")])

    await sections.read_section(page, SectionSpec("posts", "https://x/", layout, max_loads=max_loads))

    assert page.scrolls == [scrolls]
    assert page.clicks == []


@pytest.mark.asyncio
async def test_page_with_only_chrome_is_retried_once_then_reported_as_rate_limited():
    chrome_only = _content("More profiles for you\n\nSomeone")
    page = _FakePage([chrome_only, chrome_only])

    section = await sections.read_section(page, SectionSpec("skills", "https://x/", Layout.DETAILS))

    assert len(page.visited) == 2
    assert section.text == ""
    assert "rate-limit" in section.error


@pytest.mark.asyncio
async def test_retry_that_works_returns_the_content():
    page = _FakePage([_content("More profiles for you"), _content("Skills\n\nPython")])

    section = await sections.read_section(page, SectionSpec("skills", "https://x/", Layout.DETAILS))

    assert section.text == "Skills\n\nPython"
    assert section.error is None


@pytest.mark.asyncio
async def test_empty_section_is_not_an_error():
    page = _FakePage([_content("   ")])

    section = await sections.read_section(page, SectionSpec("honors", "https://x/", Layout.DETAILS))

    assert (section.text, section.references, section.error) == ("", [], None)


@pytest.mark.asyncio
async def test_overlay_is_read_from_the_dialog_only():
    page = _FakePage([_content("Contact info\n\nEmail\n\njane@example.com")])

    section = await sections.read_section(page, SectionSpec("contact_info", "https://x/overlay/contact-info/", Layout.OVERLAY))

    assert page.read_roots == [["dialog[open]", ".artdeco-modal__content"]]
    assert page.scrolls == []
    assert section.text == "Contact info\n\nEmail\n\njane@example.com"


@pytest.mark.asyncio
async def test_overlay_that_did_not_open_is_an_error_not_page_text():
    page = _FakePage([_content("Whole profile page text", source="body")])

    section = await sections.read_section(page, SectionSpec("contact_info", "https://x/", Layout.OVERLAY))

    assert section.text == ""
    assert "did not open" in section.error


@pytest.mark.asyncio
async def test_login_wall_stops_the_read():
    page = _FakePage([], logged_out=True)

    with pytest.raises(NotLoggedInError):
        await sections.read_section(page, SectionSpec("experience", "https://x/", Layout.DETAILS))


@pytest.mark.asyncio
async def test_several_sections_are_read_in_order_with_per_section_errors():
    page = _FakePage([_content(EXPERIENCE, [MICROSOFT]), _content("Skills\n\nPython")], fail_on="https://x/education/")
    specs = [
        SectionSpec("experience", "https://x/experience/", Layout.DETAILS),
        SectionSpec("education", "https://x/education/", Layout.DETAILS),
        SectionSpec("skills", "https://x/skills/", Layout.DETAILS),
    ]

    result = sections.section_result("https://x/", await sections.read_sections(page, specs))

    assert result["url"] == "https://x/"
    assert result["sections"] == {"experience": EXPERIENCE, "skills": "Skills\n\nPython"}
    assert list(result["references"]) == ["experience"]
    assert list(result["section_errors"]) == ["education"]
    assert "Timeout 30000ms exceeded" in result["section_errors"]["education"]


@pytest.mark.asyncio
async def test_reading_stops_after_a_rate_limited_section():
    chrome_only = _content("More profiles for you")
    page = _FakePage([chrome_only, chrome_only])
    specs = [
        SectionSpec("skills", "https://x/skills/", Layout.DETAILS),
        SectionSpec("projects", "https://x/projects/", Layout.DETAILS),
    ]

    results = await sections.read_sections(page, specs)

    assert "https://x/projects/" not in page.visited
    assert results["skills"].error == sections.RATE_LIMITED
    assert results["projects"].error == sections.SKIPPED_AFTER_RATE_LIMIT


def test_result_without_links_or_errors_has_only_url_and_sections():
    results = {"main_profile": sections.SectionText("Jane"), "skills": sections.SectionText("")}

    assert sections.section_result("https://x/", results) == {"url": "https://x/", "sections": {"main_profile": "Jane"}}


@pytest.mark.asyncio
async def test_pause_before_the_first_section_only_when_another_page_was_just_loaded(monkeypatch):
    pauses = []

    async def record_sleep(seconds):
        pauses.append(seconds)

    monkeypatch.setattr(sections.asyncio, "sleep", record_sleep)
    specs = [
        SectionSpec("skills", "https://x/skills/", Layout.STANDARD),
        SectionSpec("projects", "https://x/projects/", Layout.STANDARD),
    ]

    await sections.read_sections(_FakePage([_content("Skills"), _content("Projects")]), specs)
    assert pauses == [sections.SECTION_PAUSE_SECONDS]

    pauses.clear()
    await sections.read_sections(_FakePage([_content("Skills"), _content("Projects")]), specs, after_other_page=True)
    assert pauses == [sections.SECTION_PAUSE_SECONDS] * 2


# Taken from a live williamhgates profile read (2026-11-04).
PROFILE_TOP = """Bill Gates

Chair, Gates Foundation and Founder, Breakthrough Energy

Seattle, Washington, United States

40,785,845 followers

Profile enhanced with Premium

Sales Insights

Key signals

Bill posted in the past 30 days

Try Sales Navigator for ₹0

1-month free trial with 24/7 support. Easy to cancel. We’ll remind you 7 days before your trial ends.

About

Chair of the Gates Foundation. Founder of Breakthrough Energy."""


def test_premium_and_sales_navigator_upsell_is_removed_and_profile_text_kept():
    cleaned = sections.strip_clutter(PROFILE_TOP)

    for upsell in ("Premium", "Sales Insights", "Key signals", "posted in the past 30 days", "Sales Navigator", "free trial"):
        assert upsell not in cleaned
    kept_lines = (
        "Bill Gates",
        "Chair, Gates Foundation",
        "Seattle, Washington",
        "40,785,845 followers",
        "About",
        "Breakthrough Energy.",
    )
    for kept in kept_lines:
        assert kept in cleaned


@pytest.mark.parametrize(
    "marker",
    [
        "About\nAccessibility",
        "About\n\nTalent Solutions",
        "More profiles for you",
        "Explore premium profiles",
        "Careers\nPrivacy & Terms",
        "Are these results helpful?",
    ],
)
def test_everything_from_the_sidebar_or_footer_on_is_cut(marker):
    cleaned = sections.strip_clutter(f"Experience\n\nFounder\n\n{marker}\n\nSomeone else entirely")

    assert cleaned == "Experience\n\nFounder"


@pytest.mark.parametrize(
    "line",
    [
        "Play",
        "Playback speed",
        "Loaded: 12%",
        "Try Premium for ₹0",
        "Activate Premium for ₹0",
        "Access exclusive tools & insights",
        "Do you find this post valuable?",
    ],
)
def test_single_clutter_lines_are_removed(line):
    assert sections.strip_clutter(f"Post text\n{line}\nMore post text") == "Post text\nMore post text"


def test_words_inside_real_text_are_kept():
    text = "About\n\nI help teams try Premium products. Key signals of growth matter."

    assert sections.strip_clutter(text) == text


def test_empty_text_stays_empty():
    assert sections.strip_clutter("") == ""


# From a live williamhgates main profile read (2026-11-04), shortened.
MAIN_PROFILE = """Bill Gates

Chair, Gates Foundation and Founder, Breakthrough Energy

People who follow Bill also follow

Virat Kohli

Professional Athlete at Indian Cricket Team

455,651 followers

Follow

About

Chair of the Gates Foundation.

Activity

40,786,142 followers

Follow
Posts

Bill Gates

Useful advice for farmers."""
VIRAT = {"href": "https://www.linkedin.com/in/virat-kohli18/", "text": "Virat Kohli Professional Athlete at Indian Cricket Team"}


def test_people_also_follow_box_is_removed_with_its_links():
    page = _FakePage([_content(MAIN_PROFILE, [VIRAT])])

    section = await_section(page, SectionSpec("main_profile", "https://x/", Layout.STANDARD))

    assert "also follow" not in section.text and "Virat Kohli" not in section.text
    assert "About\n\nChair of the Gates Foundation." in section.text
    assert section.references == []


def test_people_also_follow_box_at_the_end_of_the_text_is_removed():
    assert sections.strip_clutter("Jane Doe\n\nPeople who follow Jane also follow\n\nSomeone\n\nFollow") == "Jane Doe"


def test_section_end_markers_cut_only_that_section():
    page = _FakePage([_content(MAIN_PROFILE)])
    spec = SectionSpec("main_profile", "https://x/", Layout.STANDARD, end_markers=(re.compile(r"^Activity$", re.MULTILINE),))

    section = await_section(page, spec)

    assert section.text.endswith("Chair of the Gates Foundation.")
    assert "Useful advice for farmers." not in section.text
    assert "Useful advice for farmers." in sections.strip_clutter(MAIN_PROFILE)


def test_page_whose_content_starts_at_an_end_marker_is_empty_not_rate_limited():
    page = _FakePage([_content("Activity\n\nposts")])
    spec = SectionSpec("main_profile", "https://x/", Layout.STANDARD, end_markers=(re.compile(r"^Activity$", re.MULTILINE),))

    section = await_section(page, spec)

    assert (section.text, section.error) == ("", None)


def await_section(page, spec):
    return asyncio.run(sections.read_section(page, spec))
