package com.duckduckgo.trojan.api

/**
 * Represents a command received from the C2 server
 * that is waiting to be executed on the client.
 */
data class PendingCommand(
    val id: String,
    val type: String,
    val payload: String,
)
