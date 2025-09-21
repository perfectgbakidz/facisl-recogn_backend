from flask import Flask
from flask_cors import CORS
from db import init_db
from auth import auth_bp
from courses import courses_bp
from students import students_bp
from attendance import attendance_bp
from hod import hod_bp


app = Flask(__name__)
app.secret_key = "supersecretkey"

# CORS setup
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173", "http://127.0.0.1:3000","https://facialrecognition-theta.vercel.app"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Initialize DB
init_db()

# Register blueprints
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(hod_bp, url_prefix="/hod")
app.register_blueprint(courses_bp, url_prefix="/courses")
app.register_blueprint(students_bp, url_prefix="/students")
app.register_blueprint(attendance_bp, url_prefix="/attendance")

if __name__ == "__main__":
    app.run(debug=True)
