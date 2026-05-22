import os
import resend

ADMIN_EMAIL = os.getenv("ALERT_EMAIL", "bikram6086@gmail.com")
FROM_ADDRESS = "alerts@fundguldasta.com"


def _client():
    key = os.getenv("RESEND_API_KEY", "")
    if not key:
        return None
    resend.api_key = key
    return resend


def send_pipeline_failure_alert(pipeline_name: str, error_detail: str):
    """Send email when a nightly pipeline fails."""
    client = _client()
    if not client:
        print(f"[ALERT] No RESEND_API_KEY — skipping email for {pipeline_name} failure")
        return
    try:
        client.Emails.send({
            "from": FROM_ADDRESS,
            "to": [ADMIN_EMAIL],
            "subject": f"[FundGuldasta] Pipeline failure: {pipeline_name}",
            "html": f"""
<div style="font-family:sans-serif;max-width:600px">
  <h2 style="color:#D4AF37">Pipeline Failure Alert</h2>
  <p><strong>Pipeline:</strong> {pipeline_name}</p>
  <p><strong>Error:</strong></p>
  <pre style="background:#f5f5f5;padding:12px;border-radius:6px;font-size:13px">{error_detail[:1000]}</pre>
  <p style="color:#888;font-size:12px">FundGuldasta automated alert · fundguldasta.com</p>
</div>""",
        })
        print(f"[ALERT] Pipeline failure email sent for {pipeline_name}")
    except Exception as e:
        print(f"[ALERT] Failed to send email: {e}")


def send_cache_stale_alert(age_hours: float):
    """Send email when bouquet cache is stale beyond threshold."""
    client = _client()
    if not client:
        return
    try:
        client.Emails.send({
            "from": FROM_ADDRESS,
            "to": [ADMIN_EMAIL],
            "subject": "[FundGuldasta] Bouquet cache is stale",
            "html": f"""
<div style="font-family:sans-serif;max-width:600px">
  <h2 style="color:#D4AF37">Cache Stale Alert</h2>
  <p>The bouquet cache has not been refreshed for <strong>{age_hours:.0f} hours</strong>.</p>
  <p>Auto-remediation has been triggered. If this alert repeats, investigate the precompute pipeline.</p>
  <p style="color:#888;font-size:12px">FundGuldasta automated alert · fundguldasta.com</p>
</div>""",
        })
        print(f"[ALERT] Cache stale email sent ({age_hours:.0f}h)")
    except Exception as e:
        print(f"[ALERT] Failed to send cache stale email: {e}")


def send_manager_change_alert(to_email: str, display_name: str, changes: list):
    """Notify a user when a fund manager changes in one of their saved bouquets."""
    client = _client()
    if not client:
        print(f"[ALERT] No RESEND_API_KEY — skipping manager change alert for {to_email}")
        return
    rows = "".join(
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #eee'>{c['fund_name']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #eee;color:#888'>{c['old_manager']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #eee;color:#333;font-weight:600'>{c['new_manager']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #eee;color:#888;font-size:11px'>{c['detected_date']}</td></tr>"
        for c in changes
    )
    try:
        client.Emails.send({
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": "[FundGuldasta] Manager change detected in your saved bouquet",
            "html": f"""
<div style="font-family:sans-serif;max-width:600px">
  <h2 style="color:#D4AF37">Manager Change Alert</h2>
  <p>Hi {display_name},</p>
  <p>A fund manager change has been detected for one or more funds in your saved FundGuldasta bouquets.</p>
  <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:13px">
    <thead><tr style="background:#f9f9f9">
      <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #D4AF37">Fund</th>
      <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #D4AF37">Previous Manager</th>
      <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #D4AF37">New Manager</th>
      <th style="padding:8px 12px;text-align:left;border-bottom:2px solid #D4AF37">Date</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="font-size:13px;color:#555">Manager changes can impact a fund's style consistency and performance. Log in to FundGuldasta to review your bouquet and decide whether to re-evaluate.</p>
  <p><a href="https://fundguldasta.com" style="display:inline-block;background:#D4AF37;color:#000;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:600;font-size:13px">Review at FundGuldasta</a></p>
  <p style="color:#888;font-size:11px">You received this because you enabled manager change alerts. Manage alerts in your account settings.</p>
  <p style="color:#888;font-size:11px">FundGuldasta · Research &amp; Education Only · Not Investment Advice</p>
</div>""",
        })
        print(f"[ALERT] Manager change alert sent to {to_email}")
    except Exception as e:
        print(f"[ALERT] Failed to send manager change alert: {e}")


def send_monthly_digest(to_email: str, display_name: str, saved_bouquets: list):
    """Send monthly performance digest to an opted-in user."""
    from datetime import datetime
    client = _client()
    if not client:
        print(f"[ALERT] No RESEND_API_KEY — skipping monthly digest for {to_email}")
        return
    month_label = datetime.now().strftime("%B %Y")
    rows = "".join(
        f"<tr>"
        f"<td style='padding:10px 12px;border-bottom:1px solid #f0f0f0;font-weight:500'>{b.get('name','—')}</td>"
        f"<td style='padding:10px 12px;border-bottom:1px solid #f0f0f0;color:#888;font-size:12px'>{b.get('archetype_id','').title()}</td>"
        f"<td style='padding:10px 12px;border-bottom:1px solid #f0f0f0;color:#D4AF37;font-size:12px'>{b.get('target_cagr','—')}% target</td>"
        f"<td style='padding:10px 12px;border-bottom:1px solid #f0f0f0;color:#888;font-size:11px'>{b.get('horizon_years','—')}yr horizon</td>"
        f"</tr>"
        for b in saved_bouquets
    )
    try:
        client.Emails.send({
            "from": FROM_ADDRESS,
            "to": [to_email],
            "subject": f"[FundGuldasta] Your Monthly Digest — {month_label}",
            "html": f"""
<div style="font-family:sans-serif;max-width:600px">
  <h2 style="color:#D4AF37">Monthly Research Digest</h2>
  <p style="color:#888;margin-top:-8px">{month_label}</p>
  <p>Hi {display_name},</p>
  <p>Here's a summary of your saved FundGuldasta bouquets:</p>
  <table style="width:100%;border-collapse:collapse;margin:16px 0;font-size:13px">
    <thead><tr style="background:#f9f9f9">
      <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #D4AF37">Bouquet Name</th>
      <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #D4AF37">Archetype</th>
      <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #D4AF37">CAGR Target</th>
      <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #D4AF37">Horizon</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="font-size:13px;color:#555">Visit FundGuldasta to see the latest confidence scores, run a historical backtest, and explore the full analysis for each bouquet.</p>
  <p><a href="https://fundguldasta.com" style="display:inline-block;background:#D4AF37;color:#000;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:600;font-size:13px">Open FundGuldasta</a></p>
  <p style="color:#888;font-size:11px">You received this because you enabled monthly digest. Manage preferences in your account.</p>
  <p style="color:#888;font-size:11px">FundGuldasta · Research &amp; Education Only · Not Investment Advice</p>
</div>""",
        })
        print(f"[ALERT] Monthly digest sent to {to_email}")
    except Exception as e:
        print(f"[ALERT] Failed to send monthly digest: {e}")
