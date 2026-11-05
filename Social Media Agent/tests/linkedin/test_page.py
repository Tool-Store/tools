import pytest

from errors import NotLoggedInError
from linkedin import page as linkedin_page


class _ProbePage:
    def __init__(self, logged_out, url="https://www.linkedin.com/login"):
        self.logged_out = logged_out
        self.url = url

    async def run_script(self, name):
        assert name == "linkedin_auth_probe"
        return self.logged_out


@pytest.mark.asyncio
async def test_logged_in_page_passes():
    await linkedin_page.require_login(_ProbePage(logged_out=False))


@pytest.mark.asyncio
async def test_login_wall_asks_the_user_to_log_in_again():
    with pytest.raises(NotLoggedInError, match="start_login with site 'linkedin'"):
        await linkedin_page.require_login(_ProbePage(logged_out=True))


@pytest.mark.asyncio
async def test_security_check_says_where_linkedin_sent_the_session():
    checkpoint = "https://www.linkedin.com/checkpoint/challenge/AQG"

    with pytest.raises(NotLoggedInError) as error:
        await linkedin_page.require_login(_ProbePage(logged_out=True, url=checkpoint))

    assert "security check or login page" in str(error.value)
    assert checkpoint in str(error.value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, ""), ("  a   b\n c ", "a b c"), (42, "42")],
)
def test_whitespace_is_normalized(raw, expected):
    assert linkedin_page.normalize_whitespace(raw) == expected

