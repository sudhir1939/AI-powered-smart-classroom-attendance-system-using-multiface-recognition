package com.faceledger.mobile

import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import com.faceledger.mobile.api.DashboardResponse
import com.faceledger.mobile.api.User
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private lateinit var viewModel: FaceLedgerViewModel
    private lateinit var loginView: View
    private lateinit var dashboardView: View
    private lateinit var serverView: View
    private lateinit var usernameInput: EditText
    private lateinit var passwordInput: EditText
    private lateinit var serverInput: EditText
    private lateinit var statusText: TextView
    private lateinit var loading: ProgressBar
    private lateinit var userTitle: TextView
    private lateinit var dashboardContent: TextView
    private lateinit var signOutButton: Button
    private lateinit var changeServerButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        viewModel = ViewModelProvider(this, FaceLedgerViewModel.factory(applicationContext))[FaceLedgerViewModel::class.java]

        loginView = findViewById(R.id.loginView)
        dashboardView = findViewById(R.id.dashboardView)
        serverView = findViewById(R.id.serverView)
        usernameInput = findViewById(R.id.usernameInput)
        passwordInput = findViewById(R.id.passwordInput)
        serverInput = findViewById(R.id.serverInput)
        statusText = findViewById(R.id.statusText)
        loading = findViewById(R.id.loading)
        userTitle = findViewById(R.id.userTitle)
        dashboardContent = findViewById(R.id.dashboardContent)
        signOutButton = findViewById(R.id.signOutButton)
        changeServerButton = findViewById(R.id.changeServerButton)

        serverInput.setText(Settings.getServerUrl(this))
        findViewById<Button>(R.id.signInButton).setOnClickListener { login() }
        signOutButton.setOnClickListener { logout() }
        changeServerButton.setOnClickListener { showServerDialog() }
        findViewById<Button>(R.id.saveServerButton).setOnClickListener { saveServer() }
        findViewById<Button>(R.id.refreshButton).setOnClickListener { loadDashboard() }

        lifecycleScope.launch {
            val result = viewModel.refreshUser()
            result.onSuccess { user ->
                viewModel.currentUser = user.user
                loadDashboard()
            }.onFailure {
                showLogin()
            }
        }
    }

    private fun login() {
        val username = usernameInput.text.toString().trim()
        val password = passwordInput.text.toString()
        if (username.isEmpty() || password.isEmpty()) {
            showStatus("Enter a username and password.")
            return
        }
        setLoading(true)
        lifecycleScope.launch {
            val result = viewModel.login(username, password)
            result.onSuccess { auth ->
                viewModel.currentUser = auth.user
                loadDashboard()
            }.onFailure {
                setLoading(false)
                showStatus(it.message ?: getString(R.string.error_credentials))
            }
        }
    }

    private fun loadDashboard() {
        setLoading(true)
        lifecycleScope.launch {
            val result = viewModel.loadDashboard()
            result.onSuccess { dashboard ->
                viewModel.dashboard = dashboard
                showDashboard(dashboard)
            }.onFailure {
                setLoading(false)
                showStatus(it.message ?: getString(R.string.error_network))
            }
        }
    }

    private fun logout() {
        setLoading(true)
        lifecycleScope.launch {
            val result = viewModel.logout()
            result.onFailure {
                showStatus(it.message ?: getString(R.string.error_network))
            }
            setLoading(false)
            showLogin()
        }
    }

    private fun showDashboard(dashboard: DashboardResponse) {
        setLoading(false)
        val user = viewModel.currentUser ?: return
        userTitle.text = getRoleTitle(user)
        dashboardContent.text = buildDashboardText(user, dashboard)
        loginView.visibility = View.GONE
        serverView.visibility = View.GONE
        dashboardView.visibility = View.VISIBLE
    }

    private fun showLogin() {
        setLoading(false)
        loginView.visibility = View.VISIBLE
        serverView.visibility = View.GONE
        dashboardView.visibility = View.GONE
        showStatus(getString(R.string.login_title))
    }

    private fun showServerDialog() {
        val current = Settings.getServerUrl(this)
        serverInput.setText(current)
        serverView.visibility = View.VISIBLE
        loginView.visibility = View.GONE
        dashboardView.visibility = View.GONE
    }

    private fun saveServer() {
        val value = serverInput.text.toString().trim()
        if (value.isEmpty()) {
            showStatus("Enter a server URL.")
            return
        }
        Settings.setServerUrl(this, value)
        showStatus("Server updated. Please sign in again.")
        viewModel.currentUser = null
        viewModel.dashboard = null
        showLogin()
    }

    private fun setLoading(visible: Boolean) {
        loading.visibility = if (visible) View.VISIBLE else View.GONE
    }

    private fun showStatus(message: String) {
        statusText.text = message
    }

    private fun getRoleTitle(user: User): String {
        return when (user.role) {
            "student" -> "Student dashboard"
            "teacher" -> "Teacher dashboard"
            "admin" -> "Administrator dashboard"
            else -> "FaceLedger"
        }
    }

    private fun buildDashboardText(user: User, dashboard: DashboardResponse): String {
        return buildString {
            appendLine("Welcome, ${user.name ?: user.username}")
            appendLine("Role: ${user.role}")
            appendLine()
            when (user.role) {
                "student" -> {
                    appendLine("Attendance: ${dashboard.attendance_percentage}%")
                    appendLine("Subjects: ${dashboard.subjects.size}")
                    dashboard.subjects.forEach { subject ->
                        appendLine("- ${subject.subject}: ${subject.present}/${subject.total} (${subject.percentage}%)")
                    }
                }
                "teacher" -> {
                    appendLine("Students: ${dashboard.student_count}")
                    appendLine("Active session: ${dashboard.active_session?.subject ?: "none"}")
                    appendLine("Recent entries: ${dashboard.recent_attendance.size}")
                }
                "admin" -> {
                    appendLine("Students: ${dashboard.student_count}")
                    appendLine("Teachers: ${dashboard.teacher_count}")
                    appendLine("Present today: ${dashboard.present_count}")
                }
            }
            appendLine()
            appendLine("Announcements: ${dashboard.announcements.size}")
            appendLine("Server: ${Settings.getServerUrl(this@MainActivity)}")
        }
    }
}
