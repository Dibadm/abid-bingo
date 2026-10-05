# test_telegram_auth.py
# ============================================
# HABESHA BET - TELEGRAM AUTH TESTS
# ============================================

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.telegram_auth import (
    verify_init_data,
    extract_user_id,
    InitDataInvalid,
    _build_secret_key,
)


TEST_BOT_TOKEN = "123456789:TEST-token-for-testing-only"


def _build_secret_key_local(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def _build_fake_init_data(user_dict, auth_date, bot_token, extra_fields=None):
    fields = {
        "user": json.dumps(user_dict, separators=(",", ":")),
        "auth_date": str(auth_date),
        "query_id": "AAEtest123",
    }
    if extra_fields:
        fields.update(extra_fields)

    data_check_fields = sorted(fields.items(), key=lambda kv: kv[0])
    data_check_string = "\n".join(f"{k}={v}" for k, v in data_check_fields)

    secret_key = _build_secret_key_local(bot_token)
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    fields["hash"] = computed_hash
    return urllib.parse.urlencode(fields)


def test_valid_fresh_init_data():
    user = {"id": 999888777, "username": "testuser", "first_name": "Test"}
    init_data = _build_fake_init_data(user, int(time.time()), TEST_BOT_TOKEN)
    result = verify_init_data(init_data, bot_token=TEST_BOT_TOKEN)
    assert result["user"]["id"] == 999888777
    assert result["user"]["username"] == "testuser"


def test_extract_user_id():
    user = {"id": 999888777, "username": "testuser"}
    init_data = _build_fake_init_data(user, int(time.time()), TEST_BOT_TOKEN)
    uid = extract_user_id(init_data, bot_token=TEST_BOT_TOKEN)
    assert uid == 999888777


def test_tampered_data_rejected():
    user = {"id": 999888777, "username": "testuser"}
    init_data = _build_fake_init_data(user, int(time.time()), TEST_BOT_TOKEN)
    tampered = init_data.replace("999888777", "111111111")
    with pytest.raises(InitDataInvalid):
        verify_init_data(tampered, bot_token=TEST_BOT_TOKEN)


def test_wrong_bot_token_rejected():
    user = {"id": 999888777, "username": "testuser"}
    forged = _build_fake_init_data(user, int(time.time()), "999999999:WRONG-token")
    with pytest.raises(InitDataInvalid):
        verify_init_data(forged, bot_token=TEST_BOT_TOKEN)


def test_stale_init_data_rejected():
    user = {"id": 999888777, "username": "testuser"}
    stale = _build_fake_init_data(user, int(time.time()) - 25 * 3600, TEST_BOT_TOKEN)
    with pytest.raises(InitDataInvalid):
        verify_init_data(stale, bot_token=TEST_BOT_TOKEN, max_age_seconds=86400)


def test_missing_hash_rejected():
    with pytest.raises(InitDataInvalid):
        verify_init_data("user=%7B%22id%22%3A123%7D&auth_date=123", bot_token=TEST_BOT_TOKEN)


def test_empty_string_rejected():
    with pytest.raises(InitDataInvalid):
        verify_init_data("", bot_token=TEST_BOT_TOKEN)


def test_missing_user_field_rejected():
    user = {"id": 999888777}
    init_data = _build_fake_init_data(user, int(time.time()), TEST_BOT_TOKEN)
    tampered = init_data.replace("user=", "bad=")
    with pytest.raises(InitDataInvalid):
        verify_init_data(tampered, bot_token=TEST_BOT_TOKEN)
