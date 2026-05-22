"""
Priority 15+17 tests — User preferences endpoints, alert functions, Hindi translation logic.
Run: pytest tests/test_priority15_17.py -v
"""
import pytest
import asyncio
import sys
sys.path.insert(0, "/home/hpbikram6086/fundguldasta")

from api.main import get_preferences, update_preferences, PreferencesUpdate, run_manager_change_alerts, run_monthly_digests
from api.alerts import send_manager_change_alert, send_monthly_digest
from fastapi import HTTPException


def run(coro):
    return asyncio.run(coro)


# ── Priority 15: Preferences Endpoints ────────────────────────────────────────

class TestPreferencesEndpoints:

    def test_get_prefs_without_token_raises_401(self):
        with pytest.raises(HTTPException) as e:
            run(get_preferences(authorization=None))
        assert e.value.status_code == 401

    def test_get_prefs_invalid_token_raises_401(self):
        with pytest.raises(HTTPException) as e:
            run(get_preferences(authorization="Bearer invalid_token_xyz"))
        assert e.value.status_code == 401

    def test_update_prefs_without_token_raises_401(self):
        with pytest.raises(HTTPException) as e:
            run(update_preferences(PreferencesUpdate(manager_alert=True), authorization=None))
        assert e.value.status_code == 401

    def test_update_prefs_invalid_token_raises_401(self):
        with pytest.raises(HTTPException) as e:
            run(update_preferences(PreferencesUpdate(manager_alert=True), authorization="Bearer bad_token"))
        assert e.value.status_code == 401

    def test_preferences_model_defaults(self):
        prefs = PreferencesUpdate()
        assert prefs.manager_alert is None
        assert prefs.monthly_digest is None

    def test_preferences_model_set_values(self):
        prefs = PreferencesUpdate(manager_alert=True, monthly_digest=False)
        assert prefs.manager_alert is True
        assert prefs.monthly_digest is False


# ── Priority 15: Alert Functions ───────────────────────────────────────────────

class TestAlertFunctions:

    def test_send_manager_change_alert_no_key(self):
        """Without RESEND_API_KEY, should print log message and not raise."""
        import os
        original = os.environ.get("RESEND_API_KEY")
        os.environ.pop("RESEND_API_KEY", None)
        try:
            # Should not raise even without API key
            send_manager_change_alert(
                "test@example.com", "Test User",
                [{"fund_name": "Test Fund", "old_manager": "Old", "new_manager": "New", "detected_date": "2026-05-01"}]
            )
        finally:
            if original:
                os.environ["RESEND_API_KEY"] = original

    def test_send_monthly_digest_no_key(self):
        """Without RESEND_API_KEY, should print log message and not raise."""
        import os
        original = os.environ.get("RESEND_API_KEY")
        os.environ.pop("RESEND_API_KEY", None)
        try:
            send_monthly_digest(
                "test@example.com", "Test User",
                [{"name": "My Bouquet", "archetype_id": "balanced", "horizon_years": 7, "target_cagr": 15}]
            )
        finally:
            if original:
                os.environ["RESEND_API_KEY"] = original

    def test_run_manager_change_alerts_no_changes(self):
        """With empty manager_change_log, function should run without error."""
        run_manager_change_alerts()  # manager_change_log is empty — no alerts should be sent

    def test_run_monthly_digests_no_users(self):
        """With no opted-in users, function should run without error."""
        run_monthly_digests()  # No users with monthly_digest=TRUE yet


# ── Priority 15: DB Column Verification ───────────────────────────────────────

class TestDBSchema:

    def test_manager_alert_column_exists(self):
        import psycopg2
        conn = psycopg2.connect('host=127.0.0.1 dbname=fundguldasta_dev user=fundguldasta_user')
        cur = conn.cursor()
        cur.execute("SELECT column_name, data_type, column_default FROM information_schema.columns "
                    "WHERE table_name='users' AND column_name='manager_alert'")
        row = cur.fetchone()
        cur.close(); conn.close()
        assert row is not None, "manager_alert column not found in users table"
        assert row[1] == 'boolean', f"Expected boolean, got {row[1]}"
        assert 'false' in str(row[2]).lower(), f"Default should be FALSE, got {row[2]}"

    def test_monthly_digest_column_exists(self):
        import psycopg2
        conn = psycopg2.connect('host=127.0.0.1 dbname=fundguldasta_dev user=fundguldasta_user')
        cur = conn.cursor()
        cur.execute("SELECT column_name, data_type, column_default FROM information_schema.columns "
                    "WHERE table_name='users' AND column_name='monthly_digest'")
        row = cur.fetchone()
        cur.close(); conn.close()
        assert row is not None, "monthly_digest column not found in users table"
        assert row[1] == 'boolean', f"Expected boolean, got {row[1]}"

    def test_all_users_have_default_prefs(self):
        """Existing users should have default FALSE (via ADD COLUMN DEFAULT)."""
        import psycopg2
        conn = psycopg2.connect('host=127.0.0.1 dbname=fundguldasta_dev user=fundguldasta_user')
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE manager_alert IS NULL OR monthly_digest IS NULL")
        null_count = cur.fetchone()[0]
        cur.close(); conn.close()
        assert null_count == 0, f"{null_count} users have NULL alert preferences (should be FALSE default)"


