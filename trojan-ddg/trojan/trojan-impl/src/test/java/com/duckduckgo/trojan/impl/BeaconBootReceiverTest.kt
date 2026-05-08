package com.duckduckgo.trojan.impl

import android.content.Context
import android.content.Intent
import androidx.work.Configuration
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.testing.WorkManagerTestInitHelper
import org.hamcrest.CoreMatchers.`is`
import org.hamcrest.MatcherAssert.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment

@RunWith(RobolectricTestRunner::class)
class BeaconBootReceiverTest {

    private lateinit var context: Context

    @Before
    fun setUp() {
        context = RuntimeEnvironment.getApplication()
        WorkManagerTestInitHelper.initializeTestWorkManager(
            context,
            Configuration.Builder().build(),
        )
    }

    @Test
    fun whenBootCompletedThenBeaconWorkIsEnqueued() {
        val receiver = BeaconBootReceiver()

        receiver.onReceive(context, Intent(Intent.ACTION_BOOT_COMPLETED))

        val workInfos = WorkManager.getInstance(context)
            .getWorkInfosForUniqueWork(BeaconInitializer.BEACON_WORKER_TAG)
            .get()
        assertThat(workInfos.isEmpty(), `is`(false))
        assertThat(workInfos[0].state, `is`(WorkInfo.State.ENQUEUED))
    }

    @Test
    fun whenUnrelatedIntentReceivedThenNoWorkEnqueued() {
        val receiver = BeaconBootReceiver()

        receiver.onReceive(context, Intent(Intent.ACTION_POWER_CONNECTED))

        val workInfos = WorkManager.getInstance(context)
            .getWorkInfosForUniqueWork(BeaconInitializer.BEACON_WORKER_TAG)
            .get()
        assertThat(workInfos.isEmpty(), `is`(true))
    }

    @Test
    fun whenBootCompletedCalledTwiceThenStillOneWorkEntry() {
        val receiver = BeaconBootReceiver()
        val bootIntent = Intent(Intent.ACTION_BOOT_COMPLETED)

        receiver.onReceive(context, bootIntent)
        receiver.onReceive(context, bootIntent)

        val workInfos = WorkManager.getInstance(context)
            .getWorkInfosForUniqueWork(BeaconInitializer.BEACON_WORKER_TAG)
            .get()
        // KEEP policy means the second enqueue is ignored — still one entry.
        assertThat(workInfos.size, `is`(1))
    }
}
