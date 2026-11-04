"""
Every error the tool raises on purpose, in one place.

Each message says what went wrong and what to do next; the MCP layer passes it to the AI unchanged.
"""


class CallerError(PermissionError):
    """The request does not say which Toolstore user it is for, or says it inconsistently."""


class DailyLimitError(RuntimeError):
    """The user's daily request limit for a site is used up."""


class LoginStoreError(RuntimeError):
    """Saved logins cannot be used because the store is not set up (missing or invalid key)."""


class NotLoggedInError(RuntimeError):
    """The user has no usable saved login for a site and must log in again."""


class LoginBusyError(RuntimeError):
    """Another login window is still open in the shared viewer."""


class LoginTimeoutError(TimeoutError):
    """The user did not finish logging in before the login window closed."""


class PageReadError(RuntimeError):
    """A site page does not have the content an action reads."""


class CommandError(RuntimeError):
    """A command cannot start or does not finish in time."""


class AgentReachError(RuntimeError):
    """An Agent Reach failure; `code` is Agent Reach's error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def login_needed_message(site: str, problem: str) -> str:
    """Tell the AI to start a fresh login for the site; `problem` is the sentence start, e.g. 'Not logged in to'."""
    return (
        f"{problem} {site}. Call start_login with site '{site}' and ask the user to log in "
        "in the browser viewer with their own account, then retry."
    )
