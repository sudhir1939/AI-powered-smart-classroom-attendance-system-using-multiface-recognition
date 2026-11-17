from datetime import date

from flask import Blueprint, jsonify, request, session

from models.announcement import Announcement
from models.attendance import Attendance
from models.session import AttendanceSession
from models.student import Student
from models.user import User
from routes.auth import login_required

mobile_api_bp = Blueprint("mobile_api", __name__, url_prefix="/api")


@mobile_api_bp.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username or password."}), 401

    session.clear()
    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    session["student_id"] = user.student_id

    return jsonify({"user": _serialize_user(user)})


@mobile_api_bp.post("/auth/logout")
@login_required
def logout():
    session.clear()
    return jsonify({"ok": True})


@mobile_api_bp.get("/auth/me")
@login_required
def current_user():
    user = User.query.get(session["user_id"])
    return jsonify({"user": _serialize_user(user)})


@mobile_api_bp.get("/dashboard")
@login_required
def dashboard():
    role = session.get("role")
    if role == "student":
        student = Student.query.get(session.get("student_id"))
        if not student:
            return jsonify({"error": "Student account not found."}), 404
        return jsonify(_student_dashboard(student))
    if role == "teacher":
        return jsonify(_teacher_dashboard())
    if role == "admin":
        return jsonify(_admin_dashboard())
    return jsonify({"error": "Unsupported account role."}), 403


@mobile_api_bp.get("/announcements")
@login_required
def announcements():
    role = session.get("role")
    if role == "student":
        student = Student.query.get(session.get("student_id"))
        if not student:
            return jsonify({"error": "Student account not found."}), 404
        division = student.division
        rows = Announcement.query.filter((Announcement.division == None) | (Announcement.division == division)).order_by(Announcement.created_at.desc()).all()
    else:
        rows = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return jsonify({"announcements": [_serialize_announcement(row) for row in rows]})


@mobile_api_bp.get("/sessions")
@login_required
def sessions():
    if session.get("role") not in {"admin", "teacher"}:
        return jsonify({"error": "Unauthorized."}), 403
    rows = AttendanceSession.query.order_by(AttendanceSession.session_date.desc(), AttendanceSession.id.desc()).all()
    return jsonify({"sessions": [_serialize_session(row) for row in rows]})


@mobile_api_bp.get("/attendance")
@login_required
def attendance_history():
    role = session.get("role")
    if role == "student":
        student = Student.query.get(session.get("student_id"))
        if not student:
            return jsonify({"error": "Student account not found."}), 404
        rows = Attendance.query.filter_by(student_id=student.id).join(AttendanceSession).order_by(Attendance.timestamp.desc()).all()
    elif role in {"admin", "teacher"}:
        rows = Attendance.query.join(Student).join(AttendanceSession).order_by(Attendance.timestamp.desc()).all()
    else:
        return jsonify({"error": "Unauthorized."}), 403
    return jsonify({"attendance": [_serialize_attendance(row) for row in rows]})


def _serialize_user(user):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "student_id": user.student.student_id if user.student else None,
        "name": user.full_name or (user.student.name if user.student else None),
        "email": user.email or (user.student.email if user.student else None),
        "department": user.department or (user.student.department if user.student else None),
        "phone": user.phone,
    }


def _serialize_announcement(announcement):
    return {
        "id": announcement.id,
        "title": announcement.title,
        "body": announcement.body,
        "division": announcement.division,
        "created_at": announcement.created_at.isoformat() if announcement.created_at else None,
        "author": announcement.author.full_name if announcement.author else None,
    }


def _serialize_session(session_record):
    return {
        "id": session_record.id,
        "subject": session_record.subject,
        "division": session_record.division,
        "classroom": session_record.classroom,
        "date": session_record.session_date.isoformat() if session_record.session_date else None,
        "start_time": session_record.start_time.isoformat() if session_record.start_time else None,
        "end_time": session_record.end_time.isoformat() if session_record.end_time else None,
        "status": session_record.status,
    }


def _serialize_attendance(record):
    return {
        "id": record.id,
        "student_id": record.student.student_id,
        "name": record.student.name,
        "subject": record.session.subject,
        "division": record.session.division,
        "date": record.session.session_date.isoformat(),
        "time": record.timestamp.isoformat(),
        "similarity": record.similarity,
        "status": record.status,
    }


def _student_dashboard(student):
    records = Attendance.query.filter_by(student_id=student.id).join(AttendanceSession).order_by(Attendance.timestamp.desc()).all()
    subject_rows = []
    subjects = (
        AttendanceSession.query.filter_by(division=student.division, status="completed").with_entities(AttendanceSession.subject).distinct().all()
    )
    for (subject,) in subjects:
        total = AttendanceSession.query.filter_by(division=student.division, subject=subject, status="completed").count()
        present = (
            Attendance.query.join(AttendanceSession)
            .filter(Attendance.student_id == student.id, AttendanceSession.division == student.division, AttendanceSession.subject == subject, AttendanceSession.status == "completed")
            .count()
        )
        subject_rows.append({
            "subject": subject,
            "present": present,
            "total": total,
            "percentage": round(present * 100 / total, 1) if total else 0,
        })
    total_sessions = sum(row["total"] for row in subject_rows)
    completed_present = sum(row["present"] for row in subject_rows)
    attendance_percentage = round(completed_present * 100 / total_sessions, 1) if total_sessions else 0
    return {
        "role": "student",
        "student": _serialize_student(student),
        "attendance_percentage": attendance_percentage,
        "subjects": subject_rows,
        "records": [_serialize_attendance(row) for row in records],
        "announcements": [_serialize_announcement(row) for row in Announcement.query.filter((Announcement.division == None) | (Announcement.division == student.division)).order_by(Announcement.created_at.desc()).limit(10).all()],
    }


def _teacher_dashboard():
    sessions = AttendanceSession.query.order_by(AttendanceSession.session_date.desc(), AttendanceSession.id.desc()).limit(10).all()
    active_session = AttendanceSession.query.filter_by(status="active").order_by(AttendanceSession.id.desc()).first()
    return {
        "role": "teacher",
        "student_count": Student.query.count(),
        "active_session": _serialize_session(active_session) if active_session else None,
        "sessions": [_serialize_session(row) for row in sessions],
        "recent_attendance": [_serialize_attendance(row) for row in Attendance.query.order_by(Attendance.timestamp.desc()).limit(8).all()],
    }


def _admin_dashboard():
    student_count = Student.query.count()
    teacher_count = User.query.filter_by(role="teacher").count()
    active_session = AttendanceSession.query.filter_by(status="active").order_by(AttendanceSession.id.desc()).first()
    present_count = Attendance.query.filter(Attendance.timestamp >= date.today()).count()
    return {
        "role": "admin",
        "student_count": student_count,
        "teacher_count": teacher_count,
        "present_count": present_count,
        "active_session": _serialize_session(active_session) if active_session else None,
        "recent_attendance": [_serialize_attendance(row) for row in Attendance.query.order_by(Attendance.timestamp.desc()).limit(8).all()],
    }


def _serialize_student(student):
    return {
        "id": student.id,
        "student_id": student.student_id,
        "name": student.name,
        "roll_number": student.roll_number,
        "department": student.department,
        "division": student.division,
        "email": student.email,
    }
