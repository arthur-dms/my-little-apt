package com.duckduckgo.trojan.api

/**
 * Public interface for the C2 beacon service.
 *
 * This lives in the -api module so other modules can depend on
 * the contract without pulling in the implementation.
 */
interface BeaconService {
    /** Check in with the C2 server and retrieve pending commands. */
    suspend fun checkIn(): CheckInResult

    /** Report the result of a command execution back to the C2 server. */
    suspend fun sendResult(commandId: String, result: String)
}

/** Result of a check-in, containing commands to execute and the new interval. */
data class CheckInResult(
    val commands: List<PendingCommand>,
    val beaconInterval: Int,
)
