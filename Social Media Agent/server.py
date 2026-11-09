"""MCP server: registers the 14 functions the AI can call."""

import logging
import os
from typing import Any, Awaitable, Callable, Dict, List, Optional

import anyio
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import TextContent

import agent_reach
import responses
import sessions
import validators
from caller import Caller, current_caller
from constants import (
    ANY_HOST,
    BROWSER_ACTION_TIMEOUT_SECONDS,
    BROWSER_LOGIN_PAGES,
    DEFAULT_MCP_ALLOWED_HOSTS,
    DEFAULT_RESULT_LIMIT,
    INSTAGRAM,
    INSTAGRAM_MAX_POSTS,
    INSTAGRAM_READ_COSTS,
    LINKEDIN,
    LINKEDIN_COMPANY_SECTIONS,
    LINKEDIN_PROFILE_SECTIONS,
    LOGIN_SITES,
    MAX_EXTRA_SECTIONS,
    MCP_ALLOWED_HOSTS_ENV,
    MCP_ALLOWED_ORIGINS,
    POST_CONTENT_TYPES,
    POST_DATE_FILTERS,
    PROFILE_SITES,
    SEARCH_SITES,
    SECONDS_PER_EXTRA_PAGE_LOAD,
    X,
)
from instagram import reads as instagram_reads
from linkedin import company as linkedin_company
from linkedin import posts as linkedin_posts
from linkedin import profile as linkedin_profile
from x import reads as x_reads


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO))


async def _run(
    site: str,
    action: str,
    arguments: List[str],
    options: Optional[Dict[str, Any]] = None,
) -> List[TextContent]:
    caller = current_caller()
    # A worker thread keeps the server answering other calls during slow browser actions.
    return await anyio.to_thread.run_sync(_run_in_thread, caller, site, action, arguments, options)


def _run_in_thread(
    caller: Caller,
    site: str,
    action: str,
    arguments: List[str],
    options: Optional[Dict[str, Any]],
) -> List[TextContent]:
    requests_left = sessions.count_request(caller, site)
    items = agent_reach.run_action(site, action, arguments, options)
    return _answer(site, action, requests_left, items)


async def _run_browser_action(
    site: str,
    action: str,
    page_loads: int,
    read: Callable[[Caller], Awaitable[Any]],
    fit: Callable[[Dict[str, Any], Any], Dict[str, Any]] = responses.fit_sections,
) -> List[TextContent]:
    """Count the call's page loads, then run `read(caller)` in the caller's own browser session.

    `fit` keeps the answer within the size limit: fit_sections for section answers, fit_items for lists.
    """
    caller = current_caller()
    requests_left = await anyio.to_thread.run_sync(sessions.count_request, caller, site, page_loads)
    timeout = BROWSER_ACTION_TIMEOUT_SECONDS + SECONDS_PER_EXTRA_PAGE_LOAD * (page_loads - 1)
    try:
        with anyio.fail_after(timeout):
            result = await read(caller)
    except TimeoutError:
        raise TimeoutError(f"{site} {action} did not finish within {timeout}s. Retry with fewer sections or later.") from None
    header = {"site": site, "action": action, "requests_left_today": requests_left}
    return responses.to_text_content(fit(header, result))


def _answer(site: str, action: str, requests_left: int, items: List[Dict[str, Any]]) -> List[TextContent]:
    header = {"site": site, "action": action, "requests_left_today": requests_left}
    return responses.to_text_content(responses.fit_items(header, items))


def _transport_security() -> TransportSecuritySettings:
    hosts = [host.strip() for host in os.getenv(MCP_ALLOWED_HOSTS_ENV, DEFAULT_MCP_ALLOWED_HOSTS).split(",") if host.strip()]
    if not hosts:
        raise ValueError(f"{MCP_ALLOWED_HOSTS_ENV} must list at least one host (e.g. 'localhost:*'), or be '{ANY_HOST}'.")
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=hosts != [ANY_HOST],
        allowed_hosts=hosts,
        allowed_origins=MCP_ALLOWED_ORIGINS,
    )


