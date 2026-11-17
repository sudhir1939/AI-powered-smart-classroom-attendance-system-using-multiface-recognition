from datetime import date, datetime

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from database.db import db
from models.attendance import Attendance
from models.session import AttendanceSession
from models.student import Student
from models.subject import Subject
from recognition.engine import RecognitionModelLoading, engine
from recognition.liveness import liveness
from routes.auth import staff_required
from services.attendance_service import correct_attendance, mark_present, session_counts
from services.security_service import decrypt_embedding
from services.audit_service import record_audit

attendance_bp = Blueprint("attendance", __name__, url_prefix="/attendance")


@attendance_bp.route("/new", methods=["GET", "POST"])
@staff_required
def new_session():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        division = request.form.get("division", "").strip()
        if not subject or not division:
            flash("Subject and division are required.", "error")
        elif not Subject.query.filter_by(name=subject, division=division, active=True).first():
            flash("Choose a subject configured for the selected division.", "error")
        else:
            classroom = request.form.get("classroom", "").strip()
            session_record = AttendanceSession(
                subject=subject,
                division=division,
                classroom=classroom or None,
                created_by=session.get("user_id"),
                session_date=date.today(),
                status="draft",
            )
            db.session.add(session_record)
            db.session.commit()
            record_audit("session_created", "attendance_session", session_record.id, subject=subject, division=division)
            db.session.commit()
            return redirect(url_for("attendance.live", session_id=session_record.id))
    divisions = [row[0] for row in db.session.query(Student.division).distinct().order_by(Student.division).all()]
    return render_template("create_session.html", divisions=divisions)


@attendance_bp.get("/api/subjects")
@staff_required
def subjects_for_division():
    division = request.args.get("division", "").strip()
    subjects = Subject.query.filter_by(division=division, active=True).order_by(Subject.name).all() if division else []
    return jsonify({"subjects": [{"id": item.id, "name": item.name} for item in subjects]})


@attendance_bp.route("/live/<int:session_id>")
@staff_required
def live(session_id):
    session_record = AttendanceSession.query.get_or_404(session_id)
    if session_record.status == "draft":
        session_record.status = "active"
        session_record.start_time = datetime.now().time().replace(microsecond=0)
        db.session.commit()
    total, present, absent = session_counts(session_record)
    return render_template("live_attendance.html", attendance_session=session_record, total=total, present=present, absent=absent, model_status=engine.status)


@attendance_bp.post("/api/<int:session_id>/frame")
@staff_required
def process_frame(session_id):
    session_record = AttendanceSession.query.get_or_404(session_id)
    if session_record.status != "active":
        return jsonify(ok=False, error="This attendance session is not active."), 400
    payload = request.get_json(silent=True) or {}
    try:
        faces = engine.detect(engine.decode_image(payload.get("image", "")))
    except RecognitionModelLoading as exc:
        return jsonify(ok=False, loading=True, error=str(exc), model_status=engine.status), 503
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    stored = []
    students = Student.query.filter_by(division=session_record.division).all()
    for face_index, face in enumerate(faces):
        if face.embedding is None:
            stored.append({"box": face.box, "name": "Unknown", "similarity": None, "quality_score": face.quality_score, "quality_flags": list(face.quality_flags), "new": False})
            continue
        best_student, best_score, recognized = _recognize_face(face, students)
        is_new = False
        live = liveness.observe(session_record.id, face_index, face.box)
        attendance_recorded = False
        if recognized and _quality_allows_attendance(face):
            record, is_new = mark_present(session_record, best_student, best_score)
            attendance_recorded = record.status in {"Present", "Late"}
        attendance_allowed = _quality_allows_attendance(face)
        stored.append({"box": face.box, "name": best_student.name if recognized and attendance_allowed else "Unknown", "student_id": best_student.student_id if recognized and attendance_allowed else None, "similarity": round(best_score, 3) if recognized else None, "quality_score": face.quality_score, "quality_flags": list(face.quality_flags), "new": is_new, "live": live, "recognized": recognized, "attendance_recorded": attendance_recorded, "quality_blocked": not attendance_allowed})
    total, present, absent = session_counts(session_record)
    return jsonify(ok=True, faces=stored, counts={"total": total, "present": present, "absent": absent}, model_status=engine.status)


def _match_faces(session_record, faces):
    students = Student.query.filter_by(division=session_record.division).all()
    matches = []
    for face in faces:
        if face.embedding is None:
            matches.append({"name": "Unknown", "student_id": None, "similarity": None, "new": False})
            continue
        best_student, best_score, recognized = _recognize_face(face, students)
        is_new = False
        attendance_recorded = False
        if recognized and _quality_allows_attendance(face):
            record, is_new = mark_present(session_record, best_student, best_score)
            attendance_recorded = record.status in {"Present", "Late"}
        matches.append({
            "name": best_student.name if recognized and _quality_allows_attendance(face) else "Unknown",
            "student_id": best_student.student_id if recognized and _quality_allows_attendance(face) else None,
            "similarity": round(best_score, 3) if recognized else None,
            "quality_score": face.quality_score,
            "quality_flags": list(face.quality_flags),
            "attendance_recorded": attendance_recorded,
            "new": is_new,
        })
    return matches


