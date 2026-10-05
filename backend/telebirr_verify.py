# telebirr_verify.py
# ============================================
# HABESHA BET - TELEBIRR ONLINE RECEIPT VERIFICATION
# ============================================

import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger("habesha_bet")

TELEBIRR_RECEIPT_URL = "https://transactioninfo.ethiotelecom.et/receipt/{receipt_no}"

_CIRCUIT_BREAKER_WINDOW = 60
_CIRCUIT_BREAKER_THRESHOLD = 5
_CIRCUIT_BREAKER_COOLDOWN = 120

_failure_timestamps = []
_circuit_open_until = 0.0


def _update_circuit_breaker(success: bool):
    global _failure_timestamps, _circuit_open_until
    now = time.time()
    if success:
        _failure_timestamps = []
        _circuit_open_until = 0.0
        return
    _failure_timestamps.append(now)
    cutoff = now - _CIRCUIT_BREAKER_WINDOW
    _failure_timestamps = [t for t in _failure_timestamps if t >= cutoff]
    if len(_failure_timestamps) >= _CIRCUIT_BREAKER_THRESHOLD:
        _circuit_open_until = now + _CIRCUIT_BREAKER_COOLDOWN
        logger.warning("[telebirr_verify] circuit breaker open until %s", _circuit_open_until)


def _is_circuit_open() -> bool:
    return time.time() < _circuit_open_until


_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; HabeshaBet/1.0)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en,am;q=0.9",
})


def verify_receipt_online(receipt_no: str, timeout: int = 10) -> dict:
    """
    Fetch and verify a Telebirr receipt online.

    Returns dict with:
        ok: bool
        amount: float (if ok)
        recipient_name: str (if ok)
        recipient_phone_last4: str (if ok)
        reference: str (if ok)
        timestamp: str (if ok)
        error: str (if not ok)
    """
    if not receipt_no or not re.match(r'^[A-Za-z0-9]{8,20}$', receipt_no):
        return {"ok": False, "error": "invalid_receipt_number"}

    if _is_circuit_open():
        return {"ok": False, "error": "receipt_site_circuit_open"}

    url = TELEBIRR_RECEIPT_URL.format(receipt_no=receipt_no.upper())

    max_retries = 2
    backoff = 1.0
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = _session.get(url, timeout=(timeout, timeout))
            if resp.status_code == 200:
                _update_circuit_breaker(True)
                html = resp.text
                result = parse_receipt_html(html)

                if not result.get("ok"):
                    _update_circuit_breaker(False)
                    return result

                result["reference"] = receipt_no.upper()
                return result

            if resp.status_code == 404:
                _update_circuit_breaker(False)
                return {"ok": False, "error": "receipt_not_found_http_404"}

            last_error = f"receipt_not_found_http_{resp.status_code}"
        except requests.Timeout:
            last_error = "receipt_site_timeout"
        except requests.ConnectionError:
            last_error = "receipt_site_unreachable"
        except Exception as e:
            logger.warning("[telebirr_verify] unexpected error fetching receipt %s: %s", receipt_no, e)
            last_error = "receipt_fetch_error"

        if attempt < max_retries:
            time.sleep(backoff)
            backoff *= 2

    _update_circuit_breaker(False)
    return {"ok": False, "error": last_error}


def parse_receipt_html(html: str) -> dict:
    """
    Parse Telebirr receipt HTML page.
    Extract: amount, recipient name, recipient phone last 4, reference, timestamp.
    Use BeautifulSoup with resilient selectors.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        return {"ok": False, "error": f"html_parse_error: {e}"}

    amount = _extract_amount(soup)
    recipient_name = _extract_recipient_name(soup)
    recipient_phone_last4 = _extract_recipient_phone_last4(soup)
    timestamp = _extract_timestamp(soup)

    if amount is None:
        return {"ok": False, "error": "amount_not_found_on_receipt"}

    return {
        "ok": True,
        "amount": amount,
        "recipient_name": recipient_name or "",
        "recipient_phone_last4": recipient_phone_last4 or "",
        "timestamp": timestamp or "",
    }


def _extract_amount(soup) -> Optional[float]:
    text = soup.get_text(separator=" ", strip=True)
    m = re.search(r'(?:amount|transferred|debit|paid)[\s:]*ETB\s*([\d,]+(?:\.\d{1,2})?)', text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    m = re.search(r'ETB\s*([\d,]+(?:\.\d{1,2})?)', text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _extract_recipient_name(soup) -> Optional[str]:
    text = soup.get_text(separator=" ", strip=True)
    patterns = [
        r'(?:to|recipient|beneficiary)[\s:]*([A-Za-z][A-Za-z\s]{2,40}?)(?:\s*\(|\s*$|\s*–|\s*-)',
        r'Payee[\s:]*([A-Za-z][A-Za-z\s]{2,40}?)(?:\s*\(|\s*$|\s*–|\s*-)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if len(name) >= 2:
                return name
    return None


def _extract_recipient_phone_last4(soup) -> Optional[str]:
    text = soup.get_text(separator=" ", strip=True)
    m = re.search(r'(?:\(|phone[\s:]*|to[\s:]*)(?:2519|09)?\d*\*+(\d{4})(?:\))?', text)
    if m:
        return m.group(1)
    return None


def _extract_timestamp(soup) -> Optional[str]:
    text = soup.get_text(separator=" ", strip=True)
    m = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})', text)
    if m:
        return m.group(1)
    m = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', text)
    if m:
        return m.group(1)
    return None
