package com.faceledger.mobile

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.faceledger.mobile.api.ApiClient
import com.faceledger.mobile.api.AuthResponse
import com.faceledger.mobile.api.DashboardResponse
import com.faceledger.mobile.api.User

class FaceLedgerViewModel(private val api: ApiClient) : ViewModel() {
    var currentUser: User? = null
    var dashboard: DashboardResponse? = null

    suspend fun login(username: String, password: String): Result<AuthResponse> = runCatching {
        api.login(username, password).getOrThrow()
    }

    suspend fun loadDashboard(): Result<DashboardResponse> = runCatching {
        api.dashboard().getOrThrow()
    }

    suspend fun refreshUser(): Result<AuthResponse> = runCatching {
        api.currentUser().getOrThrow()
    }

    suspend fun logout(): Result<Unit> = runCatching {
        api.logout().getOrThrow()
        currentUser = null
        dashboard = null
    }

    companion object {
        fun factory(context: Context): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return FaceLedgerViewModel(ApiClient(context.applicationContext)) as T
            }
        }
    }
}
