# toolstore-bootstrap
"""Client for the Tool Store Developer API (injected into imported connectors).

Per-request identity comes from inbound MCP headers when available.
Local activation falls back to TOOLSTORE_* environment variables.

Uses only the Python standard library so connector images do not need ``requests``.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import urllib.error
import urllib.request
from contextvars import ContextVar
from typing import Any, Mapping
from urllib.parse import urlparse

_request_auth: ContextVar[dict[str, str] | None] = ContextVar("toolstore_request_auth", default=None)
_ALLOWED_URL_SCHEMES = frozenset({"http", "https"})


def _header_value(headers: Mapping[str, str], name: str) -> str:
	needle = name.lower()
	for key, value in headers.items():
		if key.lower() == needle:
			return str(value).strip()
	return ""


def _bearer_token(auth_header: str) -> str:
	parts = auth_header.strip().split(None, 1)
	if len(parts) == 2 and parts[0].lower() == "bearer":
		return parts[1].strip()
	return ""


def bind_request_auth(headers: Mapping[str, str]) -> None:
	"""Bind caller identity from MCP proxy headers for the current request.

	User id is taken from the JWT payload (``user_id`` / ``sub`` / ``uid``) when
	present. A mismatched ``X-Toolstore-User-Id`` header is rejected so callers
	cannot point a valid JWT at another user's secrets path.
	"""
	jwt = _header_value(headers, "X-Toolstore-JWT") or _bearer_token(_header_value(headers, "Authorization"))
	header_user_id = _header_value(headers, "X-Toolstore-User-Id")
	user_slug = _header_value(headers, "X-Toolstore-User-Slug")
	jwt_user_id = _user_id_from_jwt(jwt) if jwt else ""
	if jwt_user_id and header_user_id and jwt_user_id != header_user_id:
		_request_auth.set(None)
		return
	user_id = jwt_user_id or header_user_id
	if jwt and user_id:
		_request_auth.set({"jwt": jwt, "user_id": user_id, "user_slug": user_slug})
	else:
		_request_auth.set(None)


def _user_id_from_jwt(jwt: str) -> str:
	"""Best-effort subject from JWT payload (signature verified by Dev API)."""
	import base64

	parts = (jwt or "").split(".")
	if len(parts) < 2:
		return ""
	payload = parts[1]
	padding = "=" * (-len(payload) % 4)
	try:
		raw = base64.urlsafe_b64decode(payload + padding)
		claims = json.loads(raw.decode("utf-8"))
	except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
		return ""
	if not isinstance(claims, dict):
		return ""
	for key in ("user_id", "sub", "uid"):
		value = claims.get(key)
		if value is not None and str(value).strip():
			return str(value).strip()
	return ""


def _http_json(
	method: str,
	url: str,
	*,
	headers: dict[str, str],
	body: dict[str, Any] | None = None,
	timeout: float = 20,
) -> tuple[int, str, Any]:
	"""Perform an HTTP JSON call. Returns (status, raw_text, parsed_json_or_None)."""
	scheme = urlparse(url).scheme.lower()
	if scheme not in _ALLOWED_URL_SCHEMES:
		raise ValueError(f"Unsupported URL scheme: {scheme!r}")
	payload = None if body is None else json.dumps(body).encode("utf-8")
	request = urllib.request.Request(url, data=payload, headers=headers, method=method.upper())  # noqa: S310
	try:
		with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
			raw = response.read().decode("utf-8", errors="replace")
			status = int(getattr(response, "status", 200) or 200)
	except urllib.error.HTTPError as exc:
		raw = exc.read().decode("utf-8", errors="replace")
		status = int(exc.code)
	except urllib.error.URLError as exc:
		raise RuntimeError(f"Tool Store API request failed: {exc}") from exc

	parsed: Any = None
	if raw.strip():
		try:
			parsed = json.loads(raw)
		except json.JSONDecodeError:
			parsed = None
	return status, raw, parsed


class ToolStoreClient:
	"""Client for interacting with the Tool Store Developer API."""

	def __init__(
		self,
		*,
		jwt: str | None = None,
		user_id: str | None = None,
		user_slug: str | None = None,
	) -> None:
		bound = _request_auth.get()
		self.api_base = os.getenv("TOOLSTORE_API_BASE", "https://api.toolstore.com/dev_api/v1").rstrip("/")
		self.jwt = jwt or (bound or {}).get("jwt") or os.getenv("TOOLSTORE_JWT", "")
		self.dev_slug = os.getenv("TOOLSTORE_DEV_SLUG", "")
		self.tool_slug = os.getenv("TOOLSTORE_TOOL_SLUG", "")
		self.user_id = user_id or (bound or {}).get("user_id") or os.getenv("TOOLSTORE_USER_ID", "")
		self.user_slug = user_slug or (bound or {}).get("user_slug") or os.getenv("TOOLSTORE_USER_SLUG", "")
		env_endpoint = os.getenv("TOOLSTORE_OAUTH_TOKEN_ENDPOINT", "").strip()
		self.oauth_token_endpoint = env_endpoint or f"{self.api_base}/tool-auth/refresh"

	def _auth_headers(self) -> dict[str, str]:
		if not self.jwt:
			raise RuntimeError(
				"Missing Tool Store auth. Connect via MCP with a valid API key, " "or set TOOLSTORE_JWT for local activation.",
			)
		return {"Authorization": f"Bearer {self.jwt}", "Content-Type": "application/json"}

	def _require_identities(self) -> None:
		missing = [
			name
			for name, value in (
				("TOOLSTORE_DEV_SLUG", self.dev_slug),
				("TOOLSTORE_TOOL_SLUG", self.tool_slug),
				("TOOLSTORE_USER_ID", self.user_id),
				("TOOLSTORE_USER_SLUG", self.user_slug),
			)
			if not value
		]
		if missing:
			raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

	def get_user_data(self) -> dict[str, Any]:
		"""Fetch tool user data for the current user."""
		self._require_identities()
		url = f"{self.api_base}/tool-user-data/{self.dev_slug}/{self.tool_slug}/user/{self.user_id}"
		status, raw, data = _http_json("GET", url, headers=self._auth_headers(), timeout=20)
		if status == 404:
			return {}
		if status < 200 or status >= 300:
			raise RuntimeError(f"Failed to get user data: {status} {raw}")
		if not isinstance(data, dict):
			return {}
		inner = data.get("data", data)
		return inner if isinstance(inner, dict) else {}

	def update_user_data(self, new_data: dict[str, Any]) -> dict[str, Any]:
		"""Replace or merge tool user data for the current user."""
		self._require_identities()
		url = f"{self.api_base}/tool-user-data/{self.dev_slug}/{self.tool_slug}/user/{self.user_id}"
		status, raw, data = _http_json(
			"PUT",
			url,
			headers=self._auth_headers(),
			body=new_data,
			timeout=20,
		)
		if status < 200 or status >= 300:
			raise RuntimeError(f"Failed to update user data: {status} {raw}")
		if not isinstance(data, dict):
			return {}
		inner = data.get("data", data)
		return inner if isinstance(inner, dict) else {}

	def get_secrets(self) -> dict[str, str]:
		"""Return per-user API secrets from activation (``data.secrets``)."""
		user_data = self.get_user_data()
		raw = user_data.get("secrets")
		if not isinstance(raw, dict) or not raw:
			nested = user_data.get("data")
			raw = nested.get("secrets") if isinstance(nested, dict) else {}
		if not isinstance(raw, dict):
			return {}
		return {str(key): str(value) for key, value in raw.items() if key and value is not None and str(value).strip()}

	def get_secret(self, name: str) -> str:
		"""Return one secret by env var name, or raise if missing."""
		secrets = self.get_secrets()
		value = secrets.get(name, "").strip()
		if not value:
			raise RuntimeError(
				f"Missing secret '{name}'. Please complete tool activation and paste your API key.",
			)
		return value

	def get_oauth_access_token(self, provider: str = "google") -> str:
		"""Retrieve an OAuth access token for the provider from user data."""
		user_data = self.get_user_data()
		oauth = user_data.get("oauth", {})
		if not isinstance(oauth, dict):
			oauth = {}
		prov = oauth.get(provider, {})
		if not isinstance(prov, dict):
			prov = {}

		def still_valid(exp_value: Any) -> bool:
			if not exp_value:
				return True
			try:
				exp_ts = float(exp_value)
				return time.time() < (exp_ts - 15)
			except Exception:
				return True

		access_token = prov.get("access_token")
		expiry = prov.get("expiry") or prov.get("expires_at")
		refresh_token = prov.get("refresh_token")

		if access_token and still_valid(expiry):
			return str(access_token)

		if self.oauth_token_endpoint and refresh_token:
			payload = {
				"provider": provider,
				"refresh_token": refresh_token,
				"dev_slug": self.dev_slug,
				"tool_slug": self.tool_slug,
				"user_id": self.user_id,
				"user_slug": self.user_slug,
			}
			status, raw, fresh = _http_json(
				"POST",
				self.oauth_token_endpoint,
				headers=self._auth_headers(),
				body=payload,
				timeout=30,
			)
			if status < 200 or status >= 300:
				raise RuntimeError(
					f"Token refresh failed: {status} {raw}. Please re-connect your account.",
				)
			if not isinstance(fresh, dict):
				fresh = {}
			new_access = fresh.get("access_token") or fresh.get("id_token")
			expires_in = fresh.get("expires_in")
			new_expiry = None
			if fresh.get("expiry"):
				new_expiry = fresh.get("expiry")
			elif fresh.get("expires_at"):
				new_expiry = fresh.get("expires_at")
			elif isinstance(expires_in, (int, float)):
				new_expiry = str(time.time() + float(expires_in))

			if not new_access:
				raise RuntimeError("Token refresh did not return access_token. Please re-connect your account.")

			prov_updated = dict(prov)
			prov_updated["access_token"] = new_access
			if new_expiry is not None:
				prov_updated["expiry"] = str(new_expiry)
			oauth_updated = dict(oauth)
			oauth_updated[provider] = prov_updated
			updated_doc = dict(user_data)
			updated_doc["oauth"] = oauth_updated
			with contextlib.suppress(Exception):
				self.update_user_data(updated_doc)
			return str(new_access)

		if not access_token:
			raise RuntimeError("Missing access token. Please connect your account in activation.")
		raise RuntimeError("Access token expired. Please re-connect your account.")
