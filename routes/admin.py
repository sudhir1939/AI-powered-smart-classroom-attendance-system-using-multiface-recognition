import io
import os
import sqlite3
from datetime import datetime, timedelta
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, session, send_file

from database.db import db
from models.student import Student
from models.user import User
from models.audit import AuditLog
from models.embedding import FaceEmbedding
from models.subject import Subject
from routes.auth import admin_required
from services.audit_service import record_audit

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        department = request.form.get("department", "").strip()
        phone = request.form.get("phone", "").strip()
        role = "teacher"
        if not username or not full_name or len(password) < 8:
            flash("Username and full name are required; password must contain at least 8 characters.", "error")
        elif User.query.filter_by(username=username).first():
            flash("That username already exists.", "error")
        else:
            account = User(username=username, role=role, full_name=full_name, email=email, department=department, phone=phone)
            account.set_password(password)
            db.session.add(account)
            db.session.commit()
            flash(f"{role.title()} account created for {username}.", "success")
            return redirect(url_for("admin.users"))
    accounts = User.query.order_by(User.role, User.username).all()
    return render_template("admin_users.html", accounts=accounts)


@admin_bp.route("/subjects", methods=["GET", "POST"])
@admin_required
def subjects():
    if request.method == "POST":
        division = request.form.get("division", "").strip()
        name = request.form.get("name", "").strip()
        if not division or not name:
            flash("Division and subject name are required.", "error")
        elif Subject.query.filter_by(division=division, name=name).first():
            flash("That subject already exists for this division.", "error")
        else:
            db.session.add(Subject(division=division, name=name))
            record_audit("subject_created", "subject", None, division=division, name=name)
            db.session.commit()
            flash("Subject added to the division.", "success")
            return redirect(url_for("admin.subjects"))
    subjects = Subject.query.order_by(Subject.division, Subject.name).all()
    divisions = [row[0] for row in db.session.query(Student.division).distinct().order_by(Student.division).all()]
    return render_template("admin_subjects.html", subjects=subjects, divisions=divisions)


@admin_bp.post("/subjects/<int:subject_id>/delete")
@admin_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    record_audit("subject_deleted", "subject", subject.id, division=subject.division, name=subject.name)
    db.session.delete(subject)
    db.session.commit()
    flash("Subject removed from the division.", "success")
    return redirect(url_for("admin.subjects"))


@admin_bp.post("/users/<int:user_id>/delete")
@admin_required
def delete_user(user_id):
    account = User.query.get_or_404(user_id)
    if account.id == session.get("user_id"):
        flash("You cannot delete the current account.", "error")
    elif account.role == "admin" and User.query.filter_by(role="admin").count() <= 1:
        flash("Keep at least one administrator account.", "error")
    else:
        db.session.delete(account)
        db.session.commit()
        flash("Account deleted.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.get("/audit")
@admin_required
def audit():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(250).all()
    return render_template("admin_audit.html", logs=logs)


@admin_bp.post("/retention")
@admin_required
def retention():
    cutoff = datetime.utcnow() - timedelta(days=current_app.config["BIOMETRIC_RETENTION_DAYS"])
    deleted = FaceEmbedding.query.filter(FaceEmbedding.created_at < cutoff).delete(synchronize_session=False)
    record_audit("biometric_retention_cleanup", "face_embedding", None, deleted=deleted)
    db.session.commit()
    flash(f"Removed {deleted} face samples older than the retention period.", "success")
    return redirect(url_for("admin.audit"))


@admin_bp.get("/backup")
@admin_required
def backup():
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if not uri.startswith("sqlite:///"):
        return "Backups are currently implemented for SQLite deployments only.", 400
    path = uri.replace("sqlite:///", "", 1)
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    if not os.path.exists(path):
        return "Database file not found.", 404
    output = io.BytesIO()
    source = sqlite3.connect(path)
    destination = sqlite3.connect(":memory:")
    source.backup(destination)
    for line in destination.iterdump():
        output.write((line + "\n").encode("utf-8"))
    source.close()
    destination.close()
    output.seek(0)
    record_audit("database_backup", "database")
    db.session.commit()
    return send_file(output, mimetype="application/sql", as_attachment=True, download_name=f"faceledger-backup-{datetime.utcnow():%Y%m%d%H%M%S}.sql")
