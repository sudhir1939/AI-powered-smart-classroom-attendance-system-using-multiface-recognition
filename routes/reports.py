import io
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from flask import Blueprint, Response, render_template, request
from sqlalchemy import and_, or_

from database.db import db
from models.attendance import Attendance
from models.session import AttendanceSession
from models.student import Student
from routes.auth import staff_required

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@dataclass(frozen=True)
class ReportRow:
    student: Student
    session: AttendanceSession
    timestamp: datetime | None
    similarity: float | None
    status: str


def filtered_rows():
    query = (
        db.session.query(Student, AttendanceSession, Attendance)
        .join(AttendanceSession, Student.division == AttendanceSession.division)
        .outerjoin(
            Attendance,
            and_(Attendance.student_id == Student.id, Attendance.session_id == AttendanceSession.id),
        )
        .filter(or_(Attendance.id.isnot(None), AttendanceSession.status == "completed"))
    )
    date_value = request.args.get("date", "").strip()
    subject = request.args.get("subject", "").strip()
    division = request.args.get("division", "").strip()
    search = request.args.get("q", "").strip()
    if date_value:
        query = query.filter(AttendanceSession.session_date == date_value)
    if subject:
        query = query.filter(AttendanceSession.subject.ilike(f"%{subject}%"))
    if division:
        query = query.filter(AttendanceSession.division == division)
    if search:
        query = query.filter(Student.name.ilike(f"%{search}%") | Student.student_id.ilike(f"%{search}%"))
    records = query.order_by(AttendanceSession.session_date.desc(), Attendance.timestamp.desc(), Student.name).all()
    return [
        ReportRow(
            student=student,
            session=session_record,
            timestamp=attendance.timestamp if attendance else None,
            similarity=attendance.similarity if attendance else None,
            status=attendance.status if attendance else "Absent",
        )
        for student, session_record, attendance in records
    ]


@reports_bp.route("")
@staff_required
def index():
    rows = filtered_rows()
    divisions = sorted({student.division for student in Student.query.all()})
    summary = {}
    for row in rows:
        key = row.session.subject
        summary.setdefault(key, {"present": 0, "absent": 0})
        summary[key]["present" if row.status in {"Present", "Late"} else "absent"] += 1
    return render_template("reports.html", rows=rows, divisions=divisions, filters=request.args, summary=summary)


@reports_bp.route("/export/<string:file_type>")
@staff_required
def export(file_type):
    rows = filtered_rows()
    data = [{"Student ID": row.student.student_id, "Name": row.student.name, "Subject": row.session.subject, "Division": row.session.division, "Date": row.session.session_date.isoformat(), "Time": row.timestamp.strftime("%H:%M:%S") if row.timestamp else "", "Similarity": row.similarity if row.similarity is not None else "", "Status": row.status} for row in rows]
    frame = pd.DataFrame(data)
    if file_type == "csv":
        return Response(frame.to_csv(index=False), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=attendance_report.csv"})
    if file_type == "excel":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="Attendance")
        output.seek(0)
        return Response(output.getvalue(), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=attendance_report.xlsx"})
    if file_type == "pdf":
        output = io.BytesIO()
        document = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
        table_data = [["Student ID", "Name", "Subject", "Division", "Date", "Time", "Status"]]
        table_data.extend([
            [row.student.student_id, row.student.name, row.session.subject, row.session.division, row.session.session_date.isoformat(), row.timestamp.strftime("%H:%M:%S") if row.timestamp else "--", row.status]
            for row in rows
        ])
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172033")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6fa")]),
        ]))
        document.build([table])
        return Response(output.getvalue(), mimetype="application/pdf", headers={"Content-Disposition": "attachment; filename=attendance_report.pdf"})
    return Response("Unsupported export type", status=400)
