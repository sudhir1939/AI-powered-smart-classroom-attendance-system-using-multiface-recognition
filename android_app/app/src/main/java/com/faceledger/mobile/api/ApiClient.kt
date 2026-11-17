package com.faceledger.mobile.api

import android.content.Context
import com.faceledger.mobile.Settings
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.JavaNetCookieJar
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.net.CookieManager
import java.net.CookiePolicy
import java.util.concurrent.TimeUnit

class ApiClient(private val context: Context) {
    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    private val client = OkHttpClient.Builder()
        .cookieJar(JavaNetCookieJar(CookieManager(null, CookiePolicy.ACCEPT_ORIGINAL_SERVER)))
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    fun login(username: String, password: String): Result<AuthResponse> = executeJson(
        path = "api/auth/login",
        method = "POST",
        body = mapOf("username" to username, "password" to password),
        type = AuthResponse::class.java,
    )

    fun logout(): Result<ApiMessage> = executeJson(
        path = "api/auth/logout",
        method = "GET",
        type = ApiMessage::class.java,
    )

    fun currentUser(): Result<AuthResponse> = executeJson(
        path = "api/auth/me",
        method = "GET",
        type = AuthResponse::class.java,
    )

    fun dashboard(): Result<DashboardResponse> = executeJson(
        path = "api/dashboard",
        method = "GET",
        type = DashboardResponse::class.java,
    )

    fun announcements(): Result<AnnouncementsResponse> = executeJson(
        path = "api/announcements",
        method = "GET",
        type = AnnouncementsResponse::class.java,
    )

    fun attendance(): Result<AttendanceResponse> = executeJson(
        path = "api/attendance",
        method = "GET",
        type = AttendanceResponse::class.java,
    )

    fun sessions(): Result<SessionsResponse> = executeJson(
        path = "api/sessions",
        method = "GET",
        type = SessionsResponse::class.java,
    )

    private fun <T> executeJson(
        path: String,
        method: String,
        body: Map<String, String>? = null,
        type: Class<T>,
    ): Result<T> {
        val requestBody = body?.let { jsonString(it) }
            ?.toRequestBody(jsonMediaType)

        val request = Request.Builder()
            .url(Settings.getServerUrl(context).trimEnd('/') + "/" + path.trimStart('/'))
            .method(method, requestBody)
            .header("Accept", "application/json")
            .build()

        return try {
            val response = client.newCall(request).execute()
            val responseBody = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                val errorMessage = parseError(responseBody)
                Result.failure(RuntimeException(errorMessage))
            } else {
                val payload = moshi.adapter(type).fromJson(responseBody)
                if (payload == null) Result.failure(RuntimeException("Invalid server response."))
                else Result.success(payload)
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun jsonString(value: Map<String, String>): String =
        buildString {
            append('{')
            value.entries.forEachIndexed { index, entry ->
                if (index > 0) append(',')
                append('"').append(entry.key).append('"')
                append(':')
                append('"').append(entry.value.escapeJson()).append('"')
            }
            append('}')
        }

    private fun String.escapeJson(): String =
        replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")

    private fun parseError(json: String): String {
        val cleaned = json.trim()
        if (cleaned.isEmpty()) return "Server returned an error."
        return try {
            val parsed = moshi.adapter(Map::class.java).fromJson(cleaned) as? Map<*, *>
            parsed?.get("error") as? String ?: "Server returned an error."
        } catch (_: Exception) {
            cleaned
        }
    }
}
