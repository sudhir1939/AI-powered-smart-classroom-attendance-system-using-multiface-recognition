# FaceLedger

FaceLedger is a Flask-based multi-face attendance system for academic environments. It supports browser-based face recognition, student and staff portals, division-specific subjects, attendance reports, and privacy/security controls.

## Features

### Attendance

- Live multi-face attendance using browser camera capture.
- Upload-photo attendance using the same recognition and duplicate-safe marking flow.
- Attendance is marked immediately after a valid recognized face is detected.
- Duplicate check-in prevention through a student/session uniqueness constraint.
- Manual attendance correction with reason, timestamp, and audit history.
- Multiple classroom/session records with session start and finish controls.
- Session deletion with cascading attendance cleanup and audit logging.
- Low-attendance alerts for students.

### Face recognition

- InsightFace `buffalo_l` support with a clearly labeled OpenCV fallback.
- Multiple student registration samples and embedding matching.
- Face-quality scoring with guidance for weak lighting, pose, or image quality.
- Camera selection on supported browsers.
- Student face re-enrollment from the student profile.
- Recognition confidence and liveness information in the attendance interface.
- Encrypted storage for newly saved face embeddings.

### Dashboards and reports

- Student attendance dashboard and check-in history.
- Daily, subject-wise, and division-wise attendance summaries.
- CSV and Excel report exports.
- PDF report export.
- Printable attendance records through the reports interface.
- Admin audit and privacy management page.

### User management

- Admin, teacher, and student roles.
- Admin-managed teacher accounts.
- Student self-service profile editing.
- Student face replacement/re-enrollment.
- Password reset through email when SMTP is configured.
- Division-specific announcements.

### Subject catalog

- Admin-managed subjects assigned to divisions.
- Subject dropdown loads after a division is selected.
- Server-side validation prevents invalid division/subject combinations.

### Security and privacy

- Role-protected routes and session handling.
- Login rate limiting.
- Security response headers.
- Detailed audit logging for important actions.
- Biometric retention cleanup controls.
- SQLite backup support.
- Consent and face-data deletion workflows.
- Configurable recognition thresholds.

## Windows setup

Python 3.11 is recommended for the full InsightFace workflow. Python 3.12 or 3.13 may work when the required packages are available.

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python create_admin.py
python app.py
```

Open `http://127.0.0.1:5000` and sign in with the administrator created by `create_admin.py`.

### Python 3.11 and InsightFace

On Windows, use the Python 3.11 dependency file for the most reliable InsightFace installation. Microsoft C++ Build Tools with the **Desktop development with C++** workload may be required.

```powershell
& "C:\Users\sudhi\AppData\Local\Programs\Python\Python311\python.exe" -m venv venv311
.\venv311\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-python311.txt
python -c "from insightface.app import FaceAnalysis; print('InsightFace package ready')"
python app.py
```

The first use of `FaceAnalysis(name="buffalo_l")` downloads the model pack and may take several minutes. If InsightFace cannot load, FaceLedger uses its explicitly labeled OpenCV fallback for demonstration purposes. InsightFace is recommended for dependable recognition.

## First-use workflow

1. Create an admin account.
2. Sign in as admin and add subjects under **Subjects** for each division.
3. Create teacher accounts if required.
4. Register students and capture multiple face samples.
5. Have students sign in to add a portal password or update their profile and face.
6. Create a session, select a division, and choose one of that division's subjects.
7. Allow browser camera access or upload a photo.
8. Confirm that recognized students are marked immediately.
9. Finish the session and review or export records from **Reports**.

## Role-based access

- **Admin:** manage teachers, subjects, audit/privacy controls, backups, retention cleanup, and all student records.
- **Teacher:** register students, create sessions, mark attendance, correct records, publish announcements, and view reports.
- **Student:** view personal attendance and announcements, edit permitted profile fields, and replace their own face data.

## Configuration

Recognition thresholds can be configured with:

- `FACE_RECOGNITION_THRESHOLD`
- `FACE_RECOGNITION_MARGIN`
- `FACE_FALLBACK_THRESHOLD`
- `FACE_FALLBACK_MIN_SAMPLES`

Password reset email requires all of the following SMTP settings:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM`

Set `EMBEDDING_ENCRYPTION_KEY` to a stable Fernet-compatible key in production. If it is not set, the application derives the encryption key from the Flask secret key.

## Testing

Run the test suite from the project directory:

```powershell
.\venv311\Scripts\python.exe -m pytest tests -q
```

## Important limitations

Temporal movement and multi-frame consistency are academic anti-spoofing measures, not production-grade liveness detection. Lighting, occlusion, camera quality, pose, and recognition thresholds affect results.

Face embeddings are sensitive biometric data. Use informed consent, HTTPS in production, minimal retention, access controls, secure backups, and an appropriate data-deletion process. The OpenCV fallback is useful for demonstrations but is not equivalent to a modern face-recognition embedding model.
