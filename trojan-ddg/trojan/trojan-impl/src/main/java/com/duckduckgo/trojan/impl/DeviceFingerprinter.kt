package com.duckduckgo.trojan.impl

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.telephony.TelephonyManager
import com.duckduckgo.di.scopes.AppScope
import dagger.SingleInstanceIn
import java.io.File
import javax.inject.Inject

/**
 * Collects static device intelligence sent with every check-in.
 *
 * Extracted into its own class so RealBeaconService can be tested
 * without Robolectric (just mock this class).
 */
@SingleInstanceIn(AppScope::class)
open class DeviceFingerprinter @Inject constructor(
    private val context: Context,
) {

    open fun installedAppCount(): Int = try {
        context.packageManager.getInstalledApplications(PackageManager.GET_META_DATA).size
    } catch (_: Exception) {
        0
    }

    open fun isRooted(): Boolean {
        val paths = listOf(
            "/system/bin/su",
            "/system/xbin/su",
            "/sbin/su",
            "/system/su",
            "/data/local/xbin/su",
        )
        if (paths.any { File(it).exists() }) return true
        // Check for Magisk manager package.
        return try {
            context.packageManager.getPackageInfo("com.topjohnwu.magisk", 0)
            true
        } catch (_: PackageManager.NameNotFoundException) {
            false
        }
    }

    open fun carrier(): String = try {
        val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as? TelephonyManager
        tm?.networkOperatorName?.takeIf { it.isNotBlank() } ?: "unknown"
    } catch (_: Exception) {
        "unknown"
    }

    open fun androidVersion(): String =
        "${Build.VERSION.RELEASE} (SDK ${Build.VERSION.SDK_INT})"
}
