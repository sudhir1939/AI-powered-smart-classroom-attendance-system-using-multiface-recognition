from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from database.db import db
from models.announcement import Announcement
from models.student import Student
from routes.auth import staff_required

announcements_bp = Blueprint("announcements", __name__, url_prefix="/announcements")


@announcements_bp.route("", methods=["GET", "POST"])
@staff_required
def index():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        division = request.form.get("division", "").strip() or None
        if not title or not body:
            flash("Title and message are required.", "error")
        else:
            announcement = Announcement(title=title, body=body, division=division, author_id=request_user_id())
            db.session.add(announcement)
            db.session.commit()
            flash("Announcement published.", "success")
            return redirect(url_for("announcements.index"))
    divisions = [row[0] for row in db.session.query(Student.division).distinct().order_by(Student.division).all()]
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template("announcements.html", announcements=announcements, divisions=divisions)


@announcements_bp.post("/<int:announcement_id>/delete")
@staff_required
def delete(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    is_admin = session.get("role") == "admin"
    is_author = announcement.author_id == session.get("user_id")
    if not is_admin and not is_author:
        flash("You can delete only announcements you published.", "error")
        return redirect(url_for("announcements.index"))
    db.session.delete(announcement)
    db.session.commit()
    flash("Announcement deleted.", "success")
    return redirect(url_for("announcements.index"))


def request_user_id():
    from flask import session
    return session.get("user_id")
