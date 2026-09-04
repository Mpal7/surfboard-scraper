from src.models import Ad


def _format_length(ad: Ad) -> str:
    parts = []
    if ad.length_ft:
        parts.append(f"{ad.length_ft}'")
    if ad.length_in:
        parts.append(f'{ad.length_in}"')
    return "".join(parts) if parts else "—"


def _format_dimensions(ad: Ad) -> str:
    length = _format_length(ad)
    width = f'{ad.width_in}"' if ad.width_in else "—"
    thickness = f'{ad.thickness_in}"' if ad.thickness_in else "—"
    return f"{length} × {width} × {thickness}"


def _format_liters(ad: Ad) -> str:
    return f"{ad.liters}L" if ad.liters else "—"


def _format_price(ad: Ad) -> str:
    return f"€{ad.price:,.0f}" if ad.price else "—"


def build_ad_row(ad: Ad) -> str:
    return f"""
    <tr>
      <td style="padding:12px 16px;border-bottom:1px solid #e0e0e0;">
        <div style="font-weight:bold;font-size:15px;color:#333;">{ad.brand or 'Unknown'} — {ad.model or 'Unknown'}</div>
        <div style="font-size:13px;color:#666;margin-top:4px;">
          {_format_price(ad)} &middot; {_format_dimensions(ad)} &middot; {_format_liters(ad)} &middot; {ad.location or '—'}
        </div>
        <a href="{ad.link}" style="display:inline-block;margin-top:6px;font-size:13px;color:#1a73e8;text-decoration:none;">View Ad →</a>
      </td>
    </tr>"""


def build_email_html(ads: list[Ad]) -> str:
    if not ads:
        return """
    <tr>
      <td style="padding:16px;text-align:center;color:#666;">
        No surfboards matching your criteria were found.
      </td>
    </tr>"""

    rows = "".join(build_ad_row(ad) for ad in ads)
    return f"""
    <tr>
      <td style="padding:16px 16px 8px;">
        <div style="font-size:13px;color:#666;">{len(ads)} surfboard{'s' if len(ads) != 1 else ''} found</div>
      </td>
    </tr>
    {rows}"""


def build_full_email(ads: list[Ad]) -> tuple[str, str]:
    count = len(ads)
    if count > 0:
        subject = f"{count} New Surfboard Ad{'s' if count != 1 else ''}"
    else:
        subject = "No New Surfboard Ads"

    body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:20px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
          <tr>
            <td style="background:#1a73e8;padding:16px 20px;">
              <div style="font-size:18px;font-weight:bold;color:#fff;">Surfboard Alerts</div>
            </td>
          </tr>
          {build_email_html(ads)}
          <tr>
            <td style="padding:12px 16px;text-align:center;font-size:11px;color:#999;border-top:1px solid #e0e0e0;">
              Scraped from Subito.it
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return subject, body
