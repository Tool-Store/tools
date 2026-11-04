import pytest

from linkedin.links import build_references

# Anchors as the page script reports them, from a live williamhgates experience read (2026-11-04).
EXPERIENCE_TEXT = "Experience\n\nCo-chair\n\nGates Foundation\n\n2000 – Present\n\nCo-founder\n\nMicrosoft\n\n1975 – Present"
EXPERIENCE_ANCHORS = [
    {"href": "https://www.linkedin.com/company/8736/", "text": "Co-chair Gates Foundation 2000 – Present"},
    {"href": "https://www.linkedin.com/company/1035/?trk=x", "text": "Co-founder Microsoft 1975 – Present"},
    {"href": "https://www.linkedin.com/in/sundarpichai/", "text": "Sundar Pichai"},
    {"href": "https://www.linkedin.com/in/satyanadella/", "text": "Satya Nadella"},
]


def test_people_also_viewed_links_that_are_not_in_the_section_text_are_dropped():
    references = build_references(EXPERIENCE_ANCHORS, "experience", EXPERIENCE_TEXT)

    assert references == [
        {"kind": "company", "url": "/company/8736/", "text": "Co-chair Gates Foundation 2000 – Present", "context": "experience"},
        {"kind": "company", "url": "/company/1035/", "text": "Co-founder Microsoft 1975 – Present", "context": "experience"},
    ]


@pytest.mark.parametrize(
    ("href", "kind", "url"),
    [
        ("https://www.linkedin.com/in/jane-doe/", "person", "/in/jane-doe/"),
        ("https://www.linkedin.com/school/1646/", "school", "/school/1646/"),
        ("https://www.linkedin.com/jobs/view/senior-engineer-at-acme-4252026496/", "job", "/jobs/view/4252026496/"),
        ("https://www.linkedin.com/feed/update/urn:li:activity:749827/", "feed_post", "/feed/update/urn:li:activity:749827/"),
        ("https://www.linkedin.com/posts/someone_topic-activity-123-AbCd", "feed_post", "/posts/someone_topic-activity-123-AbCd"),
        ("https://www.linkedin.com/pulse/my-article-jane-doe/", "article", "/pulse/my-article-jane-doe/"),
        ("https://www.linkedin.com/newsletters/ai-weekly-123/", "newsletter", "/newsletters/ai-weekly-123/"),
        ("https://www.linkedin.com/redir/redirect/?url=https%3A%2F%2Fgatesnot.es%2FAI%3Futm%3D1", "external", "https://gatesnot.es/AI"),
    ],
)
def test_links_are_classified_and_shortened(href, kind, url):
    [reference] = build_references([{"href": href, "text": "Jane Doe"}], "main_profile", "Jane Doe")

    assert (reference["kind"], reference["url"]) == (kind, url)


@pytest.mark.parametrize(
    "anchor",
    [
        {"href": "https://www.linkedin.com/in/jane-doe/", "text": "Jane Doe", "in_nav": True},
        {"href": "https://www.linkedin.com/in/jane-doe/", "text": "Jane Doe", "in_footer": True},
        {"href": "https://www.linkedin.com/help/linkedin/", "text": "Help"},
        {"href": "https://www.linkedin.com/search/results/people/?keywords=x", "text": "Jane Doe"},
        {"href": "https://www.linkedin.com/in/jane-doe/details/skills/", "text": "Jane Doe"},
        {"href": "#top", "text": "Jane Doe"},
        {"href": "javascript:void(0)", "text": "Jane Doe"},
        {"href": "mailto:jane@example.com", "text": "Jane Doe"},
        {"href": "https://www.linkedin.com/in/jane-doe/", "text": "Follow"},
    ],
)
def test_navigation_footer_chrome_and_unlabelled_people_are_dropped(anchor):
    assert build_references([anchor], "main_profile", "Jane Doe") == []


def test_duplicate_links_keep_the_richer_label_in_first_position():
    anchors = [
        {"href": "https://www.linkedin.com/company/acme/", "aria_label": "Acme"},
        {"href": "https://www.linkedin.com/in/jane-doe/", "text": "Jane Doe"},
        {"href": "https://www.linkedin.com/company/acme/about/", "text": "Acme Corporation"},
    ]

    references = build_references(anchors, "main_profile", "Acme Corporation, Jane Doe")

    assert [reference["url"] for reference in references] == ["/company/acme/", "/in/jane-doe/"]
    assert references[0]["text"] == "Acme Corporation"


def test_labels_are_cleaned():
    anchors = [{"href": "https://www.linkedin.com/in/jane-doe/", "text": "View: Jane Doe • 2nd"}]

    [reference] = build_references(anchors, "search_results", "Jane Doe")

    assert reference["text"] == "Jane Doe"


def test_post_links_are_kept_without_a_label():
    anchors = [{"href": "https://www.linkedin.com/feed/update/urn:li:activity:1/", "text": ""}]

    assert build_references(anchors, "posts", "") == [
        {"kind": "feed_post", "url": "/feed/update/urn:li:activity:1/", "context": "posts"}
    ]


def test_each_section_keeps_at_most_its_cap():
    anchors = [{"href": f"https://www.linkedin.com/feed/update/urn:li:activity:{n}/"} for n in range(40)]

    assert len(build_references(anchors, "experience", "")) == 12
    assert len(build_references(anchors, "search_results", "")) == 15


def test_counts_are_not_used_as_labels():
    # From a live profile read: the comment-count link of a post was labelled "261".
    anchors = [{"href": "https://www.linkedin.com/feed/update/urn:li:activity:7522801130767224832/", "text": "261"}]

    [reference] = build_references(anchors, "main_profile", "261 comments")

    assert "text" not in reference


def test_external_links_whose_label_is_not_in_the_section_text_are_dropped():
    # From a live company read: pledge links from the part of the About page that is cut off.
    anchors = [
        {"href": "https://blogs.microsoft.com/blog/2020/01/16/carbon/", "text": "Carbon Negative Pledge blogs.microsoft.com"},
        {"href": "https://news.microsoft.com/", "text": "news.microsoft.com"},
        {"href": "https://news.microsoft.com/", "text": ""},
    ]

    references = build_references(anchors, "about", "Website\nhttps://news.microsoft.com/")

    assert references == [
        {"kind": "external", "url": "https://news.microsoft.com/", "text": "news.microsoft.com", "context": "about"}
    ]


def test_unlabelled_outside_links_are_kept_only_when_their_address_is_in_the_text():
    # From a live company read (2026-11-04): unlabelled links from the cut-off part of the About page.
    anchors = [
        {"href": "https://news.microsoft.com/"},
        {"href": "https://hbr.org/2022/06/why-microsoft-measures-employee-thriving-not-engagement"},
        {"href": "https://www.microsoft.com/en-us/leap/"},
        {"href": "https://gatesnot.es/AI"},
    ]

    references = build_references(anchors, "about", "Website\nhttps://news.microsoft.com/\nNotes https://gatesnot.es/AI")

    assert [reference["url"] for reference in references] == ["https://news.microsoft.com/", "https://gatesnot.es/AI"]
