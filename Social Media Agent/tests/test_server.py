import asyncio
import json
import time

import pytest

import server as server_module
from constants import LOCAL_USER_ID_ENV, MCP_ALLOWED_HOSTS_ENV
from errors import AgentReachError, CommandError

EXPECTED_TOOLS = {
    "start_login",
    "search_linkedin_jobs",
    "read_linkedin_job",
    "search_social",
    "get_social_profile",
    "get_social_posts",
    "get_x_thread",
    "get_linkedin_profile",
    "get_linkedin_company",
    "search_linkedin_posts",
    "get_instagram_profile",
    "get_instagram_posts",
}


@pytest.fixture
def mcp_server(monkeypatch):
    monkeypatch.setattr(server_module, "load_dotenv", lambda: None)
    monkeypatch.setenv(LOCAL_USER_ID_ENV, "user-1")
    monkeypatch.delenv(MCP_ALLOWED_HOSTS_ENV, raising=False)
    return server_module.create_server()


@pytest.fixture
def recorded(monkeypatch):
    """Replace the request counter and Agent Reach with recorders."""
    calls = {"counted": [], "actions": []}

    def count_request(caller, site, page_loads=1):
        calls["counted"].append((caller.user_id, site, page_loads))
        return 7

    def run_action(site, action, arguments, options=None):
        calls["actions"].append((site, action, arguments, options))
        return [{"title": "Lead Python Engineer"}]

    monkeypatch.setattr(server_module.sessions, "count_request", count_request)
    monkeypatch.setattr(server_module.agent_reach, "run_action", run_action)
    return calls


def _call(mcp_server, name, arguments):
    result = asyncio.run(mcp_server.call_tool(name, arguments))
    content = result[0] if isinstance(result, tuple) else result
    return json.loads(content[0].text)


def test_all_tools_are_registered(mcp_server):
    tools = asyncio.run(mcp_server.list_tools())

    assert {tool.name for tool in tools} == EXPECTED_TOOLS


def test_linkedin_job_search_sends_clean_input_and_reports_usage(mcp_server, recorded):
    response = _call(mcp_server, "search_linkedin_jobs", {"query": "  python  ", "location": "Ahmedabad", "limit": 3})

    assert recorded["actions"] == [("linkedin", "jobs", ["python"], {"limit": 3, "location": "Ahmedabad"})]
    assert recorded["counted"] == [("user-1", "linkedin", 1)]
    assert response == {
        "site": "linkedin",
        "action": "jobs",
        "requests_left_today": 7,
        "count": 1,
        "items": [{"title": "Lead Python Engineer"}],
    }


def test_linkedin_job_search_without_location_omits_it(mcp_server, recorded):
    _call(mcp_server, "search_linkedin_jobs", {"query": "python"})

    assert recorded["actions"][0][3] == {"limit": 5, "location": None}


@pytest.mark.parametrize(("site", "action"), [("x", "tweets")])
def test_posts_use_each_sites_action_name(mcp_server, recorded, site, action):
    _call(mcp_server, "get_social_posts", {"site": site, "username": "@natgeo", "limit": 2})

    assert recorded["actions"] == [(site, action, ["natgeo"], {"limit": 2})]


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        ("read_linkedin_job", {"url": "https://www.linkedin.com/jobs/view/4482478523"},
         ("linkedin", "read", ["https://www.linkedin.com/jobs/view/4482478523"], None)),
        ("search_social", {"site": "Facebook", "query": "openai"}, ("facebook", "search", ["openai"], {"limit": 5})),
        ("get_social_profile", {"site": "x", "username": "OpenAI"}, ("x", "profile", ["OpenAI"], None)),
        ("get_x_thread", {"tweet": "1234567890"}, ("x", "thread", ["1234567890"], None)),
    ],
    ids=["read-job", "search", "profile", "thread"],
)
def test_each_action_reaches_agent_reach(mcp_server, recorded, name, arguments, expected):
    _call(mcp_server, name, arguments)

    assert recorded["actions"] == [expected]


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("search_social", {"site": "linkedin", "query": "python"}, "Unsupported site"),
        ("get_social_posts", {"site": "facebook", "username": "zuck"}, "Unsupported site"),
        ("search_linkedin_jobs", {"query": "python", "limit": 99}, "limit must be between"),
        ("get_x_thread", {"tweet": "not-a-tweet"}, "Invalid tweet"),
    ],
    ids=["linkedin-search", "facebook-posts", "limit-too-high", "bad-tweet"],
)
def test_invalid_input_is_rejected_before_counting(mcp_server, recorded, name, arguments, message):
    with pytest.raises(Exception, match=message):
        _call(mcp_server, name, arguments)

    assert recorded == {"counted": [], "actions": []}


