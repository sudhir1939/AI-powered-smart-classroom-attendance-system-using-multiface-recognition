import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from flask import Blueprint, current_app, render_template, request, redirect, url_for, session, flash
from database.db import db
from models.audit import PasswordResetToken
from models.user import User
from services.audit_service import record_audit

_failed_logins = {}

auth_bp = Blueprint("auth", __name__)


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("auth.login"))
            if session.get("role") not in roles:
                flash("You do not have permission to open that page.", "error")
                return redirect(url_for("dashboard.index"))
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


staff_required = role_required("admin", "teacher")
admin_required = role_required("admin")
student_required = role_required("student")


def _login_for_role(expected_role=None):
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        attempts = _failed_logins.get(username, [])
        now = datetime.utcnow()
        attempts = [stamp for stamp in attempts if now - stamp < timedelta(minutes=10)]
        if len(attempts) >= 5:
            flash("Too many failed attempts. Try again in a few minutes.", "error")
            endpoint = {"student": "auth.student_login", "teacher": "auth.teacher_login"}.get(expected_role, "auth.login")
            return redirect(url_for(endpoint))
        if user and user.check_password(password) and (expected_role is None or user.role == expected_role):
            _failed_logins.pop(username, None)
            session.clear()
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            session["student_id"] = user.student_id
            record_audit("login", "user", user.id)
            db.session.commit()
            return redirect(url_for("dashboard.index"))

        _failed_logins[username] = attempts + [now]
        if user:
            record_audit("failed_login", "user", user.id)
            db.session.commit()
        flash("Invalid username or password.")
        endpoint = {"student": "auth.student_login", "teacher": "auth.teacher_login"}.get(expected_role, "auth.login")
        return redirect(url_for(endpoint))

    return render_template("login.html", login_role=expected_role)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    return _login_for_role()


@auth_bp.route("/student-login", methods=["GET", "POST"])
def student_login():
    return _login_for_role("student")


@auth_bp.route("/teacher-login", methods=["GET", "POST"])
def teacher_login():
    return _login_for_role("teacher")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        user = User.query.filter_by(username=username).first()
        if user and user.email:
            raw_token = secrets.token_urlsafe(32)
            token = PasswordResetToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                expires_at=datetime.utcnow() + timedelta(minutes=current_app.config["PASSWORD_RESET_MINUTES"]),
            )
            db.session.add(token)
            db.session.commit()
            _send_reset_email(user, raw_token)
        flash("If the account has an email address, reset instructions have been sent.", "success")
        return redirect(url_for("auth.login"))
    return render_template("forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    token_record = PasswordResetToken.query.filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest(), used_at=None).first()
    if not token_record or token_record.expires_at < datetime.utcnow():
        return render_template("reset_password.html", invalid=True), 400
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        else:
            token_record.user.set_password(password)
            token_record.used_at = datetime.utcnow()
            record_audit("password_reset", "user", token_record.user_id)
            db.session.commit()
            flash("Password updated. You can now sign in.", "success")
            return redirect(url_for("auth.login"))
    return render_template("reset_password.html", invalid=False)


def _send_reset_email(user, raw_token):
    host = current_app.config["SMTP_HOST"]
    if not host:
        current_app.logger.warning("Password reset requested for %s but SMTP_HOST is not configured.", user.username)
        return
    message = EmailMessage()
    message["Subject"] = "FaceLedger password reset"
    message["From"] = current_app.config["SMTP_FROM"] or current_app.config["SMTP_USERNAME"]
    message["To"] = user.email
    message.set_content(f"Reset your FaceLedger password at {url_for('auth.reset_password', token=raw_token, _external=True)}")
    with smtplib.SMTP(host, current_app.config["SMTP_PORT"]) as smtp:
        smtp.starttls()
        if current_app.config["SMTP_USERNAME"]:
            smtp.login(current_app.config["SMTP_USERNAME"], current_app.config["SMTP_PASSWORD"])
        smtp.send_message(message)