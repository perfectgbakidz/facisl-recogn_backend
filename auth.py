from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db
import jwt
import datetime
from functools import wraps
import os

auth_bp = Blueprint("auth", __name__)

# -------------------------------
# JWT Config
# -------------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")  # ⚠️ use env var in prod
JWT_ALGO = "HS256"
JWT_EXP_HOURS = 6


def create_token(user_id, role):
    """Generate JWT for a user"""
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXP_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_token(token):
    """Decode JWT token and handle errors"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        return {"error": "Token expired"}
    except jwt.InvalidTokenError:
        return {"error": "Invalid token"}


def token_required(func):
    """Decorator to protect endpoints with JWT"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Token required"}), 401

        token = auth_header.split(" ")[1]
        decoded = decode_token(token)

        if isinstance(decoded, dict) and "error" in decoded:
            return jsonify(decoded), 401  # return specific error

        g.user = decoded  # attach decoded payload to g (Flask request context)
        return func(*args, **kwargs)
    return wrapper

# -------------------------------
# Lecturer Registration
# -------------------------------
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    registration_code = data.get("registration_code")

    if registration_code != "masterkey":
        return jsonify({"error": "Invalid registration code"}), 403

    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO lecturers (username, password, role) VALUES (?, ?, ?)",
            (username, generate_password_hash(password), "lecturer")
        )
        conn.commit()
        return jsonify({"message": "Lecturer registered successfully"})
    except Exception as e:
        return jsonify({"error": "Username already exists"}), 400
    finally:
        conn.close()


# -------------------------------
# Lecturer Login
# -------------------------------
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, password, role FROM lecturers WHERE username=?", (username,))
    lecturer = cursor.fetchone()
    conn.close()

    if lecturer and check_password_hash(lecturer[1], password):
        token = create_token(lecturer[0], lecturer[2])
        return jsonify({
            "message": "Login successful",
            "role": lecturer[2],
            "token": token,
            "expires_in": JWT_EXP_HOURS * 3600  # in seconds
        })
    return jsonify({"error": "Invalid credentials"}), 401