def test_start_login_returns_viewer_link_without_counting(mcp_server, recorded, monkeypatch):
    monkeypatch.setattr(
        server_module.sessions, "start_login", lambda site: {"site": site, "viewer_url": "http://localhost:6080/vnc.html"}
    )

    response = _call(mcp_server, "start_login", {"site": "X"})

    assert response == {"site": "x", "viewer_url": "http://localhost:6080/vnc.html"}
    assert recorded["counted"] == []


def test_slow_request_does_not_block_other_calls(mcp_server, monkeypatch):
    finished = []

    def slow_action(site, action, arguments, options=None):
        time.sleep(1)
        finished.append("search")
        return []

    monkeypatch.setattr(server_module.sessions, "count_request", lambda caller, site: 7)
    monkeypatch.setattr(server_module.agent_reach, "run_action", slow_action)
    monkeypatch.setattr(server_module.sessions, "start_login", lambda site: finished.append("login") or {"site": site})

    async def call_both():
        await asyncio.gather(
            mcp_server.call_tool("search_linkedin_jobs", {"query": "python"}),
            mcp_server.call_tool("start_login", {"site": "x"}),
        )

    asyncio.run(call_both())

    assert finished == ["login", "search"]


def test_server_only_accepts_requests_addressed_to_localhost(mcp_server):
    security = mcp_server.settings.transport_security

    assert security.enable_dns_rebinding_protection is True
    assert security.allowed_hosts == ["127.0.0.1:*", "localhost:*"]


def test_allowed_hosts_come_from_the_setting(monkeypatch):
    monkeypatch.setattr(server_module, "load_dotenv", lambda: None)
    monkeypatch.setenv(MCP_ALLOWED_HOSTS_ENV, " social-agent.mcp-dev.svc.cluster.local:* , 10.0.0.5:8080 ")

    security = server_module.create_server().settings.transport_security

    assert security.enable_dns_rebinding_protection is True
    assert security.allowed_hosts == ["social-agent.mcp-dev.svc.cluster.local:*", "10.0.0.5:8080"]


@pytest.mark.parametrize("value", ["", " , "])
def test_empty_allowed_hosts_setting_stops_the_server_from_starting(monkeypatch, value):
    monkeypatch.setattr(server_module, "load_dotenv", lambda: None)
    monkeypatch.setenv(MCP_ALLOWED_HOSTS_ENV, value)

    with pytest.raises(ValueError, match="MCP_ALLOWED_HOSTS must list at least one host"):
        server_module.create_server()


def test_star_turns_the_host_check_off_for_cluster_deployments(monkeypatch):
    monkeypatch.setattr(server_module, "load_dotenv", lambda: None)
    monkeypatch.setenv(MCP_ALLOWED_HOSTS_ENV, "*")

    assert server_module.create_server().settings.transport_security.enable_dns_rebinding_protection is False


def test_command_timeout_reaches_caller_through_real_agent_reach_layer(mcp_server, monkeypatch):
    counted = []
    monkeypatch.setattr(server_module.sessions, "count_request", lambda caller, site: counted.append(site) or 7)

    def slow_command(argv):
        raise CommandError("'agent-reach linkedin jobs' did not finish within 150s. Retry with a lower limit.")

    monkeypatch.setattr(server_module.agent_reach, "run_command", slow_command)

    with pytest.raises(Exception, match="did not finish within 150s"):
        _call(mcp_server, "search_linkedin_jobs", {"query": "python"})
    assert counted == ["linkedin"]


def test_failed_request_still_counts_toward_daily_limit(mcp_server, recorded, monkeypatch):
    def failing_action(site, action, arguments, options=None):
        raise AgentReachError("UPSTREAM_BROKEN", "linkedin jobs failed")

    monkeypatch.setattr(server_module.agent_reach, "run_action", failing_action)

    with pytest.raises(Exception, match="linkedin jobs failed"):
        _call(mcp_server, "search_linkedin_jobs", {"query": "python"})
    assert recorded["counted"] == [("user-1", "linkedin", 1)]


