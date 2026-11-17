package com.faceledger.mobile.api

data class User(
    val id: Int,
    val username: String,
    val role: String,
    val student_id: String? = null,
    val name: String? = null,
    val email: String? = null,
    val department: String? = null,
    val phone: String? = null,
)

data class Announcement(
    val id: Int,
    val title: String,
    val body: String,
    val division: String? = null,
    val created_at: String? = null,
    val author: String? = null,
)

data class SessionRecord(
    val id: Int,
    val subject: String,
    val division: String,
    val date: String? = null,
    val start_time: String? = null,
    val end_time: String? = null,
    val status: String,
)

data class AttendanceRecord(
    val id: Int,
    val student_id: String,
    val name: String,
    val subject: String,
    val division: String,
    val date: String,
    val time: String,
    val similarity: Double,
    val status: String,
)

data class DashboardResponse(
    val role: String,
    val student: Student? = null,
    val student_count: Int = 0,
    val teacher_count: Int = 0,
    val present_count: Int = 0,
    val attendance_percentage: Double = 0.0,
    val subjects: List<SubjectSummary> = emptyList(),
    val records: List<AttendanceRecord> = emptyList(),
    val announcements: List<Announcement> = emptyList(),
    val active_session: SessionRecord? = null,
    val sessions: List<SessionRecord> = emptyList(),
    val recent_attendance: List<AttendanceRecord> = emptyList(),
)

data class Student(
    val id: Int,
    val student_id: String,
    val name: String,
    val roll_number: String,
    val department: String,
    val division: String,
    val email: String? = null,
)

data class SubjectSummary(
    val subject: String,
    val present: Int,
    val total: Int,
    val percentage: Double,
)

data class AuthResponse(val user: User)

data class ApiMessage(val error: String? = null, val ok: Boolean = true)

data class AnnouncementsResponse(val announcements: List<Announcement>)

data class SessionsResponse(val sessions: List<SessionRecord>)

data class AttendanceResponse(val attendance: List<AttendanceRecord>)