def _quality_allows_attendance(face):
    """Treat quality flags as guidance; only severely low scores block marking."""
    return face.quality_score is None or face.quality_score >= 0.2


def _recognize_face(face, students):
    """Accept only strong, unambiguous matches; otherwise return Unknown."""
    if face.embedding is None:
        return None, -1.0, False
    student_scores = []
    for student in students:
        scores = []
        for embedding in student.embeddings:
            raw_embedding = decrypt_embedding(embedding.embedding, getattr(embedding, "encrypted", False))
            vector = engine.deserialize_embedding(raw_embedding, embedding.dimension)
            if vector.shape != face.embedding.shape:
                continue
            scores.append(engine.similarity(face.embedding, vector))
        if scores:
            if engine.using_insightface:
                representative_score = max(scores)
            else:
                representative_score = sum(scores) / len(scores)
            student_scores.append((representative_score, student, scores))
    student_scores.sort(key=lambda item: item[0], reverse=True)
    if not student_scores:
        return None, -1.0, False
    best_score, best_student, best_samples = student_scores[0]
    second_score = student_scores[1][0] if len(student_scores) > 1 else -1.0
    threshold = current_app.config["FACE_RECOGNITION_THRESHOLD"] if engine.using_insightface else current_app.config["FACE_FALLBACK_THRESHOLD"]
    margin_ok = len(student_scores) == 1 or best_score - second_score >= current_app.config["FACE_RECOGNITION_MARGIN"]
    fallback_consistent = engine.using_insightface or (
        len(best_samples) >= current_app.config["FACE_FALLBACK_MIN_SAMPLES"]
        and sum(score >= threshold for score in best_samples) >= current_app.config["FACE_FALLBACK_MIN_SAMPLES"]
    )
    recognized = best_score >= threshold and margin_ok and fallback_consistent
    return best_student if recognized else None, best_score, recognized


@attendance_bp.post("/api/<int:session_id>/photos")
@staff_required
def process_photos(session_id):
    session_record = AttendanceSession.query.get_or_404(session_id)
    if session_record.status != "active":
        return jsonify(ok=False, error="This attendance session is not active."), 400
    uploads = request.files.getlist("photos")
    if not uploads:
        return jsonify(ok=False, error="Choose at least one image."), 400
    results = []
    for upload in uploads:
        filename = upload.filename or "unnamed image"
        try:
            faces = engine.detect(engine.decode_bytes(upload.read()))
            matches = _match_faces(session_record, faces)
            results.append({"filename": filename, "faces": len(faces), "matches": matches})
        except RecognitionModelLoading as exc:
            return jsonify(ok=False, loading=True, error=str(exc), model_status=engine.status), 503
        except ValueError as exc:
            results.append({"filename": filename, "error": str(exc), "faces": 0, "matches": []})
    total, present, absent = session_counts(session_record)
    return jsonify(ok=True, results=results, counts={"total": total, "present": present, "absent": absent})


@attendance_bp.post("/<int:session_id>/finish")
@staff_required
def finish(session_id):
    session_record = AttendanceSession.query.get_or_404(session_id)
    session_record.status = "completed"
    session_record.end_time = datetime.now().time().replace(microsecond=0)
    db.session.commit()
    record_audit("session_finished", "attendance_session", session_record.id)
    db.session.commit()
    return redirect(url_for("dashboard.index"))


@attendance_bp.post("/<int:session_id>/delete")
@staff_required
def delete_session(session_id):
    session_record = AttendanceSession.query.get_or_404(session_id)
    session_id_value = session_record.id
    subject = session_record.subject
    division = session_record.division
    record_audit("session_deleted", "attendance_session", session_id_value, subject=subject, division=division)
    db.session.delete(session_record)
    db.session.commit()
    flash(f"Session '{subject}' for division {division} and its attendance records were deleted.", "success")
    return redirect(url_for("dashboard.index"))


@attendance_bp.post("/<int:session_id>/corrections")
@staff_required
def correction(session_id):
    session_record = AttendanceSession.query.get_or_404(session_id)
    student_id = request.form.get("student_id", type=int)
    status = request.form.get("status", "Present").strip()
    reason = request.form.get("reason", "").strip()
    if status not in {"Present", "Absent", "Excused", "Late"} or not reason:
        flash("Choose a valid status and provide a correction reason.", "error")
        return redirect(url_for("reports.index"))
    record = Attendance.query.filter_by(session_id=session_record.id, student_id=student_id).first()
    if not record:
        record = Attendance(session_id=session_record.id, student_id=student_id, similarity=0, status=status)
        db.session.add(record)
        db.session.flush()
    correct_attendance(record, status, reason, session.get("user_id"))
    flash("Attendance correction saved and added to the audit history.", "success")
    return redirect(url_for("reports.index"))
