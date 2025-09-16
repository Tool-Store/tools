AI Usage Guidance

Purpose
- This tool manages Google Contacts. Use it to search, inspect, update, delete contacts, list today’s birthdays, and export all contacts to CSV stored in Tool Store Storage.

General Guidance
- Prefer `search_contacts` first to locate resource names (e.g., `people/c123`).
- Use `get_contact_details` to retrieve complete information for a specific contact.
- When updating, send only fields that need changes; the tool merges them with existing data.
- Resource names are required for `get_contact_details`, `update_contact`, and `delete_contact`.
- `export_contacts` will upload a CSV to Tool Store storage and return its storage path and download info.

Actions
- create contact: Provide any of `given_name`, `family_name`, `email`, `phone`, `birthday`, `photo_url`, `note`.
- search contacts: Provide `query` text; optional `page_size` and `page_token` for pagination.
- get contact details: Provide `resource_name`.
- update contact: Provide `resource_name` plus any fields to change.
- delete contact: Provide `resource_name`.
- get todays birthdays: No input parameters; returns contacts with birthdays today.
- export contacts: Optional `file_name` (default `contacts-export.csv`).
- export contacts vcf: Optional `file_name` (default `contacts-export.vcf`).
- import contacts vcf: Provide `file_url` for a public VCF file, or `storage_file_name` to import from Tool Store storage; optional `limit`.

Authentication
- If the action fails due to missing/expired credentials, the tool attempts an automatic refresh via the Tool Store endpoint when configured. Otherwise, prompt the user to run activation and re-connect their Google account.
