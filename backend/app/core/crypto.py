import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import settings

def _get_key() -> bytes:
    try:
        raw_key = base64.b64decode(settings.SETTINGS_ENCRYPTION_KEY)
        if len(raw_key) == 32:
            return raw_key
    except Exception:
        pass
    # Fallback to deterministic 32-byte key derived from secret
    padded = (settings.SETTINGS_ENCRYPTION_KEY.encode() * 2)[:32]
    return padded

def encrypt_setting(plaintext: str) -> str:
    """
    Encrypt sensitive setting using AES-256-GCM.
    Returns format: base64(nonce):base64(ciphertext):base64(tag)
    """
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    
    # AESGCM.encrypt appends 16-byte tag to ciphertext
    ct_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    ciphertext = ct_with_tag[:-16]
    tag = ct_with_tag[-16:]
    
    b64_nonce = base64.b64encode(nonce).decode("utf-8")
    b64_ct = base64.b64encode(ciphertext).decode("utf-8")
    b64_tag = base64.b64encode(tag).decode("utf-8")
    
    return f"{b64_nonce}:{b64_ct}:{b64_tag}"

def decrypt_setting(encrypted_payload: str) -> str:
    """
    Decrypt payload in format: base64(nonce):base64(ciphertext):base64(tag)
    """
    parts = encrypted_payload.split(":")
    if len(parts) != 3:
        raise ValueError("Invalid encrypted payload format")
        
    b64_nonce, b64_ct, b64_tag = parts
    nonce = base64.b64decode(b64_nonce)
    ciphertext = base64.b64decode(b64_ct)
    tag = base64.b64decode(b64_tag)
    
    key = _get_key()
    aesgcm = AESGCM(key)
    
    # Reassemble ciphertext + tag for cryptography library
    ct_with_tag = ciphertext + tag
    decrypted_bytes = aesgcm.decrypt(nonce, ct_with_tag, None)
    return decrypted_bytes.decode("utf-8")
