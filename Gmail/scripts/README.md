# Gmail Manual Verification Scripts

End-to-end verification scripts that exercise every public method on `GmailClient`
against a real Google account. Each script is self-contained, takes a Google
OAuth access token via the `GOOGLE_ACCESS_TOKEN` env var, and prints PASS/FAIL
per assertion.

## Prerequisites

1. Activated venv with `mcp`, `python-dotenv`, `requests` installed.
2. A Google access token with scope `https://www.googleapis.com/auth/gmail.modify`.
   Get one from [Google's OAuth 2.0 Playground](https://developers.google.com/oauthplayground/):
   - Step 1: select **Gmail API v1** → `gmail.modify` → Authorize APIs → sign in → Allow.
   - Step 2: click **Exchange authorization code for tokens**.
   - Copy the **Access token** value (starts with `ya29....`).

## Configuration

Two env vars are honored:

| Variable | Default | Purpose |
|---|---|---|
| `GOOGLE_ACCESS_TOKEN` | required | The Gmail access token. Token never lives in a file. |
| `GMAIL_TEST_RECIPIENT` | `lilua.brainerhub@gmail.com` | Address used by send/forward tests. |
| `GMAIL_TEST_STATE_FILE` | `/tmp/gmail_test_state.json` | Shared state between scripts (e.g. message ids). |

## Recommended run order

Run from the `Gmail/` folder so module imports resolve:

```bash
cd "/home/python/Desktop/toolstore/tools/Gmail"
export GOOGLE_ACCESS_TOKEN="ya29...."

python scripts/01_read_only.py
python scripts/02_drafts_lifecycle.py
python scripts/03_labels_lifecycle.py
python scripts/04_send.py            # sends a real email
python scripts/05_reply_forward.py   # sends 2 real emails (reply + forward)
python scripts/06_trash_cycle.py     # trashes then untrashes the test message
python scripts/07_attachment.py      # downloads an attachment to /tmp/
```

## Safety summary

| Script | Reads | Writes | Side effects |
|---|---|---|---|
| `01_read_only.py` | yes | no | none |
| `02_drafts_lifecycle.py` | yes | yes | Creates draft, then deletes it. Net zero. |
| `03_labels_lifecycle.py` | yes | yes | Creates label `GmailToolTest_<ts>`, applies to one message, removes, deletes label. Net zero. |
| `04_send.py` | yes | yes | **Sends one real email** to `GMAIL_TEST_RECIPIENT`. |
| `05_reply_forward.py` | yes | yes | **Sends two real emails** (reply to self, forward to `GMAIL_TEST_RECIPIENT`). |
| `06_trash_cycle.py` | yes | yes | Trashes then untrashes the message from step 04. Net zero. |
| `07_attachment.py` | yes | no | Saves attachment bytes to `/tmp/`. No Gmail writes. |

## Skipped on purpose

| Tool | Why |
|---|---|
| `delete_message` | Requires `https://mail.google.com/` scope; our `gmail.modify` scope returns 403. Documented behaviour. |
| `send_draft` | Already covered by `04_send.py` for the actual send path. |

## Tokens expire

Google access tokens last ~1 hour. If a script returns `401 Invalid Credentials`,
mint a fresh token from the OAuth Playground and rerun.
