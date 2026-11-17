from datetime import datetime

from database.db import db


class Subject(db.Model):
    __tablename__ = "subjects"
    __table_args__ = (db.UniqueConstraint("division", "name", name="uq_subject_division_name"),)

    id = db.Column(db.Integer, primary_key=True)
    division = db.Column(db.String(30), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
