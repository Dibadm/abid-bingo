# sms_parser.py
# ============================================
# HABESHA BET - TELEBIRR SMS PARSER
#
# Tested against real Telebirr format:
#
#   "Dear Abdi
#    You have transferred ETB 30.00 to hanan reda (2519****8740) on
#    14/06/2026 20:47:00. Your transaction number is DFE8VVNNIC. The
#    service fee is ETB 0.87 and 15% VAT on the service fee is ETB 0.13.
#    Your current E-Money Account balance is ETB 1,429.52. To download
#    your payment information please click this link:
#    https://transactioninfo.ethiotelecom.et/receipt/DFE8VVNNIC.
#
#    Thank you for using telebirr
#    Ethio telecom"
#
# Fields extracted:
#   amount          -> 30.00  (the transferred amount, NOT fee or balance)
#   recipient_name  -> "hanan reda"
#   recipient_last4 -> "8740"
#   reference       -> "DFE8VVNNIC"
# ============================================

import re


# =====================================================================
# MAIN PARSER
# =====================================================================

def parse_telebirr_sms(sms_text: str) -> dict:
    """
    Parse a pasted Telebirr payment confirmation SMS.

    Returns dict with keys:
        amount          (float)
        recipient_name  (str | None)
        recipient_last4 (str | None)  -- last 4 digits of masked phone
        reference       (str | None)
        raw_text        (str)
    or None if the SMS cannot be parsed (missing amount or reference).
    """
    if not sms_text or len(sms_text.strip()) < 20:
        return None

    text = sms_text.strip()

    # ---- 1. Amount ----
    # Primary: "transferred ETB 30.00" -- the actual sent amount.
    # Using "transferred" keyword avoids matching service fee / current balance
    # which also appear as "ETB X.XX" later in the message.
    amount_match = re.search(
        r"transferred\s+ETB\s*([\d,]+(?:\.\d{1,2})?)",
        text, re.IGNORECASE
    )
    if not amount_match:
        # Fallback: first "ETB X.XX" found (works for some Telebirr variants)
        amount_match = re.search(r"ETB\s*([\d,]+(?:\.\d{1,2})?)", text, re.IGNORECASE)
    if not amount_match:
        return None

    try:
        amount = float(amount_match.group(1).replace(",", ""))
    except ValueError:
        return None

    # ---- 2. Recipient name ----
    # Pattern: "to hanan reda (" -- text between "to " and " ("
    name_match = re.search(r"\btransferred\s+ETB[^t]+to\s+([A-Za-z\s]+?)\s*\(", text, re.IGNORECASE)
    if not name_match:
        name_match = re.search(r"\bto\s+([A-Za-z\s]{2,40}?)\s*\(", text, re.IGNORECASE)
    recipient_name = name_match.group(1).strip() if name_match else None

    # ---- 3. Recipient phone last 4 digits ----
    # Pattern: "(2519****8740)" or "(09****1234)"
    phone_match = re.search(r"\((?:2519|09)?\d*\*+(\d{4})\)", text)
    recipient_last4 = phone_match.group(1) if phone_match else None

    # ---- 4. Transaction reference ----
    # Primary: "Your transaction number is DFE8VVNNIC"
    ref_match = re.search(r"transaction number is\s+([A-Za-z0-9]+)", text, re.IGNORECASE)
    if ref_match:
        reference = ref_match.group(1).upper()
    else:
        # Fallback: any uppercase alphanumeric token of 8+ chars
        # (avoids matching common words)
        fallback = re.search(r"\b([A-Z0-9]{8,})\b", text)
        reference = fallback.group(1) if fallback else None

    if reference is None:
        return None

    return {
        "amount": amount,
        "recipient_name": recipient_name,
        "recipient_last4": recipient_last4,
        "reference": reference,
        "raw_text": text,
    }


# =====================================================================
# RECEIPT NUMBER EXTRACTION
# =====================================================================

