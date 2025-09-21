from flask import Blueprint, request, jsonify, g
from db import get_db
from auth import token_required

courses_bp = Blueprint("courses", __name__)


@courses_bp.route("/create", methods=["POST"])
@token_required
def create_course():
    data = request.json or {}
    name = data.get("name")

    if not name:
        return jsonify({"error": "Course name is required"}), 400

    # ✅ Get lecturer_id + role from decoded JWT
    lecturer_id = g.user.get("user_id")
    role = g.user.get("role")

    if role != "lecturer":
        return jsonify({"error": "Only lecturers can create courses"}), 403

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, lecturer_id FROM courses WHERE name=?", (name,))
    course = cursor.fetchone()

    if course:
        course_id, existing_lecturer_id = course
        if existing_lecturer_id is None:
            cursor.execute(
                "UPDATE courses SET lecturer_id=? WHERE id=?",
                (lecturer_id, course_id),
            )
            conn.commit()
            conn.close()
            return jsonify({
                "message": f"Course '{name}' assigned to you",
                "course_id": course_id,
                "name": name
            })
        else:
            conn.close()
            return jsonify({"error": "Course already assigned"}), 403
    else:
        cursor.execute(
            "INSERT INTO courses (name, lecturer_id) VALUES (?, ?)",
            (name, lecturer_id),
        )
        conn.commit()
        course_id = cursor.lastrowid
        conn.close()
        return jsonify({
            "message": f"Course '{name}' created successfully",
            "course_id": course_id,
            "name": name
        })


@courses_bp.route("/my", methods=["GET"])
@token_required
def get_my_courses():
    lecturer_id = g.user.get("user_id")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM courses WHERE lecturer_id=?", (lecturer_id,))
    courses = [{"course_id": row[0], "name": row[1]} for row in cursor.fetchall()]
    conn.close()

    return jsonify({"courses": courses})