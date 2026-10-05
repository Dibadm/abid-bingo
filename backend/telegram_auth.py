# telegram_auth.py
# ============================================
# HABESHA BET - TELEGRAM MINI APP AUTH VERIFICATION
#
# When a user opens the Mini App, Telegram gives the React frontend a
# string called `initData` containing the user's id/username/etc, signed
# with HMAC-SHA256 using a key derived from your bot token. The frontend
# sends this string to our API on every request; THIS module verifies
# the signature server-side before trusting anything in it.
#
# Without this check, anyone could open browser dev tools, fabricate a
# fake initData claiming to be user_id=12345, and drain that user's
# balance. This is the single most important security boundary between
# "a Mini App" and "an open API anyone can call with any user_id."
#
# Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
# ============================================

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import config


class InitDataInvalid(Exception):
    """Raised when initData fails signature verification or has expired."""
    pass


def _build_secret_key(bot_token: str) -> bytes:
    """Per Telegram's spec: secret_key = HMAC-SHA256(key="WebAppData", data=bot_token)"""
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def verify_init_data(init_data: str, bot_token: str = None, max_age_seconds: int = 86400) -> dict:
    """
    Verify a Telegram Mini App initData string and return the parsed,
    trustworthy fields if valid.

    Returns a dict with at least:
        {"user": {"id": int, "username": str, "first_name": str, ...},
         "auth_date": int}

    Raises InitDataInvalid if:
        - the hash doesn't match (tampered or forged data)
        - required fields are missing
        - auth_date is older than max_age_seconds (stale/replayed init data)

    max_age_seconds defaults to 24h, matching Telegram's own guidance that
    initData should be treated as freshly issued per app-open, not stored
    and reused indefinitely.
    """
    if bot_token is None:
        bot_token = config.BOT_TOKEN

    if not init_data:
        raise InitDataInvalid("empty init_data")

    # parse_qsl preserves duplicate keys and doesn't silently merge them,
    # which matters because Telegram's spec is explicit about using the
    # raw querystring pairs, not a dict-deduplicated version.
    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)

    received_hash = None
    data_check_fields = []
    for key, value in pairs:
        if key == "hash":
            received_hash = value
        else:
            data_check_fields.append((key, value))

    if received_hash is None:
        raise InitDataInvalid("missing hash field")

    # Build the data-check-string: all fields except hash, sorted by key,
    # joined as "key=value" with newline separators. This exact format
    # is mandated by Telegram's spec - any deviation breaks verification.
    data_check_fields.sort(key=lambda kv: kv[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in data_check_fields)

    secret_key = _build_secret_key(bot_token)
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    # Constant-time comparison to avoid timing side-channels leaking the
    # correct hash byte-by-byte over many requests.
    if not hmac.compare_digest(computed_hash, received_hash):
        raise InitDataInvalid("hash mismatch - data may have been tampered with")

    parsed = dict(data_check_fields)

    auth_date_raw = parsed.get("auth_date")
    if auth_date_raw is None:
        raise InitDataInvalid("missing auth_date field")

    try:
        auth_date = int(auth_date_raw)
    except ValueError:
        raise InitDataInvalid("auth_date is not a valid integer")

    age = time.time() - auth_date
    if age > max_age_seconds:
        raise InitDataInvalid(f"init_data is stale ({int(age)}s old, max {max_age_seconds}s)")
    if age < -60:
        # Allow a small amount of clock skew (60s) but reject anything
        # claiming to be from the future beyond that - a sign of a
        # forged or badly malformed auth_date.
        raise InitDataInvalid("auth_date is in the future")

    user_raw = parsed.get("user")
    if user_raw is None:
        raise InitDataInvalid("missing user field")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        raise InitDataInvalid("user field is not valid JSON")

    if "id" not in user:
        raise InitDataInvalid("user object missing id")

    return {
        "user": user,
        "auth_date": auth_date,
        "query_id": parsed.get("query_id"),
    }


def extract_user_id(init_data: str, bot_token: str = None, max_age_seconds: int = 86400) -> int:
    """Convenience wrapper: verify init_data and return just the
    authenticated Telegram user_id as an int. This is what most API
    endpoints actually need - a trustworthy user_id to look up in our
    own database, never trusting any user_id the frontend might also
    send in the request body/query params separately."""
    result = verify_init_data(init_data, bot_token=bot_token, max_age_seconds=max_age_seconds)
    return int(result["user"]["id"])


# =====================================================================
# SELF-TEST
# Builds a real signed init_data string the same way Telegram would,
# then verifies it - confirming the round-trip actually works, plus
# negative tests for tampering and staleness.
# =====================================================================

if __name__ == "__main__":
    import urllib.parse

    TEST_BOT_TOKEN = "123456789:TEST-token-for-selftest-only"

    def build_fake_init_data(user_dict, auth_date, bot_token, extra_fields=None):
        """Helper that mimics what Telegram's client actually sends, so we
        can test our own verifier against correctly-signed data."""
        fields = {
            "user": json.dumps(user_dict, separators=(",", ":")),
            "auth_date": str(auth_date),
            "query_id": "AAEtest123",
        }
        if extra_fields:
            fields.update(extra_fields)

        data_check_fields = sorted(fields.items(), key=lambda kv: kv[0])
        data_check_string = "\n".join(f"{k}={v}" for k, v in data_check_fields)

        secret_key = _build_secret_key(bot_token)
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        fields["hash"] = computed_hash
        return urllib.parse.urlencode(fields)

    print("=== Test 1: Valid, fresh init_data ===")
    user = {"id": 999888777, "username": "testuser", "first_name": "Test"}
    valid_init_data = build_fake_init_data(user, int(time.time()), TEST_BOT_TOKEN)
    try:
        result = verify_init_data(valid_init_data, bot_token=TEST_BOT_TOKEN)
        print("PASS - verified successfully:", result["user"])
    except InitDataInvalid as e:
        print("FAIL - should have passed:", e)

    print("\n=== Test 2: extract_user_id convenience function ===")
    uid = extract_user_id(valid_init_data, bot_token=TEST_BOT_TOKEN)
    print(f"PASS - extracted user_id: {uid}" if uid == 999888777 else f"FAIL - got {uid}")

    print("\n=== Test 3: Tampered data (attacker changes user id after signing) ===")
    tampered = valid_init_data.replace("999888777", "111111111")
    try:
        verify_init_data(tampered, bot_token=TEST_BOT_TOKEN)
        print("FAIL - tampered data was accepted!")
    except InitDataInvalid as e:
        print("PASS - correctly rejected:", e)

    print("\n=== Test 4: Wrong bot token (forged by someone without our token) ===")
    forged = build_fake_init_data(user, int(time.time()), "999999999:WRONG-token")
    try:
        verify_init_data(forged, bot_token=TEST_BOT_TOKEN)
        print("FAIL - forged data was accepted!")
    except InitDataInvalid as e:
        print("PASS - correctly rejected:", e)

    print("\n=== Test 5: Stale init_data (25 hours old, max is 24h) ===")
    stale = build_fake_init_data(user, int(time.time()) - 25 * 3600, TEST_BOT_TOKEN)
    try:
        verify_init_data(stale, bot_token=TEST_BOT_TOKEN)
        print("FAIL - stale data was accepted!")
    except InitDataInvalid as e:
        print("PASS - correctly rejected:", e)

    print("\n=== Test 6: Missing hash field entirely ===")
    try:
        verify_init_data("user=%7B%22id%22%3A123%7D&auth_date=123", bot_token=TEST_BOT_TOKEN)
        print("FAIL - missing-hash data was accepted!")
    except InitDataInvalid as e:
        print("PASS - correctly rejected:", e)

    print("\n=== Test 7: Empty string ===")
    try:
        verify_init_data("", bot_token=TEST_BOT_TOKEN)
        print("FAIL - empty string was accepted!")
    except InitDataInvalid as e:
        print("PASS - correctly rejected:", e)

    print("\n=== Test 8: Future auth_date (clock-skew abuse attempt) ===")
    future = build_fake_init_data(user, int(time.time()) + 3600, TEST_BOT_TOKEN)
    try:
        verify_init_data(future, bot_token=TEST_BOT_TOKEN)
        print("FAIL - future-dated data was accepted!")
    except InitDataInvalid as e:
        print("PASS - correctly rejected:", e)
