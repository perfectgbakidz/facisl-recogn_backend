# hod.py
from flask import Blueprint, jsonify, g
import sqlite3
from auth import token_required

hod_bp = Blueprint("hod", __name__)

# -------------------------------
# Utility to open DB
# -------------------------------
def get_db():
    conn = sqlite3.connect("attendance.db")
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------------
# Dashboard Overview
# -------------------------------
@hod_bp.route("/overview", methods=["GET"])
@token_required
def overview():
    if g.user.get("role") not in ["hod", "admin"]:
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM lecturers WHERE role='lecturer'")
    total_lecturers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM courses")
    total_courses = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM attendance")
    total_attendance = cursor.fetchone()[0]

    # average attendance = attendance records / (students * courses) — simple estimate
    avg_attendance = 0
    if total_students > 0 and total_courses > 0:
        avg_attendance = round(
            (total_attendance / (total_students * total_courses)) * 100, 2
        )

    conn.close()
    return jsonify({
        "total_students": total_students,
        "total_lecturers": total_lecturers,
        "total_courses": total_courses,
        "average_attendance": avg_attendance
    })


# -------------------------------
# Courses with Attendance Summary
# -------------------------------
@hod_bp.route("/courses", methods=["GET"])
@token_required
def courses_summary():
    if g.user.get("role") not in ["hod", "admin"]:
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.id as course_id, c.name, l.username as lecturer,
               COUNT(sc.student_id) as student_count,
               COALESCE(ROUND(
                   (CAST(COUNT(a.id) AS FLOAT) / NULLIF(COUNT(sc.student_id),0)) * 100, 2
               ), 0) as average_attendance
        FROM courses c
        LEFT JOIN lecturers l ON c.lecturer_id = l.id
        LEFT JOIN student_courses sc ON c.id = sc.course_id
        LEFT JOIN attendance a ON c.id = a.course_id
        GROUP BY c.id
    """)
    rows = cursor.fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


# -------------------------------
# Lecturers list + courses
# -------------------------------
@hod_bp.route("/lecturers", methods=["GET"])
@token_required
def lecturers():
    if g.user.get("role") not in ["hod", "admin"]:
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT l.id as lecturer_id, l.username as name,
               GROUP_CONCAT(c.name, ', ') as courses
        FROM lecturers l
        LEFT JOIN courses c ON l.id = c.lecturer_id
        WHERE l.role='lecturer'
        GROUP BY l.id
    """)
    rows = cursor.fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])


# -------------------------------
# Low Attendance Students (<=25%)
# -------------------------------
@hod_bp.route("/low_attendance", methods=["GET"])
@token_required
def low_attendance():
    if g.user.get("role") not in ["hod", "admin"]:
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.id as student_id, s.first_name || ' ' || s.last_name as name,
               s.matric_number,
               COUNT(a.id) as attended_sessions,
               (COUNT(a.id) * 100.0 / NULLIF((SELECT COUNT(*) FROM courses c
                                             JOIN student_courses sc ON sc.course_id=c.id
                                             WHERE sc.student_id=s.id),0)) as percentage
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id
        GROUP BY s.id
        HAVING percentage <= 25
    """)
    rows = cursor.fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])