@pytest.fixture
def profile_reads(monkeypatch):
    reads = []

    async def read_profile(caller, profile_url, sections):
        reads.append((caller.user_id, profile_url, sections))
        return {"url": "https://www.linkedin.com/in/jane-doe/", "sections": {"main_profile": "Jane Doe"}}

    monkeypatch.setattr(server_module.linkedin_profile, "read_profile", read_profile)
    return reads


def test_linkedin_profile_is_read_for_the_calling_user(mcp_server, recorded, profile_reads):
    response = _call(mcp_server, "get_linkedin_profile", {"profile_url": "https://in.linkedin.com/in/jane-doe"})

    assert profile_reads == [("user-1", "https://www.linkedin.com/in/jane-doe/", [])]
    assert recorded["counted"] == [("user-1", "linkedin", 1)]
    assert response == {
        "site": "linkedin",
        "action": "profile",
        "requests_left_today": 7,
        "url": "https://www.linkedin.com/in/jane-doe/",
        "sections": {"main_profile": "Jane Doe"},
    }


def test_linkedin_profile_without_a_link_reads_the_users_own_profile(mcp_server, recorded, profile_reads):
    _call(mcp_server, "get_linkedin_profile", {})

    assert profile_reads == [("user-1", None, [])]


def test_invalid_profile_link_is_rejected_before_counting(mcp_server, recorded, profile_reads):
    with pytest.raises(Exception, match="Invalid LinkedIn profile URL"):
        _call(mcp_server, "get_linkedin_profile", {"profile_url": "https://evil.com/in/jane"})

    assert recorded["counted"] == [] and profile_reads == []


def test_request_without_a_user_is_refused_before_counting(mcp_server, recorded, profile_reads, monkeypatch):
    monkeypatch.delenv(LOCAL_USER_ID_ENV)

    with pytest.raises(Exception, match="No Toolstore user"):
        _call(mcp_server, "get_linkedin_profile", {})

    assert recorded["counted"] == [] and profile_reads == []


def test_slow_browser_action_times_out_with_a_clear_message(mcp_server, recorded, monkeypatch):
    async def never_finishes(caller, profile_url, sections):
        await asyncio.sleep(60)

    monkeypatch.setattr(server_module, "BROWSER_ACTION_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(server_module.linkedin_profile, "read_profile", never_finishes)

    with pytest.raises(Exception, match="linkedin profile did not finish within 0.1s"):
        _call(mcp_server, "get_linkedin_profile", {})
    assert recorded["counted"] == [("user-1", "linkedin", 1)]


def test_linkedin_login_opens_our_browser_login_for_the_calling_user(mcp_server, recorded, monkeypatch):
    started = []

    async def start_browser_login(caller, site):
        started.append((caller.user_id, site))
        return {"site": site, "viewer_url": "http://localhost:6080/vnc.html"}

    monkeypatch.setattr(server_module.sessions, "start_browser_login", start_browser_login)
    monkeypatch.setattr(server_module.sessions, "start_login", lambda site: pytest.fail("Agent Reach login used"))

    response = _call(mcp_server, "start_login", {"site": "LinkedIn"})

    assert started == [("user-1", "linkedin")]
    assert response["viewer_url"] == "http://localhost:6080/vnc.html"
    assert recorded["counted"] == []


def test_each_profile_section_counts_as_one_more_page_load(mcp_server, recorded, profile_reads):
    _call(mcp_server, "get_linkedin_profile", {"sections": ["Experience", "posts", "experience"]})

    assert profile_reads == [("user-1", None, ["experience", "posts"])]
    assert recorded["counted"] == [("user-1", "linkedin", 3)]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"sections": ["hobbies"]}, "Unknown sections 'hobbies'"),
        ({"sections": ["experience", "education", "skills", "projects", "languages", "honors"]}, "At most 5 sections"),
    ],
)
def test_bad_profile_sections_are_rejected_before_counting(mcp_server, recorded, profile_reads, arguments, message):
    with pytest.raises(Exception, match=message):
        _call(mcp_server, "get_linkedin_profile", arguments)

    assert recorded["counted"] == [] and profile_reads == []


