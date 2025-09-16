import csv
import datetime as dt
import io
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from toolstore_client import ToolStoreClient
from google_contacts import GooglePeopleClient

# MCP server library (Model Context Protocol)
from mcp.server import Server
from mcp.server.stdio import run
from mcp.types import TextContent


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO))


def _people_client(ts: ToolStoreClient) -> GooglePeopleClient:
    """Instantiate a People API client with a valid access token from Tool Store data."""
    token = ts.get_oauth_access_token("google")
    return GooglePeopleClient(token)


def _csv_bytes_from_people(people: List[Dict[str, Any]]) -> bytes:
    """Create CSV bytes from a list of People API person objects."""
    headers = [
        "given_name",
        "family_name",
        "emails",
        "phones",
        "organization",
        "title",
        "birthday",
        "photo_url",
        "resource_name",
        "notes",
    ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    from google_contacts import GooglePeopleClient as GPC

    for p in people:
        writer.writerow(GPC.to_csv_row(p))
    return buf.getvalue().encode("utf-8")


def _vcf_bytes_from_people(people: List[Dict[str, Any]]) -> bytes:
    """Create VCF (vCard 3.0) bytes from a list of People API person objects."""
    import vobject

    cards: List[str] = []
    for person in people:
        v = vobject.vCard()
        names = person.get("names", [])
        given = names[0].get("givenName") if names else ""
        family = names[0].get("familyName") if names else ""
        fn = (given + " " + family).strip() or given or family
        v.add('n'); v.n.value = vobject.vcard.Name(family=family or '', given=given or '')
        v.add('fn'); v.fn.value = fn or 'Unnamed'
        for e in person.get("emailAddresses", []) or []:
            if e.get("value"):
                v.add('email'); v.email.type_param = 'INTERNET'; v.email.value = e['value']
        for p in person.get("phoneNumbers", []) or []:
            if p.get("value"):
                v.add('tel'); v.tel.type_param = 'CELL'; v.tel.value = p['value']
        orgs = person.get("organizations", []) or []
        if orgs:
            org = orgs[0]
            if org.get("name"):
                v.add('org'); v.org.value = [org['name']]
            if org.get("title"):
                v.add('title'); v.title.value = org['title']
        bdays = person.get("birthdays", []) or []
        if bdays:
            date = bdays[0].get("date", {})
            y = date.get("year"); m = date.get("month"); d = date.get("day")
            if m and d:
                if y:
                    v.add('bday'); v.bday.value = f"{y:04d}-{m:02d}-{d:02d}"
                else:
                    v.add('bday'); v.bday.value = f"--{m:02d}-{d:02d}"
        photos = person.get("photos", []) or []
        if photos and photos[0].get("url"):
            v.add('photo'); v.photo.value = photos[0]['url']; v.photo.type_param = 'URI'
        cards.append(v.serialize())
    text = "".join(cards)
    return text.encode('utf-8')


def _download_text_from_url(url: str) -> str:
    import requests
    resp = requests.get(url, timeout=60)
    if not resp.ok:
        raise RuntimeError(f"Failed to download file: {resp.status_code}")
    # Try utf-8 fallback to latin-1
    try:
        return resp.content.decode(resp.encoding or 'utf-8')
    except Exception:
        return resp.content.decode('latin-1')


def create_server() -> Server:
    """Create the MCP server and register tools for Google Contacts management."""
    load_dotenv()
    _setup_logging()
    server = Server("google-contacts")

    ts = ToolStoreClient()

    @server.tool()
    def create_contact(
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        birthday: Optional[str] = None,
        photo_url: Optional[str] = None,
        note: Optional[str] = None,
    ) -> List[TextContent]:
        """Create a new contact with optional fields and photo."""
        client = _people_client(ts)
        created = client.create_contact(
            given_name=given_name,
            family_name=family_name,
            email=email,
            phone=phone,
            birthday=birthday,
            photo_url=photo_url,
            note=note,
        )
        return [TextContent(type="text", text=str(created))]

    @server.tool()
    def search_contacts(query: str, page_size: int = 50, page_token: Optional[str] = None) -> List[TextContent]:
        """Search contacts by text query over names, emails, and phones.

        Returns a JSON listing of matches as text content.
        """
        client = _people_client(ts)
        data = client.search_contacts(query=query, page_size=page_size, page_token=page_token)
        return [TextContent(type="text", text=str(data))]

    @server.tool()
    def get_contact_details(resource_name: str) -> List[TextContent]:
        """Get full details for the specified contact resource name."""
        client = _people_client(ts)
        data = client.get_contact(resource_name)
        return [TextContent(type="text", text=str(data))]

    @server.tool()
    def update_contact(
        resource_name: str,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        birthday: Optional[str] = None,
        photo_url: Optional[str] = None,
        note: Optional[str] = None,
    ) -> List[TextContent]:
        """Update selected fields for a contact. Fields not provided are left unchanged."""
        client = _people_client(ts)
        updated = client.update_contact(
            resource_name=resource_name,
            given_name=given_name,
            family_name=family_name,
            email=email,
            phone=phone,
            birthday=birthday,
            photo_url=photo_url,
            note=note,
        )
        return [TextContent(type="text", text=str(updated))]

    @server.tool()
    def delete_contact(resource_name: str) -> List[TextContent]:
        """Delete a contact by resource name."""
        client = _people_client(ts)
        client.delete_contact(resource_name)
        return [TextContent(type="text", text="Deleted")]        

    @server.tool()
    def get_todays_birthdays() -> List[TextContent]:
        """Return contacts whose birthdays are today (month/day)."""
        client = _people_client(ts)
        today = (dt.datetime.utcnow()).date()
        month = today.month
        day = today.day
        matches: List[Dict[str, Any]] = []
        for person in client.list_all_connections():
            bdays = person.get("birthdays", [])
            if not bdays:
                continue
            date = bdays[0].get("date", {})
            m = date.get("month")
            d = date.get("day")
            if m == month and d == day:
                matches.append(person)
        return [TextContent(type="text", text=str({"count": len(matches), "people": matches}))]

    @server.tool()
    def export_contacts(file_name: Optional[str] = None) -> List[TextContent]:
        """Export all contacts to CSV and upload to Tool Store storage.

        Args:
            file_name: Optional target file name. Defaults to `contacts-export.csv`.

        Returns:
            JSON payload containing storage metadata.
        """
        client = _people_client(ts)
        people: List[Dict[str, Any]] = list(client.list_all_connections())
        csv_bytes = _csv_bytes_from_people(people)
        fname = file_name or "contacts-export.csv"
        info = ts.upload_file(file_name=fname, content=csv_bytes, content_type="text/csv")
        return [TextContent(type="text", text=str(info))]

    @server.tool()
    def export_contacts_vcf(file_name: Optional[str] = None) -> List[TextContent]:
        """Export all contacts to a VCF file and upload to Tool Store storage."""
        client = _people_client(ts)
        people: List[Dict[str, Any]] = list(client.list_all_connections())
        vcf_bytes = _vcf_bytes_from_people(people)
        fname = file_name or "contacts-export.vcf"
        info = ts.upload_file(file_name=fname, content=vcf_bytes, content_type="text/vcard")
        return [TextContent(type="text", text=str(info))]

    @server.tool()
    def import_contacts_vcf(
        file_url: Optional[str] = None,
        storage_file_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TextContent]:
        """Import contacts from a VCF file. Provide either a public file_url or a storage_file_name.

        Args:
            file_url: Publicly accessible URL to a .vcf file.
            storage_file_name: Path in Tool Store storage for the current user; the server will resolve a download URL.
            limit: Optional maximum number of vCards to import (useful for testing).
        """
        client = _people_client(ts)
        if bool(file_url) == bool(storage_file_name):
            raise RuntimeError("Provide exactly one of file_url or storage_file_name")
        if storage_file_name:
            resolved = ts.get_download_url(storage_file_name)
            if not resolved:
                raise RuntimeError("Could not resolve download URL for storage_file_name")
            file_url = resolved
        assert file_url is not None
        text = _download_text_from_url(file_url)

        import vobject
        created: List[str] = []
        count = 0
        for v in vobject.readComponents(io.StringIO(text)):
            if limit is not None and count >= limit:
                break
            count += 1
            # Extract fields
            given = family = email = phone = note = None
            bday = None
            photo_url = None
            try:
                if hasattr(v, 'n') and v.n.value:
                    family = getattr(v.n.value, 'family', None)
                    given = getattr(v.n.value, 'given', None)
                if hasattr(v, 'email'):
                    # v.email can be a list or single; v.contents['email'] is canonical
                    emails = [c.value for c in v.contents.get('email', []) if getattr(c, 'value', None)]
                    email = emails[0] if emails else None
                if hasattr(v, 'tel'):
                    tels = [c.value for c in v.contents.get('tel', []) if getattr(c, 'value', None)]
                    phone = tels[0] if tels else None
                if hasattr(v, 'bday') and getattr(v.bday, 'value', None):
                    b = v.bday.value
                    if hasattr(b, 'year') and hasattr(b, 'month') and hasattr(b, 'day'):
                        if b.year:
                            bday = f"{b.year:04d}-{b.month:02d}-{b.day:02d}"
                        else:
                            bday = f"--{b.month:02d}-{b.day:02d}"
                    else:
                        bday = str(b)
                if hasattr(v, 'photo') and getattr(v.photo, 'value', None):
                    # If the PHOTO is a URI, use it; skip embedded/base64
                    val = v.photo.value
                    if isinstance(val, str) and val.lower().startswith(('http://','https://')):
                        photo_url = val
                if hasattr(v, 'note') and getattr(v.note, 'value', None):
                    note = str(v.note.value)
            except Exception:
                pass

            res = client.create_contact(
                given_name=given,
                family_name=family,
                email=email,
                phone=phone,
                birthday=bday,
                photo_url=photo_url,
                note=note,
            )
            rn = res.get('resourceName')
            if rn:
                created.append(rn)

        return [TextContent(type="text", text=str({"created": len(created), "resource_names": created}))]

    return server


def main() -> None:
    server = create_server()
    run(server)


if __name__ == "__main__":
    main()
