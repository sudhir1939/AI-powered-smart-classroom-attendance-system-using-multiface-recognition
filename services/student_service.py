import re

from database.db import db
from models.embedding import FaceEmbedding
from models.student import Student
from models.user import User
from recognition.engine import engine
from services.security_service import encrypt_embedding


def validate_student_form(form):
    values = {key: form.get(key, "").strip() for key in ("student_id", "roll_number", "name", "department", "division", "email")}
    errors = []
    for key, label in (("student_id", "Student ID"), ("roll_number", "Roll number"), ("name", "Name"), ("department", "Department"), ("division", "Division")):
        if not values[key]:
            errors.append(f"{label} is required.")
    if values["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", values["email"]):
        errors.append("Enter a valid email address.")
    return values, errors


def create_student(values, embeddings, account_password):
    student = Student(**values)
    db.session.add(student)
    db.session.flush()
    for vector in embeddings:
        serialized = engine.serialize_embedding(vector)
        db.session.add(FaceEmbedding(student_id=student.id, embedding=encrypt_embedding(serialized), dimension=len(vector), encrypted=True))
    account = User(username=values["student_id"], role="student", student_id=student.id)
    account.set_password(account_password)
    db.session.add(account)
    db.session.commit()
    return student
