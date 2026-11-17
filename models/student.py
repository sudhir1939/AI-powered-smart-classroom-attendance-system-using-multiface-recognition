from datetime import datetime

from database.db import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    roll_number = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(120), nullable=False)
    division = db.Column(db.String(30), nullable=False, index=True)
    email = db.Column(db.String(160), nullable=True)
    consent_at = db.Column(db.DateTime, nullable=True)
    consent_version = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    embeddings = db.relationship("FaceEmbedding", back_populates="student", cascade="all, delete-orphan")
    attendance = db.relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    account = db.relationship("User", back_populates="student", uselist=False, foreign_keys="User.student_id")
