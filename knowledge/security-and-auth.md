# 🔐 Security, Authentication & Cryptography (`knowledge/security-and-auth.md`)

This document details the security architecture, PIN protection, password hashing, JWT session management, and AES-256-GCM encryption of sensitive database settings.

---

## 1. PIN Gatekeeper (Argon2id)

The user locks their instance with a 4 to 8 digit numeric PIN.

### Hashing Implementation
Implemented in [`backend/app/core/security.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/core/security.py):
- Algorithm: **Argon2id** (via `passlib.hash.argon2`).
- Resistant to GPU-based brute-force attacks and side-channel attacks.

### Brute-Force Rate Limiting:
- `failed_attempts` is tracked in the `user_auth` table.
- If consecutive failed logins reach `5`:
  - `locked_until = now() + 5 minutes`.
  - Endpoint returns HTTP 429 Too Many Requests with remaining cooldown seconds.
- Successful login resets `failed_attempts = 0` and clears `locked_until`.

---

## 2. JWT Session Management

- Standard: JSON Web Token (**JWT**), algorithm **HS256**.
- Secret Key: Loaded from `SECRET_KEY` environment variable. Defaults to local persistent machine key.
- Lifetime: 24 hours.
- Token passed via HTTP header:
  `Authorization: Bearer <jwt_token>`
- Frontend Axios interceptor automatically attaches the token and clears it upon receiving HTTP 401.

### Public vs Protected Endpoints
Protected with `dependencies=[Depends(get_current_session)]`:
- `/api/videos/*`
- `/api/clips/*`
- `/api/shorts/*`
- `/api/tts/*`
- `/api/settings/*` (except public OAuth callback)

Public endpoints:
- `/api/health`
- `/api/auth/status`, `/api/auth/setup`, `/api/auth/login`
- `/api/settings/gdrive/oauth/callback` (must be accessible by Google redirect without Bearer headers).

---

## 3. Database Secrets Encryption (AES-256-GCM)

Sensitive user settings stored in SQLite must NOT be stored in plaintext.
Implemented in [`backend/app/core/crypto.py`](file:///Users/sultanherrysan/Documents/dev/web-development/clipping/backend/app/core/crypto.py).

### Encrypted Keys:
- `llm_api_key`: OpenAI API key.
- `gdrive_sa_json`: Service account private key JSON.
- `gdrive_client_secret`: Google OAuth client secret.
- `gdrive_refresh_token`: Google OAuth refresh token.

### Cryptographic Details:
- Cipher: **AES-256-GCM** (Authenticated Encryption with Associated Data).
- 12-byte cryptographically secure random nonce (`os.urandom(12)`).
- 16-byte authentication tag appended to the ciphertext.
- Stored as base64-encoded string: `base64(nonce + ciphertext + tag)`.
- Master key derived from `ENCRYPTION_KEY` or hashed machine ID.
