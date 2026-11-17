from datetime import datetime
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import or_

from database.db import db
from models.embedding import FaceEmbedding
from models.student import Student
from models.user import User
from recognition.engine import engine
from routes.auth import admin_required, staff_required, student_required
from services.student_service import create_student, validate_student_form
from services.security_service import encrypt_embedding
from services.audit_service import record_audit

students_bp = Blueprint("students", __name__, url_prefix="/students")


@students_bp.get("/my-profile")
@student_required
def my_profile():
    student = Student.query.get_or_404(session.get("student_id"))
    form = {
        "student_id": student.student_id,
        "roll_number": student.roll_number,
        "name": student.name,
        "department": student.department,
        "division": student.division,
        "email": student.email or "",
    }
    return render_template("register_student.html", form=form, existing_student_id=student.id, self_edit=True)


@students_bp.post("/api/my-profile")
@student_required
def update_my_profile():
    student = Student.query.get_or_404(session.get("student_id"))
    payload = request.get_json(silent=True) or {}
    values = {
        "student_id": student.student_id,
        "roll_number": str(payload.get("roll_number", student.roll_number)).strip(),
        "name": str(payload.get("name", student.name)).strip(),
        "department": str(payload.get("department", student.department)).strip(),
        "division": str(payload.get("division", student.division)).strip(),
        "email": str(payload.get("email", student.email or "")).strip(),
    }
    _, errors = validate_student_form(values)
    if errors:
        return jsonify(ok=False, errors=errors), 400
    frames = payload.get("frames", [])
    vectors = []
    for frame in frames:
        try:
            detected = engine.detect(engine.decode_image(frame))
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        if len(detected) == 1 and detected[0].embedding is not None and not getattr(detected[0], "quality_flags", ()):
            vectors.append(detected[0].embedding)
    minimum_vectors = max(5, int(current_app.config["FACE_REGISTRATION_SAMPLES"] * 0.6))
    if len(vectors) < minimum_vectors:
        return jsonify(ok=False, error=f"Capture at least {minimum_vectors} clear face samples."), 400
    FaceEmbedding.query.filter_by(student_id=student.id).delete()
    for vector in vectors:
        db.session.add(FaceEmbedding(
            student_id=student.id,
            embedding=encrypt_embedding(engine.serialize_embedding(vector)),
            dimension=len(vector),
            encrypted=True,
        ))
    for key in ("roll_number", "name", "department", "division", "email"):
        setattr(student, key, values[key])
    student.consent_at = datetime.utcnow()
    student.consent_version = "1"
    record_audit("student_profile_updated", "student", student.id)
    db.session.commit()
    return jsonify(ok=True)


@students_bp.route("")
@staff_required
def index():
    query = request.args.get("q", "").strip()
    students_query = Student.query
    if query:
        pattern = f"%{query}%"
        students_query = students_query.filter(or_(Student.student_id.ilike(pattern), Student.name.ilike(pattern), Student.roll_number.ilike(pattern)))
    return render_template("students.html", students=students_query.order_by(Student.name).all(), query=query)


@students_bp.route("/register", methods=["GET", "POST"])
@staff_required
def register():
    if request.method == "POST":
        values, errors = validate_student_form(request.form)
        if Student.query.filter_by(student_id=values["student_id"]).first():
            errors.append("Student ID already exists.")
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("register_student.html", form=values)
        return render_template("register_student.html", form=values, begin_capture=True)
    return render_template("register_student.html", form={})


@students_bp.get("/<int:student_id>/recapture")
@staff_required
def recapture(student_id):
    student = Student.query.get_or_404(student_id)
    form = {"student_id": student.student_id, "roll_number": student.roll_number, "name": student.name, "department": student.department, "division": student.division, "email": student.email or ""}
    return render_template("register_student.html", form=form, existing_student_id=student.id)


@students_bp.post("/api/register")
@staff_required
def register_api():
    payload = request.get_json(silent=True) or {}
    values = {key: str(payload.get(key, "")).strip() for key in ("student_id", "roll_number", "name", "department", "division", "email")}
    account_password = str(payload.get("account_password", ""))
    existing_student_id = payload.get("existing_student_id")
    existing_student = Student.query.get(existing_student_id) if existing_student_id else None
    _, errors = validate_student_form(values)
    if not existing_student and len(account_password) < 8:
        errors.append("Student portal password must contain at least 8 characters.")
    elif account_password and len(account_password) < 8:
        errors.append("Student portal password must contain at least 8 characters.")
    if not existing_student and User.query.filter_by(username=values["student_id"]).first():
        errors.append("That Student ID already has a portal account.")
    duplicate = Student.query.filter_by(student_id=values["student_id"]).first()
    if duplicate and (not existing_student or duplicate.id != existing_student.id):
        errors.append("Student ID already exists.")
    if errors:
        return jsonify(ok=False, errors=errors), 400
    frames = payload.get("frames", [])
    vectors = []
    quality_warnings = []
    for frame in frames:
        try:
            detected = engine.detect(engine.decode_image(frame))
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 400
        if len(detected) != 1 or detected[0].embedding is None:
            continue
        if getattr(detected[0], "quality_flags", ()):
            quality_warnings.extend(detected[0].quality_flags)
            continue
        vectors.append(detected[0].embedding)
    minimum_vectors = max(5, int(current_app.config["FACE_REGISTRATION_SAMPLES"] * 0.6))
    if len(vectors) < minimum_vectors:
        if engine.status.startswith("InsightFace unavailable"):
            message = f"Only {len(vectors)} usable face samples were found. At least {minimum_vectors} are required. Keep one face visible, improve lighting, and try again."
        else:
            message = f"Only {len(vectors)} usable face samples were found. At least {minimum_vectors} are required. Ensure the face is visible and try again."
        return jsonify(ok=False, error=message), 400
    try:
        student = existing_student
        if student:
            FaceEmbedding.query.filter_by(student_id=student.id).delete()
            for vector in vectors:
                db.session.add(FaceEmbedding(student_id=student.id, embedding=encrypt_embedding(engine.serialize_embedding(vector)), dimension=len(vector), encrypted=True))
            for key, value in values.items():
                setattr(student, key, value)
            student.consent_at = datetime.utcnow()
            student.consent_version = "1"
            db.session.commit()
        else:
            student = create_student(values, vectors, account_password)
            student.consent_at = datetime.utcnow()
            student.consent_version = "1"
            db.session.commit()
        record_audit("student_face_data_updated", "student", student.id, quality_warnings=sorted(set(quality_warnings)))
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify(ok=False, error="The student could not be saved."), 500
    return jsonify(ok=True, student_id=student.student_id)


@students_bp.post("/<int:student_id>/delete")
@admin_required
def delete(student_id):
    student = Student.query.get_or_404(student_id)
    account = User.query.filter_by(student_id=student.id).first()
    if account:
        db.session.delete(account)
    db.session.delete(student)
    db.session.commit()
    record_audit("student_deleted", "student", student_id)
    db.session.commit()
    flash("Student profile, portal login, embeddings, and attendance records deleted.", "success")
    return redirect(url_for("students.index"))
