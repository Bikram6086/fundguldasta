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
