from flask import Blueprint, request, jsonify, g
import sqlite3, numpy as np
from datetime import datetime
from auth import token_required

attendance_bp = Blueprint("attendance", __name__)

# -------------------------------
# Load known embeddings
# -------------------------------
EMBEDDINGS_FILE = "models/known_face_embeddings.npy"
NAMES_FILE = "models/known_face_names.npy"

try:
    known_face_embeddings = np.load(EMBEDDINGS_FILE, allow_pickle=True)
    known_face_names = np.load(NAMES_FILE, allow_pickle=True)
except Exception:
    known_face_embeddings = np.array([])
    known_face_names = np.array([])


def find_best_match(embedding, threshold=0.6):
    """
    Find the closest student by comparing embeddings.
    Returns (matric_number, distance) or (None, None) if no match.
    """
    if len(known_face_embeddings) == 0:
        return None, None

    embedding = np.array(embedding)
    distances = np.linalg.norm(known_face_embeddings - embedding, axis=1)
    min_index = np.argmin(distances)
    min_distance = distances[min_index]

    if min_distance <= threshold:
        return known_face_names[min_index], float(min_distance)
    return None, None


# -------------------------------
# Mark Attendance
# -------------------------------
@attendance_bp.route("/mark", methods=["POST"])
@token_required
def mark_attendance():
    data = request.json
    course_id = data.get("course_id")
    embedding = data.get("embedding")

    if not course_id or embedding is None:
        return jsonify({"error": "course_id and embedding required"}), 400

    matric_number, distance = find_best_match(embedding)
    if not matric_number:
        return jsonify({"error": "No matching student found"}), 404

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, first_name, last_name FROM students WHERE matric_number=?", (matric_number,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"error": "Student not found in database"}), 404

    student_id, first_name, last_name = student

    # ✅ Check enrollment
    cursor.execute("SELECT 1 FROM student_courses WHERE student_id=? AND course_id=?", (student_id, course_id))
    enrolled = cursor.fetchone()
    if not enrolled:
        conn.close()
        return jsonify({
            "match": True,
            "matric_number": matric_number,
            "name": f"{first_name} {last_name}",
            "attendance_marked": False,
            "reason": "Student not enrolled in this course"
        })

    # ✅ Prevent duplicates (same day)
    cursor.execute("""SELECT 1 FROM attendance
                      WHERE student_id=? AND course_id=?
                      AND DATE(timestamp)=DATE('now')""",
                   (student_id, course_id))
    if cursor.fetchone():
        conn.close()
        return jsonify({
            "match": True,
            "matric_number": matric_number,
            "name": f"{first_name} {last_name}",
            "attendance_marked": False,
            "reason": "Already marked today"
        })

    cursor.execute(
        "INSERT INTO attendance (student_id, course_id, timestamp) VALUES (?, ?, ?)",
        (student_id, course_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()

    return jsonify({
        "match": True,
        "matric_number": matric_number,
        "name": f"{first_name} {last_name}",
        "attendance_marked": True,
        "course_id": course_id,
        "distance": distance
    })


# -------------------------------
# Course Attendance Tiers (Analytics)
# -------------------------------
@attendance_bp.route("/course_attendance_tiers/<int:course_id>", methods=["GET"])
@token_required
def course_attendance_tiers(course_id):
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    # Count total sessions held for this course
    cursor.execute("SELECT COUNT(DISTINCT DATE(timestamp)) FROM attendance WHERE course_id=?", (course_id,))
    total_sessions = cursor.fetchone()[0]

    if total_sessions == 0:
        conn.close()
        return jsonify({"message": "No attendance records yet"}), 200

    # Get student attendance
    cursor.execute("""
        SELECT s.id, s.first_name, s.last_name, s.matric_number, COUNT(a.id) as attended
        FROM students s
        JOIN student_courses sc ON s.id = sc.student_id
        LEFT JOIN attendance a ON s.id = a.student_id AND a.course_id=sc.course_id
        WHERE sc.course_id=?
        GROUP BY s.id
    """, (course_id,))

    records = cursor.fetchall()
    conn.close()

    attendance_data = []
    for student_id, first_name, last_name, matric_number, attended in records:
        percentage = (attended / total_sessions) * 100
        attendance_data.append({
            "student_id": student_id,
            "name": f"{first_name} {last_name}",
            "matric_number": matric_number,
            "attended_sessions": attended,
            "percentage": percentage
        })

    # Categorize into tiers
    tiers = {
        "25%_or_below": [s for s in attendance_data if s["percentage"] <= 25],
        "50%_or_below": [s for s in attendance_data if 25 < s["percentage"] <= 50],
        "75%_or_below": [s for s in attendance_data if 50 < s["percentage"] <= 75],
        "100%": [s for s in attendance_data if s["percentage"] > 75],
    }

    return jsonify({
        "course_id": course_id,
        "total_sessions": total_sessions,
        "attendance_tiers": tiers
    })


# -------------------------------
# Department-wide Analytics (HOD)
# -------------------------------
@attendance_bp.route("/department_summary", methods=["GET"])
@token_required
def department_summary():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    # Total courses
    cursor.execute("SELECT COUNT(*) FROM courses")
    total_courses = cursor.fetchone()[0]

    # Total students
    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    # Total attendance records
    cursor.execute("SELECT COUNT(*) FROM attendance")
    total_attendance = cursor.fetchone()[0]

    # Course-level stats
    cursor.execute("""
        SELECT c.id, c.name, COUNT(DISTINCT DATE(a.timestamp)) as sessions, COUNT(a.id) as attendance_records
        FROM courses c
        LEFT JOIN attendance a ON c.id = a.course_id
        GROUP BY c.id
    """)
    course_stats = [
        {"course_id": row[0], "course_name": row[1], "sessions": row[2], "attendance_records": row[3]}
        for row in cursor.fetchall()
    ]

    # Student-level stats
    cursor.execute("""
        SELECT s.id, s.first_name, s.last_name, s.matric_number, COUNT(a.id) as total_attended
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id
        GROUP BY s.id
    """)
    student_stats = [
        {"student_id": row[0], "name": f"{row[1]} {row[2]}", "matric_number": row[3], "total_attended": row[4]}
        for row in cursor.fetchall()
    ]

    conn.close()

    return jsonify({
        "summary": {
            "total_courses": total_courses,
            "total_students": total_students,
            "total_attendance_records": total_attendance,
        },
        "course_stats": course_stats,
        "student_stats": student_stats
    })
