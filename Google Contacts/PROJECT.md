# PROJECT.md (Tool Definition)

Google Contacts is an MCP tool that provides contact management capabilities through the Google People API. It allows users to create, read, update, delete, search, and export contacts, as well as retrieve birthday information.

This tool runs as an MCP server and integrates with the Tool Store platform for authentication, user data storage, and file management.

## It should

- Allow users to create, search, read, update, and delete Google Contacts.
- Retrieve today's birthdays from Google Contacts.
- Export contacts to CSV or VCF formats.
- Import contacts from VCF files via public URLs or Tool Store storage.
- Upload exported files to Tool Store storage.
- Use OAuth-based activation to connect a user's Google account securely.

## Capabilities

### MCP Functions
- `create_contact` - Create a new contact with name, email, phone, and optional fields
- `search_contacts` - Search contacts by query string with optional field filters
- `get_contact` - Retrieve a specific contact by resource name
- `update_contact` - Update an existing contact's information
- `delete_contact` - Remove a contact by resource name
- `get_todays_birthdays` - List contacts whose birthdays fall on the current date
- `export_contacts_csv` - Export all contacts to CSV format, upload to Tool Store storage
- `export_contacts_vcf` - Export all contacts to VCF format, upload to Tool Store storage
- `import_contacts_vcf` - Import contacts from a VCF file via URL or storage path

### MCP Resources
- `contacts://birthdays/today` - Resource providing today's birthday contacts
- `contacts://list` - Resource listing all contacts

## Technical stack

- Python 3.x runtime
- MCP Python SDK (FastMCP server)
- Google People API v1
- Tool Store Developer API for user data and storage
- HTTP/REST clients via `requests` library

## Activation requirements

- OAuth 2.0 flow for Google account authorization
- Required scopes: `https://www.googleapis.com/auth/contacts`
- Per-user OAuth tokens stored in Tool Store user data

## Configuration

- `tool-data.yaml` - MCP contract, metadata, activation steps, pricing
- `.env` / `.env.example` - Environment variables for local development
- `Dockerfile` - Container runtime definition

## Quality constraints

- Validate all user inputs before Google API calls
- Handle OAuth token refresh automatically via Tool Store platform
- Log errors explicitly with actionable messages
- Keep user data and storage operations within Tool Store platform boundaries
- Fail fast on missing credentials or invalid activation state

## Open questions

- Additional export formats beyond CSV/VCF
- Bulk contact operations performance limits
- Extended contact fields support (addresses, organizations, etc.)
