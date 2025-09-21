import sqlite3
from werkzeug.security import generate_password_hash

def get_db():
    return sqlite3.connect("attendance.db")

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            matric_number TEXT UNIQUE NOT NULL,
            level TEXT NOT NULL,
            name TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lecturers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'lecturer'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            lecturer_id INTEGER NULL,
            FOREIGN KEY(lecturer_id) REFERENCES lecturers(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(course_id) REFERENCES courses(id),
            UNIQUE(student_id, course_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
    """)

    # Default HOD
    hod_pass = generate_password_hash("Admin123")
    cursor.execute("""
        INSERT OR IGNORE INTO lecturers (username, password, role)
        VALUES (?, ?, ?)
    """, ("departmentHOD@mapoly.com", hod_pass, "hod"))

    conn.commit()
    conn.close()