def create_server() -> FastMCP:
    """Create the MCP server and register all functions."""
    load_dotenv()
    _setup_logging()
    server = FastMCP(
        "social-media-agent",
        host=os.getenv("MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("MCP_PORT", "8000")),
        transport_security=_transport_security(),
    )
    _register_login_tool(server)
    _register_linkedin_tools(server)
    _register_instagram_tools(server)
    _register_x_tools(server)
    _register_social_tools(server)
    return server


def _register_login_tool(server: FastMCP) -> None:
    @server.tool()
    async def start_login(site: str) -> List[TextContent]:
        """Open a site's login page in the user's browser and return the link where the user logs in."""
        site = validators.validate_site(site, LOGIN_SITES)
        if site in BROWSER_LOGIN_PAGES:
            login = await sessions.start_browser_login(current_caller(), site)
        else:
            login = await anyio.to_thread.run_sync(sessions.start_login, site)
        return responses.to_text_content(login)


def _register_linkedin_tools(server: FastMCP) -> None:
    @server.tool()
    async def search_linkedin_jobs(
        query: str,
        location: Optional[str] = None,
        limit: int = DEFAULT_RESULT_LIMIT,
    ) -> List[TextContent]:
        """Search LinkedIn jobs with the user's logged-in LinkedIn session."""
        options = {
            "limit": validators.validate_limit(limit),
            "location": validators.validate_location(location) if location else None,
        }
        return await _run(LINKEDIN, agent_reach.JOB_SEARCH, [validators.validate_query(query)], options)

    @server.tool()
    async def read_linkedin_job(url: str) -> List[TextContent]:
        """Read one LinkedIn job post by its link."""
        return await _run(LINKEDIN, agent_reach.JOB_READ, [validators.validate_linkedin_job_url(url)])

    @server.tool()
    async def get_linkedin_profile(profile_url: Optional[str] = None, sections: Optional[List[str]] = None) -> List[TextContent]:
        """Read a LinkedIn profile as text: name, headline, location, About and Featured, plus any extra sections.

        profile_url: e.g. https://www.linkedin.com/in/jane-doe/; leave empty for the user's own profile.
        sections: up to 5 of experience, education, skills, projects, certifications, languages, honors,
        volunteering, interests, contact_info, posts. Each one opens one more page and counts toward the daily limit.
        Returns each section's text and links (people, companies, schools, posts) for follow-up calls.
        """
        url = validators.validate_linkedin_profile_url(profile_url) if profile_url else None
        names = validators.validate_choices(sections, LINKEDIN_PROFILE_SECTIONS, "sections", MAX_EXTRA_SECTIONS)
        return await _run_browser_action(
            LINKEDIN, "profile", 1 + len(names), lambda caller: linkedin_profile.read_profile(caller, url, names)
        )

    @server.tool()
    async def get_linkedin_company(company: str, sections: Optional[List[str]] = None) -> List[TextContent]:
        """Read a LinkedIn company page as text: About (industry, size, headquarters, website), plus posts or jobs.

        company: page name such as 'microsoft', or a link such as https://www.linkedin.com/company/microsoft/.
        sections: any of posts, jobs. Each one opens one more page and counts toward the daily limit.
        """
        name = validators.validate_company(company)
        names = validators.validate_choices(sections, LINKEDIN_COMPANY_SECTIONS, "sections", MAX_EXTRA_SECTIONS)
        return await _run_browser_action(
            LINKEDIN, "company", 1 + len(names), lambda caller: linkedin_company.read_company(caller, name, names)
        )

    @server.tool()
    async def search_linkedin_posts(
        keywords: str,
        date_posted: Optional[str] = None,
        content_type: Optional[str] = None,
        pages: int = 1,
    ) -> List[TextContent]:
        """Search LinkedIn posts by keywords and return the results as text: authors, post text, reactions and links.

        date_posted: past-24h, past-week or past-month. content_type: videos, images, job_posts, live_videos or documents.
        pages: 1 to 3; more pages scroll further for more posts and count as more requests.
        """
        query = validators.validate_query(keywords)
        posted = validators.validate_choice(date_posted, POST_DATE_FILTERS, "date_posted")
        kind = validators.validate_choice(content_type, tuple(POST_CONTENT_TYPES), "content_type")
        page_count = validators.validate_pages(pages)
        return await _run_browser_action(
            LINKEDIN,
            "post search",
            page_count,
            lambda caller: linkedin_posts.search_posts(caller, query, posted, kind, page_count),
        )


def _register_instagram_tools(server: FastMCP) -> None:
    async def run(command: str, read: Callable[[Caller], Awaitable[Any]]) -> List[TextContent]:
        return await _run_browser_action(INSTAGRAM, command, INSTAGRAM_READ_COSTS[command], read, responses.fit_items)

    @server.tool()
    async def get_instagram_profile(username: str) -> List[TextContent]:
        """Read an Instagram account's profile: name, bio, followers, following, post count, verified, category, website."""
        name = validators.validate_username(username)
        return await run("profile", lambda caller: instagram_reads.profile(caller, name))

    @server.tool()
    async def get_instagram_posts(username: str, limit: int = DEFAULT_RESULT_LIMIT) -> List[TextContent]:
        """Read an Instagram account's recent posts (up to 12): full caption, likes or plays, comments, type, date, link."""
        name, count = validators.validate_username(username), validators.validate_limit(limit, INSTAGRAM_MAX_POSTS)
        return await run("posts", lambda caller: instagram_reads.posts(caller, name, count))


def _register_x_tools(server: FastMCP) -> None:
    async def run(command: str, read: Callable[[Caller], Awaitable[Any]]) -> List[TextContent]:
        return await _run_browser_action(X, command, 1, read, responses.fit_items)

    @server.tool()
    async def search_x(query: str, limit: int = DEFAULT_RESULT_LIMIT) -> List[TextContent]:
        """Search X posts (tweets): text, author, date, likes, retweets, replies, views, media and link.

        query: what to search for; X's search operators work, e.g. 'from:NASA moon', '#python', 'lang:en'.
        limit: 1 to 20 tweets (default 5).
        """
        text, count = validators.validate_query(query), validators.validate_limit(limit)
        return await run("search", lambda caller: x_reads.search(caller, text, count))

    @server.tool()
    async def get_x_profile(username: str) -> List[TextContent]:
        """Read an X account's profile: name, bio, location, website, followers, following, tweets, likes, verified, join date."""
        name = validators.validate_x_handle(username)
        return await run("profile", lambda caller: x_reads.profile(caller, name))

    @server.tool()
    async def get_x_tweets(username: str, limit: int = DEFAULT_RESULT_LIMIT) -> List[TextContent]:
        """Read an X account's latest tweets, newest first and without the pinned one (1 to 20, default 5).

        Each tweet has its text, date, likes, retweets, replies, views, media and link.
        """
        name, count = validators.validate_x_handle(username), validators.validate_limit(limit)
        return await run("tweets", lambda caller: x_reads.tweets(caller, name, count))

    @server.tool()
    async def get_x_thread(tweet: str, limit: int = DEFAULT_RESULT_LIMIT) -> List[TextContent]:
        """Read a tweet with its replies, by tweet id or link; limit counts the tweet itself (1 to 20, default 5)."""
        tweet_id, count = validators.validate_tweet(tweet), validators.validate_limit(limit)
        return await run("thread", lambda caller: x_reads.thread(caller, tweet_id, count))


def _register_social_tools(server: FastMCP) -> None:
    @server.tool()
    async def search_social(site: str, query: str, limit: int = DEFAULT_RESULT_LIMIT) -> List[TextContent]:
        """Search Facebook posts with the user's logged-in session."""
        site = validators.validate_site(site, SEARCH_SITES)
        options = {"limit": validators.validate_limit(limit)}
        return await _run(site, agent_reach.SEARCH, [validators.validate_query(query)], options)

    @server.tool()
    async def get_social_profile(site: str, username: str) -> List[TextContent]:
        """Get a Facebook profile by username."""
        site = validators.validate_site(site, PROFILE_SITES)
        return await _run(site, agent_reach.PROFILE, [validators.validate_username(username)])


def main() -> None:
    server = create_server()
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    server.run(transport=transport)


if __name__ == "__main__":
    main()
