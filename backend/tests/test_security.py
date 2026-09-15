import pytest
from app.services.ass_service import hex_to_ass
from app.core.security import hash_pin, verify_pin, create_access_token
from app.core.crypto import encrypt_setting, decrypt_setting
import jwt
from app.config import settings

def test_hex_to_ass_color_conversion():
    # Test golden test case from PRD:
    # #FFCC00 (R=FF, G=CC, B=00) -> &H0000CCFF& (BGR)
    ass_yellow = hex_to_ass("#FFCC00")
    assert ass_yellow == "&H0000CCFF&", f"Expected &H0000CCFF&, got {ass_yellow}"

    # Test white #FFFFFF -> &H00FFFFFF&
    ass_white = hex_to_ass("#FFFFFF")
    assert ass_white == "&H00FFFFFF&"

    # Test Ember Studio Terracotta #C2410C -> &H000C41C2&
    # R=C2, G=41, B=0C -> B=0C, G=41, R=C2
    ass_terracotta = hex_to_ass("#C2410C")
    assert ass_terracotta == "&H000C41C2&"

def test_argon2id_pin_hashing():
    pin = "123456"
    p_hash = hash_pin(pin)
    assert p_hash.startswith("$argon2id$")
    assert verify_pin(p_hash, pin) is True
    assert verify_pin(p_hash, "654321") is False

def test_jwt_access_token():
    token = create_access_token({"sub": "local-user"})
    decoded = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    assert decoded["sub"] == "local-user"
    assert decoded["type"] == "access"
    assert "exp" in decoded

def test_aes_gcm_encryption():
    secret_text = "sk-proj-super-secret-api-key-12345"
    encrypted = encrypt_setting(secret_text)
    assert encrypted != secret_text
    parts = encrypted.split(":")
    assert len(parts) == 3, "Payload must be nonce:ct:tag"
    decrypted = decrypt_setting(encrypted)
    assert decrypted == secret_text
