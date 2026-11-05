import pytest

import validators
from constants import LOGIN_SITES, MAX_QUERY_CHARS, MAX_RESULT_LIMIT, SEARCH_SITES


def test_site_is_normalized():
    assert validators.validate_site(" LinkedIn ", LOGIN_SITES) == "linkedin"


@pytest.mark.parametrize(("site", "supported"), [("", LOGIN_SITES), ("tiktok", LOGIN_SITES), ("linkedin", SEARCH_SITES)])
def test_unsupported_site_is_rejected(site, supported):
    with pytest.raises(ValueError, match="Unsupported site"):
        validators.validate_site(site, supported)


def test_query_whitespace_is_collapsed():
    assert validators.validate_query("  python   developer ") == "python developer"


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("", "query is required"),
        ("   ", "query is required"),
        ("x" * (MAX_QUERY_CHARS + 1), "at most"),
        ("--help", "must not start"),
    ],
    ids=["empty", "blank", "too-long", "option-like"],
)
def test_invalid_query_is_rejected(query, message):
    with pytest.raises(ValueError, match=message):
        validators.validate_query(query)


def test_location_is_cleaned_and_checked_like_query():
    assert validators.validate_location(" New   York ") == "New York"
    with pytest.raises(ValueError, match="location must not start with '-'"):
        validators.validate_location("-x")


def test_username_at_sign_is_removed():
    assert validators.validate_username(" @natgeo ") == "natgeo"


@pytest.mark.parametrize("username", ["nat-geo", "_private", "a", "a" * 100])
def test_valid_usernames_are_accepted(username):
    assert validators.validate_username(username) == username


@pytest.mark.parametrize("username", ["", "@", "https://x.com/natgeo", "nat geo", "a" * 101, "--help", "-v", "@--limit"])
def test_invalid_username_is_rejected(username):
    with pytest.raises(ValueError, match="Invalid username"):
        validators.validate_username(username)


@pytest.mark.parametrize("limit", [1, MAX_RESULT_LIMIT])
def test_limit_bounds_are_accepted(limit):
    assert validators.validate_limit(limit) == limit


@pytest.mark.parametrize("limit", [0, MAX_RESULT_LIMIT + 1, -5])
def test_out_of_range_limit_is_rejected(limit):
    with pytest.raises(ValueError, match="limit must be between"):
        validators.validate_limit(limit)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/jobs/view/4482478523",
        "https://in.linkedin.com/jobs/view/lead-python-engineer-4482478523/",
    ],
)
def test_linkedin_job_url_is_accepted(url):
    assert validators.validate_linkedin_job_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://www.linkedin.com/jobs/view/4482478523",
        "https://www.linkedin.com/in/someone",
        "https://evil-linkedin.com/jobs/view/4482478523",
        "https://example.com/jobs/view/4482478523",
    ],
    ids=["empty", "not-https", "profile-path", "lookalike-host", "other-host"],
)
def test_invalid_linkedin_job_url_is_rejected(url):
    with pytest.raises(ValueError, match="Invalid LinkedIn job URL"):
        validators.validate_linkedin_job_url(url)


@pytest.mark.parametrize(
    "tweet",
    ["1234567890", "https://x.com/OpenAI/status/1234567890", "https://mobile.twitter.com/OpenAI/status/1234567890/"],
)
def test_tweet_id_or_link_is_accepted(tweet):
    assert validators.validate_tweet(tweet) == tweet


@pytest.mark.parametrize(
    "tweet",
    ["", "abc", "https://x.com/OpenAI", "https://notx.com/OpenAI/status/1234567890", "http://x.com/OpenAI/status/1"],
    ids=["empty", "not-a-number", "profile-link", "lookalike-host", "not-https"],
)
def test_invalid_tweet_is_rejected(tweet):
    with pytest.raises(ValueError, match="Invalid tweet"):
        validators.validate_tweet(tweet)


def test_positive_int_setting_reads_the_environment(monkeypatch):
    monkeypatch.setenv("SOME_SETTING", "7")
    assert validators.positive_int_setting("SOME_SETTING", 3) == 7


def test_positive_int_setting_uses_the_default_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_SETTING", raising=False)
    assert validators.positive_int_setting("SOME_SETTING", 3) == 3


