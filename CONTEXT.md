# Surfboard Scraper

A system that scrapes surfboard listings from Subito.it, stores them in a database, and notifies recipients via email when new boards matching their preferences are found.

## Language

**Ad**:
A surfboard listing scraped from Subito.it. Has physical attributes (brand, model, dimensions, liters, price), location, a source link, and state flags (is_active, is_visible, is_mail_sent).
_Avoid_: Listing, post, entry

**Active Ad**:
An Ad whose source link is still live on Subito.it (`is_active=True`). Checked periodically by the maintenance script.
_Avoid_: Live ad, valid ad

**Visible Ad**:
An Ad shown in the frontend (`is_visible=True`). An ad can be active but hidden from the UI.
_Avoid_: Shown ad, displayed ad

**Recipient**:
A person configured to receive email notifications. Each recipient has an email address, a set of Filters, and toggles for include_sent and auto_send.
_Avoid_: User, subscriber

**Filter**:
A set of criteria (brand, price range, dimensions, liters range) applied to Ads to narrow which ones a Recipient receives. Each Recipient has their own Filter.
_Avoid_: Criteria, preferences, query

**Refresh**:
The act of re-scraping Subito.it for new listings. Triggered via POST /refresh. Has a cooldown period to avoid excessive requests.
_Avoid_: Scrape, update, sync

**Mail Sent**:
The state of an Ad (`is_mail_sent=True`) indicating at least one Recipient has been notified about it. Prevents duplicate notifications unless a Recipient opts in via `include_sent`.
_Avoid_: Notified, emailed

**Email Config**:
The persisted JSON file (`email_config.json`) defining global email settings, the list of Recipients, and their Filters. Managed via the `/email-config` API.
_Avoid_: Settings, preferences

## Example dialogue

> **Dev**: "When we refresh, do we send emails for all ads or only new ones?"
> **Domain expert**: "Only new ones by default — ads where mail_sent is false. But some recipients want the full list every time, so they set include_sent to true."
> **Dev**: "And if an ad becomes inactive after we emailed it?"
> **Domain expert**: "Doesn't matter — is_mail_sent stays true. We don't un-send emails."