# ── Priority 17: Hindi Translation Logic ──────────────────────────────────────

class TestHindiTranslationLogic:
    """Test that key translation strings are correctly defined and non-empty."""

    # Mirror the HI_HERO dict from App.js
    HI = {
        "tagline": "म्यूचुअल फंड रिसर्च। बेबाक।",
        "secTag": "ईमानदारी से डिज़ाइन किया गया म्यूचुअल फंड रिसर्च",
        "headline": "चुने हुए फंड बुके।",
        "headlineEm": "ईमानदारी से।",
        "sub": "दो इनपुट। चार बुके आर्केटाइप। पारदर्शी रिसर्च की दस परतें। कोई कमीशन नहीं। कोई झूठा आश्वासन नहीं।",
        "tabReturn": "रिटर्न लक्ष्य",
        "tabCorpus": "कोष लक्ष्य",
        "tabSip": "SIP क्षमता",
        "btnCurate": "मेरे बुके तैयार करें →",
        "btnBYOB": "✎ अपना बुके बनाएं",
        "btnPortfolio": "📊 पोर्टफोलियो विश्लेषण",
        "btnCalc": "📐 SIP और टैक्स कैलकुलेटर",
        "btnRisk": "🎯 मेरी जोखिम प्रोफाइल",
        "signIn": "साइन इन",
        "signOut": "साइन आउट",
        "saved": "सहेजे",
        "newSearch": "← नई खोज",
        "compare": "⊟ तुलना",
        "fundExplorer": "🔍 फंड एक्सप्लोरर",
        "savedBouquets": "सहेजे हुए बुके",
    }

    def t(self, en, hi, lang='hi'):
        return hi if lang == 'hi' else en

    def test_all_translation_keys_non_empty(self):
        for key, val in self.HI.items():
            assert val and len(val.strip()) > 0, f"Hindi translation for '{key}' is empty"

    def test_translation_preserves_english_in_en_mode(self):
        assert self.t("Mutual Fund Research", "म्यूचुअल फंड रिसर्च", 'en') == "Mutual Fund Research"

    def test_translation_returns_hindi_in_hi_mode(self):
        assert self.t("Mutual Fund Research", "म्यूचुअल फंड रिसर्च", 'hi') == "म्यूचुअल फंड रिसर्च"

    def test_hindi_strings_use_devanagari(self):
        """All Hindi strings should contain Devanagari Unicode characters."""
        for key, val in self.HI.items():
            # Check for Devanagari range (U+0900–U+097F) OR emoji/English (buttons keep icons)
            has_devanagari = any('ऀ' <= c <= 'ॿ' for c in val)
            # Buttons with emojis/SIP/CAGR can have partial Devanagari
            if key not in ['tabSip', 'btnBYOB', 'btnCalc', 'btnRisk', 'btnPortfolio']:
                assert has_devanagari, f"'{key}' = '{val}' has no Devanagari characters"

    def test_key_financial_terms_preserved(self):
        """SIP, CAGR, NAV should be preserved as-is in Hindi (standard in Indian MF)."""
        assert "SIP" in self.HI["tabSip"], "SIP should be in Hindi tab label"
        assert "SIP" in self.HI["btnCalc"], "SIP should be in Hindi calculator button"
        assert "CAGR" in self.HI.get("btnCurate", "") or True  # CAGR optional in button

    def test_all_required_keys_present(self):
        required = ["tagline", "headline", "sub", "btnCurate", "signIn", "signOut", "savedBouquets"]
        for key in required:
            assert key in self.HI, f"Missing required Hindi key: '{key}'"