def test_company_is_read_by_page_name_with_its_sections(mcp_server, recorded, monkeypatch):
    reads = []

    async def read_company(caller, company, sections):
        reads.append((caller.user_id, company, sections))
        return {"url": "https://www.linkedin.com/company/microsoft/", "sections": {"about": "Microsoft"}}

    monkeypatch.setattr(server_module.linkedin_company, "read_company", read_company)

    arguments = {"company": "https://www.linkedin.com/company/microsoft/", "sections": ["jobs"]}
    response = _call(mcp_server, "get_linkedin_company", arguments)

    assert reads == [("user-1", "microsoft", ["jobs"])]
    assert recorded["counted"] == [("user-1", "linkedin", 2)]
    assert response["sections"] == {"about": "Microsoft"}


def test_post_search_counts_one_request_per_page(mcp_server, recorded, monkeypatch):
    searches = []

    async def search_posts(caller, keywords, date_posted, content_type, pages):
        searches.append((caller.user_id, keywords, date_posted, content_type, pages))
        return {"url": "https://www.linkedin.com/search/results/content/", "sections": {"search_results": "Feed post"}}

    monkeypatch.setattr(server_module.linkedin_posts, "search_posts", search_posts)

    arguments = {"keywords": " AI  marketing ", "date_posted": "Past-Week", "content_type": "images", "pages": 2}
    _call(mcp_server, "search_linkedin_posts", arguments)

    assert searches == [("user-1", "AI marketing", "past-week", "images", 2)]
    assert recorded["counted"] == [("user-1", "linkedin", 2)]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"keywords": ""}, "query is required"),
        ({"keywords": "AI", "date_posted": "yesterday"}, "Unknown date_posted 'yesterday'"),
        ({"keywords": "AI", "content_type": "podcasts"}, "Unknown content_type 'podcasts'"),
        ({"keywords": "AI", "pages": 4}, "pages must be between 1 and 3"),
    ],
)
def test_bad_post_search_input_is_rejected_before_counting(mcp_server, recorded, arguments, message):
    with pytest.raises(Exception, match=message):
        _call(mcp_server, "search_linkedin_posts", arguments)

    assert recorded["counted"] == []


def test_time_limit_grows_with_the_pages_a_call_loads(mcp_server, recorded, monkeypatch):
    async def never_finishes(caller, profile_url, sections):
        await asyncio.sleep(60)

    monkeypatch.setattr(server_module, "BROWSER_ACTION_TIMEOUT_SECONDS", 0.1)
    monkeypatch.setattr(server_module, "SECONDS_PER_EXTRA_PAGE_LOAD", 0.05)
    monkeypatch.setattr(server_module.linkedin_profile, "read_profile", never_finishes)

    with pytest.raises(Exception, match=r"did not finish within 0\.2s"):
        _call(mcp_server, "get_linkedin_profile", {"sections": ["skills", "projects"]})


@pytest.fixture
def instagram_reads(monkeypatch):
    calls = []

    def fake(command):
        async def read(caller, *args):
            calls.append((command, caller.user_id, *args))
            return [{"username": "nasa"}]

        return read

    for command in ("profile", "posts"):
        monkeypatch.setattr(server_module.instagram_reads, command, fake(command))
    return calls


@pytest.mark.parametrize(
    ("name", "arguments", "call", "cost"),
    [
        ("get_instagram_profile", {"username": "@nasa"}, ("profile", "user-1", "nasa"), 1),
        ("get_instagram_posts", {"username": "nasa", "limit": 12}, ("posts", "user-1", "nasa", 12), 1),
    ],
)
def test_instagram_reads_count_their_instagram_requests_and_answer_with_items(
    mcp_server, recorded, instagram_reads, name, arguments, call, cost
):
    response = _call(mcp_server, name, arguments)

    assert instagram_reads == [call]
    assert recorded["counted"] == [("user-1", "instagram", cost)]
    header = {"site": "instagram", "action": call[0], "requests_left_today": 7}
    assert response == {**header, "count": 1, "items": [{"username": "nasa"}]}


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("get_instagram_profile", {"username": "https://instagram.com/nasa"}, "Invalid username"),
        ("get_instagram_posts", {"username": "nasa", "limit": 13}, "limit must be between 1 and 12"),
    ],
)
def test_bad_instagram_input_is_rejected_before_counting(mcp_server, recorded, instagram_reads, name, arguments, message):
    with pytest.raises(Exception, match=message):
        _call(mcp_server, name, arguments)

    assert recorded["counted"] == [] and instagram_reads == []


def test_instagram_is_no_longer_read_through_agent_reach(mcp_server, recorded):
    with pytest.raises(Exception, match="Unsupported site"):
        _call(mcp_server, "get_social_profile", {"site": "instagram", "username": "nasa"})
