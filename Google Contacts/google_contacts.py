import datetime as dt
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


PEOPLE_BASE = "https://people.googleapis.com/v1"


class GooglePeopleClient:
    """Minimal Google People API client using a bearer access token.

    This client performs direct REST calls with an access token obtained via Tool Store
    activation. It does not handle token refresh; callers should ensure tokens are valid.
    """

    def __init__(self, access_token: str) -> None:
        if not access_token:
            raise ValueError("access_token is required")
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})

    # ------------------------
    # Helpers
    # ------------------------
    @staticmethod
    def _read_mask(fields: Iterable[str]) -> str:
        return ",".join(sorted(set(fields)))

    # ------------------------
    # Core operations
    # ------------------------
    def search_contacts(self, query: str, page_size: int = 50, page_token: Optional[str] = None) -> Dict[str, Any]:
        """Search contacts by text query.

        Returns a JSON payload from People API `people.searchContacts`.
        """
        if not query:
            raise ValueError("query is required")
        if page_size <= 0 or page_size > 200:
            raise ValueError("page_size must be between 1 and 200")

        params = {
            "query": query,
            "readMask": self._read_mask(
                ["names", "emailAddresses", "phoneNumbers", "photos", "birthdays"]
            ),
            "pageSize": page_size,
        }
        if page_token:
            params["pageToken"] = page_token
        url = f"{PEOPLE_BASE}/people:searchContacts"
        resp = self.session.get(url, params=params, timeout=20)
        if not resp.ok:
            raise RuntimeError(f"searchContacts failed: {resp.status_code} {resp.text}")
        return resp.json()

    def get_contact(self, resource_name: str) -> Dict[str, Any]:
        """Get full details for a contact resource name (e.g., people/c123)."""
        if not resource_name:
            raise ValueError("resource_name is required")
        params = {
            "personFields": self._read_mask(
                [
                    "names",
                    "emailAddresses",
                    "phoneNumbers",
                    "photos",
                    "birthdays",
                    "organizations",
                    "biographies",
                    "memberships",
                ]
            )
        }
        url = f"{PEOPLE_BASE}/{resource_name}"
        resp = self.session.get(url, params=params, timeout=20)
        if not resp.ok:
            raise RuntimeError(f"getContact failed: {resp.status_code} {resp.text}")
        return resp.json()

    def delete_contact(self, resource_name: str) -> None:
        """Delete a contact by resource name."""
        if not resource_name:
            raise ValueError("resource_name is required")
        url = f"{PEOPLE_BASE}/{resource_name}:deleteContact"
        resp = self.session.delete(url, timeout=20)
        if not resp.ok:
            raise RuntimeError(f"deleteContact failed: {resp.status_code} {resp.text}")

    def create_contact(
        self,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        birthday: Optional[str] = None,
        photo_url: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new contact and optionally set a profile photo.

        Returns the created person object. If a photo_url is provided, attempts to
        upload the image after creation via updateContactPhoto.
        """
        person: Dict[str, Any] = {}

        if given_name is not None or family_name is not None:
            person["names"] = [{"givenName": given_name or "", "familyName": family_name or ""}]
        if email is not None:
            person["emailAddresses"] = [{"value": email}]
        if phone is not None:
            person["phoneNumbers"] = [{"value": phone}]
        if birthday is not None:
            year, month, day = self._parse_birthday(birthday)
            bday: Dict[str, Any] = {"date": {"month": month, "day": day}}
            if year is not None:
                bday["date"]["year"] = year
            person["birthdays"] = [bday]
        if note is not None:
            person["biographies"] = [{"value": note}]

        url = f"{PEOPLE_BASE}/people:createContact"
        resp = self.session.post(url, json=person, timeout=20)
        if not resp.ok:
            raise RuntimeError(f"createContact failed: {resp.status_code} {resp.text}")
        created = resp.json()

        # Photo (post-creation)
        if photo_url:
            rn = created.get("resourceName")
            if rn:
                try:
                    self.update_contact_photo(rn, photo_url)
                    # Refresh the person to include the new photo
                    created = self.get_contact(rn)
                except Exception:
                    # Photo errors should not prevent basic creation
                    pass
        return created

    def update_contact(
        self,
        resource_name: str,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        birthday: Optional[str] = None,
        photo_url: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a contact by merging selected fields and sending PATCH with ETag.

        Google People API requires an ETag for updates. We fetch the current record, merge
        the provided fields, then call `people.updateContact`.
        """
        if not resource_name:
            raise ValueError("resource_name is required")

        current = self.get_contact(resource_name)
        etag = current.get("etag") or current.get("metadata", {}).get("sources", [{}])[0].get("etag")
        if not etag:
            raise RuntimeError("Contact ETag not found; cannot perform update.")

        person: Dict[str, Any] = {"etag": etag}

        # Names
        if given_name is not None or family_name is not None:
            person["names"] = [
                {
                    "givenName": given_name or self._get(current, ["names", 0, "givenName"]),
                    "familyName": family_name or self._get(current, ["names", 0, "familyName"]),
                }
            ]

        # Email
        if email is not None:
            person["emailAddresses"] = [{"value": email}]

        # Phone
        if phone is not None:
            person["phoneNumbers"] = [{"value": phone}]

        # Birthday
        if birthday is not None:
            year, month, day = self._parse_birthday(birthday)
            bday: Dict[str, Any] = {"date": {"month": month, "day": day}}
            if year is not None:
                bday["date"]["year"] = year
            person["birthdays"] = [bday]

        # Photo: If provided, attempt to update via the People API photo endpoint.
        # This is executed after base field updates below to ensure ETag stays valid.

        # Note / biography
        if note is not None:
            person["biographies"] = [{"value": note}]

        # Determine update fields mask
        update_fields: List[str] = []
        for key, mask in (
            ("names", "names"),
            ("emailAddresses", "emailAddresses"),
            ("phoneNumbers", "phoneNumbers"),
            ("birthdays", "birthdays"),
            ("biographies", "biographies"),
        ):
            if key in person:
                update_fields.append(mask)

        if not update_fields and photo_url is None:
            # Nothing to update
            return current

        params = {"updatePersonFields": ",".join(update_fields)}
        url = f"{PEOPLE_BASE}/{resource_name}:updateContact"
        updated = current
        if update_fields:
            resp = self.session.patch(url, params=params, json=person, timeout=20)
            if not resp.ok:
                raise RuntimeError(f"updateContact failed: {resp.status_code} {resp.text}")
            updated = resp.json()

        if photo_url is not None:
            self.update_contact_photo(resource_name, photo_url)

        return updated

    def list_all_connections(self, page_size: int = 500) -> Iterable[Dict[str, Any]]:
        """Iterate over all connections for people/me with selected fields."""
        params = {
            "resourceName": "people/me",
            "pageSize": page_size,
            "personFields": self._read_mask(
                [
                    "names",
                    "emailAddresses",
                    "phoneNumbers",
                    "photos",
                    "birthdays",
                    "organizations",
                    "biographies",
                ]
            ),
        }
        url = f"{PEOPLE_BASE}/people/me/connections"
        page_token: Optional[str] = None
        while True:
            q = dict(params)
            if page_token:
                q["pageToken"] = page_token
            resp = self.session.get(url, params=q, timeout=30)
            if not resp.ok:
                raise RuntimeError(f"list connections failed: {resp.status_code} {resp.text}")
            data = resp.json()
            for person in (data.get("connections", []) or []):
                yield person
            page_token = data.get("nextPageToken")
            if not page_token:
                break

    def update_contact_photo(self, resource_name: str, photo_url: str) -> Dict[str, Any]:
        """Update a contact's photo from a provided URL using updateContactPhoto.

        Note: The URL must be publicly accessible. If the People API rejects the
        image (size/format), an error is raised.
        """
        if not resource_name:
            raise ValueError("resource_name is required")
        if not photo_url:
            raise ValueError("photo_url is required")
        # Fetch image
        img = requests.get(photo_url, timeout=30)
        if not img.ok:
            raise RuntimeError(f"Failed to fetch photo from URL: {img.status_code}")
        import base64

        photo_b64 = base64.b64encode(img.content).decode("ascii")
        url = f"{PEOPLE_BASE}/{resource_name}:updateContactPhoto"
        payload = {"photoBytes": photo_b64}
        resp = self.session.post(url, json=payload, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"updateContactPhoto failed: {resp.status_code} {resp.text}")
        return resp.json()

    # ------------------------
    # Utilities
    # ------------------------
    @staticmethod
    def _parse_birthday(s: str) -> Tuple[Optional[int], int, int]:
        """Parse an ISO-like birthday string.

        Accepts yyyy-mm-dd or --mm-dd (no year), returning (year | None, month, day).
        """
        s = s.strip()
        if s.startswith("--"):
            month, day = map(int, s[2:].split("-", 1))
            return None, month, day
        year, month, day = map(int, s.split("-", 2))
        return year, month, day

    @staticmethod
    def _get(d: Dict[str, Any], path: List[Any]) -> Any:
        cur: Any = d
        for k in path:
            if isinstance(k, int):
                if not isinstance(cur, list) or k >= len(cur):
                    return None
                cur = cur[k]
            else:
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(k)
            if cur is None:
                return None
        return cur

    @staticmethod
    def to_csv_row(person: Dict[str, Any]) -> List[str]:
        """Convert a People API person object to a CSV row with stable columns."""
        names = person.get("names", [])
        given = names[0].get("givenName") if names else ""
        family = names[0].get("familyName") if names else ""
        emails = ";".join([e.get("value", "") for e in person.get("emailAddresses", [])])
        phones = ";".join([p.get("value", "") for p in person.get("phoneNumbers", [])])
        orgs = person.get("organizations", [])
        org_name = orgs[0].get("name") if orgs else ""
        org_title = orgs[0].get("title") if orgs else ""
        bdays = person.get("birthdays", [])
        birthday = ""
        if bdays:
            date = bdays[0].get("date", {})
            y = date.get("year")
            m = date.get("month")
            d = date.get("day")
            if y:
                birthday = f"{y:04d}-{m:02d}-{d:02d}"
            else:
                birthday = f"--{m:02d}-{d:02d}"
        photos = person.get("photos", [])
        photo_url = photos[0].get("url") if photos else ""
        resource_name = person.get("resourceName", "")
        bio = person.get("biographies", [{}])[0].get("value", "")
        return [
            given,
            family,
            emails,
            phones,
            org_name,
            org_title,
            birthday,
            photo_url,
            resource_name,
            bio,
        ]