@pytest.mark.parametrize("raw", ["0", "-1", "many", ""])
def test_positive_int_setting_rejects_bad_values(monkeypatch, raw):
    monkeypatch.setenv("SOME_SETTING", raw)
    with pytest.raises(ValueError, match="SOME_SETTING must be a whole number of at least 1"):
        validators.positive_int_setting("SOME_SETTING", 3)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.linkedin.com/in/jane-doe/", "https://www.linkedin.com/in/jane-doe/"),
        ("https://in.linkedin.com/in/jane-doe", "https://www.linkedin.com/in/jane-doe/"),
        ("  https://linkedin.com/in/jane-doe/?trk=x  ", "https://www.linkedin.com/in/jane-doe/"),
    ],
)
def test_linkedin_profile_url_is_normalized(url, expected):
    assert validators.validate_linkedin_profile_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://www.linkedin.com/in/jane-doe/",
        "https://evil.com/in/jane-doe/",
        "https://linkedin.com.evil.com/in/jane-doe/",
        "https://user:pass@www.linkedin.com/in/jane-doe/",
        "https://www.linkedin.com:8443/in/jane-doe/",
        "https://www.linkedin.com/company/acme/",
        "https://www.linkedin.com/in/jane-doe/details/skills/",
    ],
)
def test_invalid_linkedin_profile_url_is_rejected(url):
    with pytest.raises(ValueError, match="Invalid LinkedIn profile URL"):
        validators.validate_linkedin_profile_url(url)


def test_choices_are_cleaned_deduplicated_and_kept_in_order():
    assert validators.validate_choices([" Skills", "experience", "skills"], ("experience", "skills"), "sections", 5) == [
        "skills",
        "experience",
    ]


@pytest.mark.parametrize("values", [None, []])
def test_no_choices_means_none(values):
    assert validators.validate_choices(values, ("experience",), "sections", 5) == []


def test_unknown_choice_is_rejected_with_the_allowed_list():
    with pytest.raises(ValueError, match="Unknown sections 'hobbies'. Choose from: experience, skills"):
        validators.validate_choices(["hobbies"], ("experience", "skills"), "sections", 5)


def test_too_many_choices_are_rejected():
    with pytest.raises(ValueError, match="At most 2 sections per call"):
        validators.validate_choices(["a", "b", "c"], ("a", "b", "c"), "sections", 2)


def test_optional_choice_is_cleaned_or_rejected():
    assert validators.validate_choice(" Past-Week ", ("past-week", "past-month"), "date_posted") == "past-week"
    assert validators.validate_choice(None, ("past-week",), "date_posted") is None
    with pytest.raises(ValueError, match="Unknown date_posted 'yesterday'. Choose from: past-week"):
        validators.validate_choice("yesterday", ("past-week",), "date_posted")


@pytest.mark.parametrize(
    ("company", "slug"),
    [
        ("microsoft", "microsoft"),
        ("  Gates-Foundation ", "Gates-Foundation"),
        ("1035", "1035"),
        ("https://www.linkedin.com/company/microsoft/", "microsoft"),
        ("https://in.linkedin.com/company/microsoft/about/?trk=x", "microsoft"),
    ],
)
def test_company_is_reduced_to_its_page_name(company, slug):
    assert validators.validate_company(company) == slug


@pytest.mark.parametrize(
    "company",
    ["", "https://evil.com/company/microsoft/", "https://www.linkedin.com/in/jane-doe/", "micro soft", "-microsoft", "a/b"],
)
def test_invalid_company_is_rejected(company):
    with pytest.raises(ValueError, match="Invalid LinkedIn company"):
        validators.validate_company(company)


@pytest.mark.parametrize(("pages", "ok"), [(1, True), (3, True), (0, False), (4, False)])
def test_search_pages_are_limited(pages, ok):
    if ok:
        assert validators.validate_pages(pages) == pages
    else:
        with pytest.raises(ValueError, match="pages must be between 1 and 3"):
            validators.validate_pages(pages)


def test_limit_can_have_its_own_maximum():
    assert validators.validate_limit(12, 12) == 12
    with pytest.raises(ValueError, match="limit must be between 1 and 12, got 13"):
        validators.validate_limit(13, 12)
