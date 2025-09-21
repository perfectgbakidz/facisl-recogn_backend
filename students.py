from flask import Blueprint, request, jsonify
import sqlite3, numpy as np, os

students_bp = Blueprint("students", __name__)

# -------------------------------
# Embeddings storage
# -------------------------------
EMBEDDINGS_FILE = "models/known_face_embeddings.npy"
NAMES_FILE = "models/known_face_names.npy"

if os.path.exists(EMBEDDINGS_FILE) and os.path.exists(NAMES_FILE):
    known_face_embeddings = np.load(EMBEDDINGS_FILE, allow_pickle=True)
    known_face_names = np.load(NAMES_FILE, allow_pickle=True)
else:
    known_face_embeddings = np.array([])
    known_face_names = np.array([])


def save_embeddings():
    np.save(EMBEDDINGS_FILE, known_face_embeddings)
    np.save(NAMES_FILE, known_face_names)


# -------------------------------
# Student Registration (JSON with embedding)
# -------------------------------
@students_bp.route("/register", methods=["POST"])
def register_student():
    global known_face_embeddings, known_face_names

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid JSON or no data provided"}), 400

    # Clean and extract fields
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    matric_number = (data.get("matric_number") or "").strip()
    level = (data.get("level") or "").strip()
    courses_offered = data.get("courses_offered", [])
    embedding = data.get("embedding")

    # Validate required fields
    if not first_name:
        return jsonify({"error": "first_name is required"}), 400
    if not last_name:
        return jsonify({"error": "last_name is required"}), 400
    if not matric_number:
        return jsonify({"error": "matric_number is required"}), 400
    if not level:
        return jsonify({"error": "level is required"}), 400
    if embedding is None:
        return jsonify({"error": "embedding is required"}), 400

    embedding = np.array(embedding, dtype=np.float32)
    if embedding.shape[0] != 128:
        return jsonify({"error": f"embedding must be length 128, got {embedding.shape[0]}"}), 400

    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO students (first_name, last_name, matric_number, level, name)
            VALUES (?, ?, ?, ?, ?)
        """, (first_name, last_name, matric_number, level, f"{first_name} {last_name}"))
        student_id = cursor.lastrowid

        # Assign courses
        for course_name in courses_offered:
            course_name = course_name.strip()
            cursor.execute("SELECT id FROM courses WHERE name=?", (course_name,))
            course = cursor.fetchone()
            if course:
                course_id = course[0]
            else:
                cursor.execute("INSERT INTO courses (name, lecturer_id) VALUES (?, NULL)", (course_name,))
                course_id = cursor.lastrowid
            cursor.execute("INSERT INTO student_courses (student_id, course_id) VALUES (?, ?)", (student_id, course_id))

        conn.commit()

        # Save embedding
        if len(known_face_embeddings) == 0:
            known_face_embeddings = np.array([embedding])
            known_face_names = np.array([matric_number])
        else:
            known_face_embeddings = np.vstack([known_face_embeddings, embedding])
            known_face_names = np.append(known_face_names, matric_number)

        save_embeddings()

        return jsonify({
            "message": f"Student {first_name} {last_name} registered successfully",
            "student_id": student_id
        })

    except sqlite3.IntegrityError:
        return jsonify({"error": "Matric number already exists"}), 400
    finally:
        conn.close()
