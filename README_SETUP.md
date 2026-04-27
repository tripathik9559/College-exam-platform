# BBDNIIT Online Exam Platform — Setup Guide

## Requirements
- Python 3.10 or higher
- pip
- Git (optional)

---

## Step 1 — Unzip and enter the project

```bash
unzip project-1-with-face-snapshots.zip
cd bbdniit_final
```

---

## Step 2 — Create a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac / Linux
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal prompt.

---

## Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

This installs Django, Pillow, and all other required packages.

---

## Step 4 — Set up the database

```bash
python manage.py migrate
```

This creates all tables including the new `StudentFaceSnapshot` table.

---

## Step 5 — Create a superuser (admin)

```bash
python manage.py createsuperuser
```

Enter a username, email, and password when prompted.

---

## Step 6 — Run the development server

```bash
python manage.py runserver
```

Open your browser at: **http://127.0.0.1:8000**

---

## Step 7 — First-time setup in the app

1. Go to **http://127.0.0.1:8000/admin** and log in with your superuser account.
2. Register as a **Teacher** at `/teacherclick` → approve yourself in admin under `Teacher` → set `status = True`.
3. Register as a **Student** at `/studentclick`.

---

## What's new in this version

### Student side
| Feature | Where |
|---|---|
| **Identity Verification** | Auto-shown after every login (face capture) |
| **Exam Schedule** | Sidebar → 🗓️ Exam Schedule (live countdown timers) |
| **Result Analysis** | Sidebar → 📊 Result Analysis (subject chart + attempt comparison) |
| **Gaze tracking** | Auto-alerts during exam if student looks away |
| **Fullscreen enforcement** | Exam auto-submits if fullscreen is exited |
| **Periodic snapshot** | Camera captures photo every 60 seconds during exam |

### Teacher side
| Feature | Where |
|---|---|
| **Live Monitoring** | Sidebar → 🟢 Live Monitoring (names of active exam takers, refreshes every 15s) |
| **Face Snapshots** | Sidebar → 📸 Face Snapshots (login photo vs exam photos per student) |
| **Per-student gallery** | Click any student in Face Snapshots to see full photo history |

---

## Media files (uploaded images)

Images are stored in the `media/` folder. In development this is served automatically.

For production (Railway, etc.), set `MEDIA_ROOT` and configure your storage backend accordingly.

---

## Environment variables (optional for production)

Create a `.env` file in the `bbdniit_final` folder:

```
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

---

## Common errors

| Error | Fix |
|---|---|
| `No module named 'PIL'` | Run `pip install Pillow` |
| `django.db.utils.OperationalError` | Run `python manage.py migrate` again |
| Camera not working | Use HTTPS or `localhost` (browsers block camera on plain HTTP) |
| `TemplateDoesNotExist` | Make sure you're running from inside `bbdniit_final/` folder |
