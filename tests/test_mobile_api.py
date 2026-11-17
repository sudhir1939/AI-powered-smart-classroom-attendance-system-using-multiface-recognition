from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import load_workbook
import pytest
import numpy as np

from app import create_app
from database.db import db
from models.announcement import Announcement
from models.attendance import Attendance
from models.session import AttendanceSession
from models.student import Student
from models.user import User
from recognition.engine import DetectedFace, RecognitionModelLoading


@pytest.fixture
def client():
    with TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "test_mobile_api.sqlite3"
        app = create_app(test_db_uri=f"sqlite:///{database_path}")
        app.config.update(TESTING=True)
        with app.app_context():
            db.create_all()
            yield app.test_client()
            db.session.remove()
            db.drop_all()
            db.engine.dispose()


def test_student_login_and_dashboard(client):
    student = Student(
        student_id="S-100",
        roll_number="100",
        name="Ava Student",
        department="Computer Science",
        division="CS-A",
    )
    db.session.add(student)
    db.session.commit()

    account = User(username="S-100", role="student", student_id=student.id)
    account.set_password("student-pass")
    db.session.add(account)
    db.session.commit()

    response = client.post(
        "/api/auth/login",
        json={"username": "S-100", "password": "student-pass"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["user"]["role"] == "student"
    assert payload["user"]["student_id"] == student.student_id
    assert payload["user"]["name"] == "Ava Student"

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    data = dashboard.get_json()
    assert data["role"] == "student"
    assert data["student"]["name"] == "Ava Student"
    assert data["announcements"] == []


def test_teacher_dashboard_lists_sessions_and_students(client):
    student = Student(
        student_id="S-200",
        roll_number="200",
        name="Noah Teacher",
        department="Computer Science",
        division="CS-B",
    )
    db.session.add(student)
    session_record = AttendanceSession(
        subject="Algorithms",
        division="CS-B",
        session_date=date.today(),
        status="active",
    )
    db.session.add(session_record)
    db.session.commit()

    account = User(username="teacher1", role="teacher", full_name="Teacher One")
    account.set_password("teacher-pass")
    db.session.add(account)
    db.session.commit()

    login = client.post(
        "/api/auth/login",
        json={"username": "teacher1", "password": "teacher-pass"},
    )
    assert login.status_code == 200

    dashboard = client.get("/api/dashboard")
    assert dashboard.status_code == 200
    data = dashboard.get_json()
    assert data["role"] == "teacher"
    assert data["student_count"] == 1
    assert data["active_session"]["subject"] == "Algorithms"
    assert data["sessions"][0]["subject"] == "Algorithms"


def test_student_login_requires_valid_credentials(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "missing", "password": "bad"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid username or password."


def test_registration_login_and_attendance_are_shared_across_portals(client, monkeypatch):
    admin = User(username="admin", role="admin", full_name="Admin User")
    admin.set_password("admin-pass")
    db.session.add(admin)
    db.session.commit()

    admin_login = client.post("/login", data={"username": "admin", "password": "admin-pass"})
    assert admin_login.status_code == 302
    created_teacher = client.post(
        "/admin/users",
        data={
            "username": "teacher1",
            "password": "teacher-pass",
            "full_name": "Teacher One",
        },
    )
    assert created_teacher.status_code == 302

    client.get("/logout")
    teacher_login = client.post(
        "/teacher-login",
        data={"username": "teacher1", "password": "teacher-pass"},
    )
    assert teacher_login.status_code == 302
    assert b"Teacher dashboard" in client.get("/dashboard").data

    client.application.config["FACE_REGISTRATION_SAMPLES"] = 5
    monkeypatch.setattr("routes.students.engine.decode_image", lambda _frame: object())
    monkeypatch.setattr(
        "routes.students.engine.detect",
        lambda _image: [DetectedFace((0, 0, 10, 10), np.array([1.0, 0.0], dtype=np.float32))],
    )
    registration = {
        "student_id": "S-300",
        "roll_number": "300",
        "name": "Mia Student",
        "department": "Computer Science",
        "division": "CS-C",
        "frames": ["frame"] * 5,
    }
    missing_password = client.post("/students/api/register", json=registration)
    assert missing_password.status_code == 400
    assert Student.query.filter_by(student_id="S-300").first() is None

    registration["account_password"] = "student-pass"
    registered = client.post("/students/api/register", json=registration)
    assert registered.status_code == 200
    student = Student.query.filter_by(student_id="S-300").one()
    assert User.query.filter_by(username="S-300", student_id=student.id).one()

    session_record = AttendanceSession(
        subject="Algorithms",
        division="CS-C",
        session_date=date.today(),
        status="active",
    )
    db.session.add(session_record)
    db.session.commit()
    monkeypatch.setattr("routes.attendance.engine.decode_image", lambda _image: object())
    monkeypatch.setattr(
        "routes.attendance.engine.detect",
        lambda _image: [DetectedFace((0, 0, 10, 10), np.array([1.0, 0.0], dtype=np.float32))],
    )
    monkeypatch.setattr(
        "routes.attendance._recognize_face",
        lambda _face, students: (students[0], 0.95, True),
    )
    monkeypatch.setattr("routes.attendance.liveness.observe", lambda *_args: True)
    marked = client.post(f"/attendance/api/{session_record.id}/frame", json={"image": "frame"})
    assert marked.status_code == 200
    assert marked.get_json()["faces"][0]["new"] is True

    finished = client.post(f"/attendance/{session_record.id}/finish")
    assert finished.status_code == 302
    report_query = "?q=Mia+Student&date={}&subject=Algorithms&division=CS-C".format(date.today().isoformat())
    report = client.get(f"/reports{report_query}")
    assert b"Mia Student" in report.data
    assert b"Algorithms" in report.data
    csv_export = client.get(f"/reports/export/csv{report_query}")
    assert csv_export.status_code == 200
    assert b"Mia Student" in csv_export.data
    excel_export = client.get(f"/reports/export/excel{report_query}")
    assert excel_export.status_code == 200
    workbook = load_workbook(BytesIO(excel_export.data), read_only=True)
    assert list(workbook.active.values)[1][1] == "Mia Student"

    client.get("/logout")
    student_login = client.post(
        "/student-login",
        data={"username": "S-300", "password": "student-pass"},
        follow_redirects=True,
    )
    assert student_login.status_code == 200
    assert b"Algorithms" in student_login.data
    assert b"100.0%" in student_login.data

    client.get("/logout")
    mobile_student_login = client.post(
        "/api/auth/login",
        json={"username": "S-300", "password": "student-pass"},
    )
    assert mobile_student_login.status_code == 200
    student_dashboard = client.get("/api/dashboard").get_json()
    assert student_dashboard["attendance_percentage"] == 100.0
    assert student_dashboard["records"][0]["subject"] == "Algorithms"

    client.post("/api/auth/logout")
    client.post(
        "/api/auth/login",
        json={"username": "teacher1", "password": "teacher-pass"},
    )
    teacher_dashboard = client.get("/api/dashboard").get_json()
    assert teacher_dashboard["recent_attendance"][0]["name"] == "Mia Student"

    client.post("/api/auth/logout")
    client.post("/login", data={"username": "admin", "password": "admin-pass"})
    admin_dashboard = client.get("/dashboard")
    assert b"Mia Student" in admin_dashboard.data


def test_completed_session_reports_absences_and_exports_them(client):
    student = Student(
        student_id="S-400",
        roll_number="400",
        name="Ivy Absent",
        department="Computer Science",
        division="CS-D",
    )
    teacher = User(username="teacher2", role="teacher", full_name="Teacher Two")
    teacher.set_password("teacher-pass")
    session_record = AttendanceSession(
        subject="Networks",
        division="CS-D",
        session_date=date.today(),
        status="completed",
    )
    db.session.add_all([student, teacher, session_record])
    db.session.commit()

    login = client.post(
        "/teacher-login",
        data={"username": "teacher2", "password": "teacher-pass"},
    )
    assert login.status_code == 302
    assert Attendance.query.count() == 0

    report = client.get("/reports")
    assert b"Ivy Absent" in report.data
    assert b"Absent" in report.data
    assert b"--" in report.data

    csv_export = client.get("/reports/export/csv")
    assert b"Ivy Absent" in csv_export.data
    assert b"Absent" in csv_export.data

    excel_export = client.get("/reports/export/excel")
    workbook = load_workbook(BytesIO(excel_export.data), read_only=True)
    exported_rows = list(workbook.active.values)
    assert exported_rows[1][1] == "Ivy Absent"
    assert exported_rows[1][-1] == "Absent"


def test_attendance_frame_reports_model_loading_without_waiting(client, monkeypatch):
    teacher = User(username="teacher3", role="teacher", full_name="Teacher Three")
    teacher.set_password("teacher-pass")
    session_record = AttendanceSession(
        subject="Operating Systems",
        division="CS-E",
        session_date=date.today(),
        status="active",
    )
    db.session.add_all([teacher, session_record])
    db.session.commit()

    client.post("/teacher-login", data={"username": "teacher3", "password": "teacher-pass"})
    monkeypatch.setattr("routes.attendance.engine.decode_image", lambda _image: object())
    monkeypatch.setattr("routes.attendance.engine.detect", lambda _image: (_ for _ in ()).throw(RecognitionModelLoading("Model loading")))
    monkeypatch.setattr("routes.attendance.engine.start_loading", lambda: None)

    response = client.post(f"/attendance/api/{session_record.id}/frame", json={"image": "frame"})

    assert response.status_code == 503
    assert response.get_json()["loading"] is True
