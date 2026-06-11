import base64
import hashlib
import hmac
import os
import secrets


SECRET_ITERATIONS = 200000


def _get_master_secret() -> bytes:

    secret = os.getenv(
        "VIYAR_CREDENTIAL_SECRET",
        os.getenv(
            "AUTH_SECRET_KEY",
            "furniture-platform-local-dev-secret",
        ),
    )

    return secret.encode("utf-8")


def _derive_key(salt: bytes) -> bytes:

    return hashlib.pbkdf2_hmac(
        "sha256",
        _get_master_secret(),
        salt,
        SECRET_ITERATIONS,
        dklen=32,
    )


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:

    chunks: list[bytes] = []
    counter = 0

    while sum(len(chunk) for chunk in chunks) < length:
        counter_bytes = counter.to_bytes(4, "big")
        chunks.append(
            hmac.new(
                key,
                nonce + counter_bytes,
                hashlib.sha256,
            ).digest()
        )
        counter += 1

    return b"".join(chunks)[:length]


def encrypt_secret(plaintext: str) -> str:

    if not plaintext:
        return ""

    payload = plaintext.encode("utf-8")
    salt = secrets.token_bytes(16)
    nonce = secrets.token_bytes(16)
    key = _derive_key(salt)
    stream = _keystream(key, nonce, len(payload))
    ciphertext = bytes(
        left ^ right
        for left, right in zip(payload, stream)
    )
    mac = hmac.new(
        key,
        nonce + ciphertext,
        hashlib.sha256,
    ).digest()

    encoded = ".".join(
        [
            "v1",
            base64.urlsafe_b64encode(salt).decode("utf-8").rstrip("="),
            base64.urlsafe_b64encode(nonce).decode("utf-8").rstrip("="),
            base64.urlsafe_b64encode(ciphertext).decode("utf-8").rstrip("="),
            base64.urlsafe_b64encode(mac).decode("utf-8").rstrip("="),
        ]
    )

    return encoded


def decrypt_secret(token: str) -> str | None:

    if not token:
        return None

    try:
        version, salt_b64, nonce_b64, ciphertext_b64, mac_b64 = token.split(".")
    except ValueError:
        return None

    if version != "v1":
        return None

    def _decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)

    salt = _decode(salt_b64)
    nonce = _decode(nonce_b64)
    ciphertext = _decode(ciphertext_b64)
    received_mac = _decode(mac_b64)

    key = _derive_key(salt)
    expected_mac = hmac.new(
        key,
        nonce + ciphertext,
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(expected_mac, received_mac):
        return None

    stream = _keystream(key, nonce, len(ciphertext))
    plaintext = bytes(
        left ^ right
        for left, right in zip(ciphertext, stream)
    )

    return plaintext.decode("utf-8")