def extract_receipt_number(sms_text: str) -> str | None:
    """Extract receipt/transaction number from SMS text.

    Matches patterns like:
      - "Your transaction number is DFE8VVNNIC"
      - "https://transactioninfo.ethiotelecom.et/receipt/DFE8VVNNIC"
      - Fallback: any 8-12 char alphanumeric token
    """
    if not sms_text:
        return None
    text = sms_text.strip()

    m = re.search(r"transaction number is\s+([A-Za-z0-9]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    m = re.search(r"transactioninfo\.ethiotelecom\.et/receipt/([A-Za-z0-9]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()

    tokens = re.findall(r"\b([A-Z0-9]{8,12})\b", text.upper())
    if tokens:
        return tokens[0]
    return None


# =====================================================================
# RECIPIENT VERIFICATION
# =====================================================================

def verify_recipient(parsed: dict, expected_name: str, expected_last4: str):
    """
    Check that the SMS was sent to the expected Telebirr account.

    Comparisons are case-insensitive and strip whitespace.
    If a field couldn't be extracted from the SMS (None), that check
    is skipped -- the unique reference-ID duplicate check is the primary
    anti-fraud mechanism; name/phone verification is the secondary layer.

    Returns (ok: bool, reason: str)
      ok=True  -> recipient matches (or field missing from SMS, which is allowed)
      ok=False -> recipient clearly does NOT match -> reject this deposit
    """
    parsed_name = parsed.get("recipient_name")
    parsed_last4 = parsed.get("recipient_last4")

    if parsed_name and expected_name:
        if parsed_name.strip().lower() != expected_name.strip().lower():
            return False, "name_mismatch"

    if parsed_last4 and expected_last4:
        if parsed_last4 != expected_last4:
            return False, "phone_mismatch"

    return True, "ok"


# =====================================================================
# AMOUNT VALIDATION
# =====================================================================

def validate_deposit_amount(parsed: dict, expected_amount: float = None, min_amount: float = None):
    """
    Optional extra check: ensure the deposited amount matches what was
    expected (if the user pre-selected an amount) and meets the minimum.

    Returns (ok: bool, reason: str)
    """
    amount = parsed.get("amount", 0)

    if min_amount is not None and amount < min_amount:
        return False, f"below_minimum_{min_amount}"

    if expected_amount is not None:
        # Allow 0.01 rounding tolerance
        if abs(amount - expected_amount) > 0.01:
            return False, "amount_mismatch"

    return True, "ok"


# =====================================================================
# SELF-TEST  (python3 sms_parser.py)
# =====================================================================
if __name__ == "__main__":
    REAL_SMS = (
        "Dear Abdi \n"
        "You have transferred ETB 30.00 to hanan reda (2519****8740) on "
        "14/06/2026 20:47:00. Your transaction number is DFE8VVNNIC. The "
        "service fee is  ETB 0.87 and  15% VAT on the service fee is ETB 0.13. "
        "Your current E-Money Account  balance is ETB 1,429.52. To download "
        "your payment information please click this link: "
        "https://transactioninfo.ethiotelecom.et/receipt/DFE8VVNNIC.\n\n"
        "Thank you for using telebirr\n"
        "Ethio telecom"
    )

    ALT_SMS = (
        "Dear Customer,\n"
        "You have transferred ETB 100.00 to Habesha Bet (2519****9988) on "
        "15/06/2026 10:30:00. Your transaction number is ABX99112ZZQ. "
        "Service fee ETB 0.87. Current balance ETB 550.00.\n"
        "Thank you for using telebirr\nEthio telecom"
    )

    print("=== Real SMS ===")
    r = parse_telebirr_sms(REAL_SMS)
    print("Parsed:", r)
    ok, reason = verify_recipient(r, "Hanan Reda", "8740")
    print("Verify (correct):", ok, reason)
    ok, reason = verify_recipient(r, "Someone Else", "8740")
    print("Verify (wrong name):", ok, reason)
    ok, reason = verify_recipient(r, "Hanan Reda", "1234")
    print("Verify (wrong phone):", ok, reason)
    ok, reason = validate_deposit_amount(r, min_amount=20)
    print("Amount valid (min 20):", ok, reason)
    ok, reason = validate_deposit_amount(r, expected_amount=50)
    print("Amount matches 50?:", ok, reason)

    print("\n=== Alt SMS ===")
    r2 = parse_telebirr_sms(ALT_SMS)
    print("Parsed:", r2)
    ok, reason = verify_recipient(r2, "Habesha Bet", "9988")
    print("Verify (correct):", ok, reason)

    print("\n=== Invalid SMS ===")
    print("Empty:", parse_telebirr_sms(""))
    print("Random text:", parse_telebirr_sms("Hello how are you today"))
    print("ETB but no ref:", parse_telebirr_sms("You transferred ETB 50.00 today"))
