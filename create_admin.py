from app import create_app
from database.db import db
from models.user import User

app = create_app()

with app.app_context():
    username = input("Enter admin username: ").strip()
    import getpass
    password = getpass.getpass("Enter admin password: ")

    if not username or len(password) < 8:
        raise SystemExit("Username is required and password must contain at least 8 characters.")

    if User.query.filter_by(username=username).first():
        print(f"User '{username}' already exists.")
    else:
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Admin user '{username}' created successfully.")