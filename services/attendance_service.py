from datetime import datetime

from database.db import db
from models.attendance import Attendance
from models.session import AttendanceSession
from models.student import Student
from services.audit_service import record_audit


def mark_present(session, student, similarity):
    existing = Attendance.query.filter_by(session_id=session.id, student_id=student.id).first()
    if existing:
        return existing, False
    record = Attendance(
        session_id=session.id,
        student_id=student.id,
        similarity=round(float(similarity), 4),
        timestamp=datetime.utcnow(),
        status="Present",
    )
    db.session.add(record)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        existing = Attendance.query.filter_by(session_id=session.id, student_id=student.id).first()
        if existing:
            return existing, False
        raise
    return record, True


def correct_attendance(record, status, reason, user_id):
    record.status = status
    record.corrected_at = datetime.utcnow()
    record.corrected_by = user_id
    record.correction_reason = reason
    record.timestamp = record.timestamp or datetime.utcnow()
    record.similarity = record.similarity or 0
    record_audit("attendance_corrected", "attendance", record.id, status=status, reason=reason, user_id=user_id)
    db.session.commit()
    return record


def session_counts(session):
    total = Student.query.filter_by(division=session.division).count()
    present = Attendance.query.filter_by(session_id=session.id, status="Present").count()
    return total, present, max(total - present, 0)
