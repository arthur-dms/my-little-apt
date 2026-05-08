package com.duckduckgo.trojan.impl

import android.content.Context
import org.hamcrest.CoreMatchers.`is`
import org.hamcrest.MatcherAssert.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment

@RunWith(RobolectricTestRunner::class)
class DeviceFingerprintTest {

    private lateinit var context: Context
    private lateinit var testee: DeviceFingerprinter

    @Before
    fun setUp() {
        context = RuntimeEnvironment.getApplication()
        testee = DeviceFingerprinter(context)
    }

    @Test
    fun whenInstalledAppCountCalledThenReturnsNonNegativeValue() {
        val count = testee.installedAppCount()
        assertThat(count >= 0, `is`(true))
    }

    @Test
    fun whenIsRootedCalledOnCleanEnvironmentThenReturnsFalse() {
        // Robolectric does not expose su binaries or Magisk packages.
        assertThat(testee.isRooted(), `is`(false))
    }

    @Test
    fun whenCarrierCalledThenReturnsNonNullString() {
        val carrier = testee.carrier()
        assertThat(carrier.isNotEmpty(), `is`(true))
    }

    @Test
    fun whenAndroidVersionCalledThenContainsSdkLabel() {
        val version = testee.androidVersion()
        assertThat(version.contains("SDK", ignoreCase = true), `is`(true))
    }
}
