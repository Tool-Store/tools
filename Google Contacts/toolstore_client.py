import os
import time
from typing import Any, Dict, Optional, Tuple

import requests


class ToolStoreClient:
    """Client for interacting with the Tool Store Developer API.

    Responsibilities:
    - Retrieve per-user tool data (e.g., stored OAuth tokens) using the Firebase JWT.
    - Upload files to Tool Store Storage via direct upload or presigned URL.

    Environment variables:
    - TOOLSTORE_API_BASE: Base URL for the Developer API.
    - TOOLSTORE_JWT: Firebase JWT for the current user session.
    - TOOLSTORE_DEV_SLUG, TOOLSTORE_TOOL_SLUG: Identify the tool namespace.
    - TOOLSTORE_USER_ID, TOOLSTORE_USER_SLUG: Identify the current user.
    - TOOLSTORE_OAUTH_TOKEN_ENDPOINT (optional): Endpoint for exchanging refresh tokens.
    """

    def __init__(self) -> None:
        self.api_base = os.getenv("TOOLSTORE_API_BASE", "https://api.toolstore.com/dev_api/v1").rstrip("/")
        self.jwt = os.getenv("TOOLSTORE_JWT", "")
        self.dev_slug = os.getenv("TOOLSTORE_DEV_SLUG", "")
        self.tool_slug = os.getenv("TOOLSTORE_TOOL_SLUG", "")
        self.user_id = os.getenv("TOOLSTORE_USER_ID", "")
        self.user_slug = os.getenv("TOOLSTORE_USER_SLUG", "")
        env_endpoint = os.getenv("TOOLSTORE_OAUTH_TOKEN_ENDPOINT", "").strip()
        # Default to the Dev API standard refresh endpoint if not explicitly set
        self.oauth_token_endpoint = env_endpoint or f"{self.api_base}/tool-auth/refresh"

    # ------------------------
    # Internal helpers
    # ------------------------
    def _auth_headers(self) -> Dict[str, str]:
        if not self.jwt:
            raise RuntimeError(
                "Missing TOOLSTORE_JWT. Please run activation and ensure the Tool Store host injects user auth."
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

    # ------------------------
    # Tool User Data
    # ------------------------
    def get_user_data(self) -> Dict[str, Any]:
        """Fetch tool user data for the current user.

        Returns:
            Dict containing user-specific data for this tool.

        Raises:
            RuntimeError: if required identities or auth are missing, or API errors occur.
        """
        self._require_identities()
        url = (
            f"{self.api_base}/tool-user-data/{self.dev_slug}/{self.tool_slug}/user/{self.user_id}"
        )
        resp = requests.get(url, headers=self._auth_headers(), timeout=20)
        if resp.status_code == 404:
            return {}
        if not resp.ok:
            raise RuntimeError(f"Failed to get user data: {resp.status_code} {resp.text}")
        data = resp.json()
        # API may wrap data; support both raw dict and {data: {...}}
        return data.get("data", data)

    def update_user_data(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        """Replace or merge tool user data for the current user.

        This operation issues a PUT to the Tool User Data endpoint. The server-side
        may either replace or merge depending on implementation. Callers should
        send the complete desired data object.

        Args:
            new_data: The full data document to store for the user.

        Returns:
            The updated data document as returned by the API.
        """
        self._require_identities()
        url = (
            f"{self.api_base}/tool-user-data/{self.dev_slug}/{self.tool_slug}/user/{self.user_id}"
        )
        resp = requests.put(url, json=new_data, headers=self._auth_headers(), timeout=20)
        if not resp.ok:
            raise RuntimeError(f"Failed to update user data: {resp.status_code} {resp.text}")
        data = resp.json()
        return data.get("data", data)

    def get_oauth_access_token(self, provider: str = "google") -> str:
        """Retrieve an OAuth access token for the provider from user data.

        If an OAuth token endpoint is provided, this can be extended to perform a
        token refresh. By default, this method only returns the stored access token.

        Args:
            provider: OAuth provider key in user data (default: "google").

        Returns:
            Access token string.
        """
        user_data = self.get_user_data()
        oauth = user_data.get("oauth", {})
        prov = oauth.get(provider, {})

        def still_valid(exp_value: Any) -> bool:
            if not exp_value:
                return True
            try:
                exp_ts = float(exp_value)
                # Include a small buffer to avoid edge expiry
                return time.time() < (exp_ts - 15)
            except Exception:
                return True

        access_token = prov.get("access_token")
        expiry = prov.get("expiry") or prov.get("expires_at")
        refresh_token = prov.get("refresh_token")

        if access_token and still_valid(expiry):
            return access_token

        # Try refresh if endpoint and refresh_token are available
        if self.oauth_token_endpoint and refresh_token:
            payload = {
                "provider": provider,
                "refresh_token": refresh_token,
                "dev_slug": self.dev_slug,
                "tool_slug": self.tool_slug,
                "user_id": self.user_id,
                "user_slug": self.user_slug,
            }
            resp = requests.post(
                self.oauth_token_endpoint,
                json=payload,
                headers=self._auth_headers(),
                timeout=30,
            )
            if not resp.ok:
                raise RuntimeError(
                    f"Token refresh failed: {resp.status_code} {resp.text}. Please re-connect your account."
                )
            fresh = resp.json() or {}
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
                raise RuntimeError(
                    "Token refresh did not return access_token. Please re-connect your account."
                )

            # Persist updated tokens into user data if possible
            prov_updated = dict(prov)
            prov_updated["access_token"] = new_access
            if new_expiry is not None:
                prov_updated["expiry"] = str(new_expiry)
            oauth_updated = dict(oauth)
            oauth_updated[provider] = prov_updated
            updated_doc = dict(user_data)
            updated_doc["oauth"] = oauth_updated
            try:
                self.update_user_data(updated_doc)
            except Exception:
                # Non-fatal if we cannot persist
                pass
            return new_access

        # No refresh path available
        if not access_token:
            raise RuntimeError(
                "Missing access token. Please connect your account in activation."
            )
        raise RuntimeError("Access token expired. Please re-connect your account.")

    # ------------------------
    # Storage
    # ------------------------
    def upload_file(self, file_name: str, content: bytes, content_type: str = "text/csv") -> Dict[str, Any]:
        """Upload a file to Tool Store storage using presigned URL flow.

        Args:
            file_name: Target file name.
            content: File content as bytes.
            content_type: MIME type.

        Returns:
            Dict with storage metadata, including storage path and download URL if provided.
        """
        self._require_identities()
        # 1) Request presigned URL
        gen_url = f"{self.api_base}/tool-storage/generate-upload-url"
        payload = {
            "dev_slug": self.dev_slug,
            "tool_slug": self.tool_slug,
            "user_slug": self.user_slug,
            "file_name": file_name,
            "content_type": content_type,
        }
        resp = requests.post(gen_url, json=payload, headers=self._auth_headers(), timeout=20)
        if not resp.ok:
            raise RuntimeError(
                f"Failed to generate upload URL: {resp.status_code} {resp.text}"
            )
        info = resp.json()
        upload_url = info.get("upload_url") or info.get("url")
        storage_path = info.get("storage_path")
        if not upload_url:
            raise RuntimeError("Upload URL not returned by Tool Store.")

        # 2) PUT content to presigned URL
        put_headers = {"Content-Type": content_type}
        put_resp = requests.put(upload_url, data=content, headers=put_headers, timeout=60)
        if not (200 <= put_resp.status_code < 300):
            raise RuntimeError(
                f"Failed to upload file to storage: {put_resp.status_code} {put_resp.text}"
            )

        return {
            "storage_path": storage_path,
            "file_name": file_name,
            "content_type": content_type,
            "upload_url": upload_url,
        }

    def get_download_url(self, file_name: str) -> str:
        """Get a presigned download URL for a file in Tool Store storage."""
        self._require_identities()
        url = f"{self.api_base}/tool-storage/download/{self.dev_slug}/{self.tool_slug}/{self.user_slug}/{file_name}"
        resp = requests.get(url, headers=self._auth_headers(), timeout=20)
        if not resp.ok:
            raise RuntimeError(f"Failed to get download URL: {resp.status_code} {resp.text}")
        data = resp.json()
        return data.get("download_url") or data.get("url") or ""
