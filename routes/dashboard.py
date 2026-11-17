from datetime import date

from flask import Blueprint, current_app, render_template, redirect, url_for, session
from sqlalchemy import func

from database.db import db
from models.attendance import Attendance
from models.session import AttendanceSession
from models.student import Student
from models.user import User
from models.announcement import Announcement
from routes.auth import login_required


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def index():
    if session.get("role") == "student":
        student = Student.query.get(session.get("student_id"))
        records = Attendance.query.filter_by(student_id=student.id).join(AttendanceSession).order_by(Attendance.timestamp.desc()).all() if student else []
        subject_rows = []
        if student:
            subjects = db.session.query(AttendanceSession.subject).filter_by(division=student.division, status="completed").distinct().all()
            for (subject,) in subjects:
                total = AttendanceSession.query.filter_by(division=student.division, subject=subject, status="completed").count()
                present = Attendance.query.join(AttendanceSession).filter(Attendance.student_id == student.id, AttendanceSession.division == student.division, AttendanceSession.subject == subject, AttendanceSession.status == "completed").count()
                subject_rows.append({"subject": subject, "present": present, "total": total, "percentage": round(present * 100 / total, 1) if total else 0})
        total_sessions = sum(row["total"] for row in subject_rows)
        completed_present = sum(row["present"] for row in subject_rows)
        attendance_percentage = round(completed_present * 100 / total_sessions, 1) if total_sessions else 0
        announcements = Announcement.query.filter((Announcement.division == None) | (Announcement.division == student.division)).order_by(Announcement.created_at.desc()).limit(10).all() if student else []
        alert = attendance_percentage < current_app.config["ATTENDANCE_ALERT_THRESHOLD"] if total_sessions else False
        return render_template("student_dashboard.html", student=student, records=records, announcements=announcements, attendance_percentage=attendance_percentage, subject_rows=subject_rows, attendance_alert=alert)
    if session.get("role") == "teacher":
        sessions = AttendanceSession.query.order_by(AttendanceSession.session_date.desc(), AttendanceSession.id.desc()).limit(10).all()
        return render_template("teacher_dashboard.html", sessions=sessions, student_count=Student.query.count(), active_session=AttendanceSession.query.filter_by(status="active").first())
    student_count = Student.query.count()
    present_count = Attendance.query.filter(func.date(Attendance.timestamp) == date.today().isoformat()).count()
    active_session = AttendanceSession.query.filter_by(status="active").order_by(AttendanceSession.id.desc()).first()
    recent = Attendance.query.order_by(Attendance.timestamp.desc()).limit(8).all()
    return render_template("admin_dashboard.html", student_count=student_count, present_count=present_count, active_session=active_session, recent=recent, teacher_count=User.query.filter_by(role="teacher").count())
