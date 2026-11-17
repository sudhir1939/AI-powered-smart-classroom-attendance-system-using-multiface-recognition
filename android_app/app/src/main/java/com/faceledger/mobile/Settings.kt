package com.faceledger.mobile

import android.content.Context

object Settings {
    private const val KEY_SERVER_URL = "server_url"
    private const val DEFAULT_SERVER_URL = "http://10.0.2.2:5000"

    fun getServerUrl(context: Context): String {
        val app = context.applicationContext as FaceLedgerApplication
        return app.settings.getString(KEY_SERVER_URL, DEFAULT_SERVER_URL) ?: DEFAULT_SERVER_URL
    }

    fun setServerUrl(context: Context, value: String) {
        val app = context.applicationContext as FaceLedgerApplication
        app.settings.edit().putString(KEY_SERVER_URL, value.trim()).apply()
    }
}
