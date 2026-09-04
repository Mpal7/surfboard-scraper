# Email Notification System

We decided to implement a per-recipient email notification system for surfboard ads. Each Recipient has their own Filter configuration persisted in a JSON file (`email_config.json`), managed via a CRUD API at `/email-config`. Emails are sent synchronously via Gmail SMTP, with the option to auto-trigger after each Refresh.

## Key decisions

- **JSON file over database table** for config persistence. Simpler, no schema changes, easy to inspect manually. Trade-off: no concurrent write protection, but this is a single-user system.
- **Per-recipient Filters** rather than global filters. Different recipients may be looking for different types of boards.
- **Per-recipient `include_sent` toggle**. By default only unsent ads are emailed, but recipients can opt in to receive already-sent ads.
- **Per-recipient `auto_send` toggle** with a global `auto_send_after_refresh` master switch. Both must be true for auto-send to trigger after a Refresh.
- **Synchronous sending** over background tasks. Simpler implementation, acceptable latency for a small recipient list. No need for status polling.
- **HTML email** with a table of surfboard info and a "View Ad" link. No images to keep emails lightweight.
- **Empty emails sent** when no ads match a recipient's filters (subject: "No New Surfboard Ads"). Keeps recipients informed that the system is working.
