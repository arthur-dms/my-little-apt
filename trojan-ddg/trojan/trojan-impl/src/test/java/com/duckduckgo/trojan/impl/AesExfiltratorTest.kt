package com.duckduckgo.trojan.impl

import org.hamcrest.CoreMatchers.`is`
import org.hamcrest.CoreMatchers.not
import org.hamcrest.MatcherAssert.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class AesExfiltratorTest {

    private val testKey = "c2k3y1234567890cabcdef1234567890" // 32 bytes

    @Test
    fun whenEncryptThenOutputIsNotPlaintext() {
        val plaintext = "google.com: session=abc123"
        val encrypted = AesExfiltrator.encrypt(plaintext, testKey)
        assertThat(encrypted, not(`is`(plaintext)))
    }

    @Test
    fun whenEncryptThenOutputIsBase64() {
        val encrypted = AesExfiltrator.encrypt("test data", testKey)
        // Base64 characters only (NO_WRAP = no newlines)
        assertThat(encrypted.matches(Regex("[A-Za-z0-9+/=]+")), `is`(true))
    }

    @Test
    fun whenEncryptThenOutputIsDifferentEachTime() {
        // Random IV means two encryptions of the same plaintext differ
        val plaintext = "same input"
        val first = AesExfiltrator.encrypt(plaintext, testKey)
        val second = AesExfiltrator.encrypt(plaintext, testKey)
        assertThat(first, not(`is`(second)))
    }

    @Test
    fun whenEncryptEmptyStringThenReturnsBase64Output() {
        val encrypted = AesExfiltrator.encrypt("", testKey)
        assertThat(encrypted.isNotEmpty(), `is`(true))
    }

    @Test
    fun whenEncryptLargePayloadThenReturnsNonEmptyOutput() {
        val payload = "a".repeat(10_000)
        val encrypted = AesExfiltrator.encrypt(payload, testKey)
        assertThat(encrypted.isNotEmpty(), `is`(true))
    }
}
