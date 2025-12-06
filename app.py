from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sqlite3
from datetime import datetime
import json
import secrets
from admin_routes import admin_bp
from student_routes import student_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', secrets.token_hex(32))
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
CORS(app)

app.register_blueprint(admin_bp)
app.register_blueprint(student_bp)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def get_db():
    conn = sqlite3.connect('exam_system.db')
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return generate_password_hash(password)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        admin = conn.execute('SELECT * FROM users WHERE username = ? AND role = "admin"', 
                           (username,)).fetchone()
        conn.close()
        
        if admin and check_password_hash(admin['password'], password):
            session['user_id'] = admin['id']
            session['username'] = admin['username']
            session['role'] = 'admin'
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('admin_login.html')

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db()
        student = conn.execute('SELECT * FROM users WHERE username = ? AND role = "student"', 
                             (username,)).fetchone()
        conn.close()
        
        if student and check_password_hash(student['password'], password):
            session['user_id'] = student['id']
            session['username'] = student['username']
            session['role'] = 'student'
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid credentials', 'error')
    
    return render_template('student_login.html')

@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        
        conn = get_db()
        existing = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if existing:
            flash('Username already exists', 'error')
        else:
            conn.execute('INSERT INTO users (username, password, email, full_name, role) VALUES (?, ?, ?, ?, ?)',
                        (username, hash_password(password), email, full_name, 'student'))
            conn.commit()
            conn.close()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('student_login'))
        
        conn.close()
    
    return render_template('student_register.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    exams = conn.execute('SELECT * FROM exams ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return render_template('admin_dashboard.html', exams=exams)

@app.route('/student/dashboard')
def student_dashboard():
    if session.get('role') != 'student':
        return redirect(url_for('student_login'))

    conn = get_db()

    exams = conn.execute('SELECT * FROM exams WHERE is_active = 1').fetchall()
    available_exams = []

    for exam in exams or []:
        attempt = conn.execute(
            'SELECT * FROM student_attempts WHERE student_id = ? AND exam_id = ?',
            (session['user_id'], exam['id'])
        ).fetchone()
        if not attempt:
            available_exams.append(exam)

    completed = conn.execute('''
        SELECT e.title, sa.score, sa.submitted_at 
        FROM student_attempts sa 
        JOIN exams e ON sa.exam_id = e.id 
        WHERE sa.student_id = ?
        ORDER BY sa.submitted_at DESC
    ''', (session['user_id'],)).fetchall() or []

    conn.close()

    if available_exams is None:
        available_exams = []
    if completed is None:
        completed = []

    return render_template(
        'student_dashboard.html',
        available_exams=available_exams,
        completed=completed
    )

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%H:%M:%S'):
    """Convert string timestamp to formatted time."""
    if not value:
        return '-'
    try:
        if isinstance(value, datetime):
            dt = value
        elif 'T' in value:
            dt = datetime.fromisoformat(value)
        else:
            dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        return dt.strftime(format)
    except Exception:
        return value
    
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
