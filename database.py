import sqlite3
from werkzeug.security import generate_password_hash

def hash_password(password):
    return generate_password_hash(password)

def init_database():
    conn = sqlite3.connect('exam_system.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        full_name TEXT,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS exams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        duration_minutes INTEGER NOT NULL,
        passing_score REAL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exam_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        option_a TEXT,
        option_b TEXT,
        option_c TEXT,
        option_d TEXT,
        correct_answer TEXT NOT NULL,
        marks INTEGER DEFAULT 1,
        FOREIGN KEY (exam_id) REFERENCES exams(id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS student_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        exam_id INTEGER NOT NULL,
        score REAL,
        total_marks INTEGER,
        answers TEXT,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        submitted_at TIMESTAMP,
        status TEXT DEFAULT 'in_progress',
        warnings_count INTEGER DEFAULT 0,
        violation_reason TEXT,
        FOREIGN KEY (student_id) REFERENCES users(id),
        FOREIGN KEY (exam_id) REFERENCES exams(id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS monitoring_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        event_type TEXT NOT NULL,
        face_detected INTEGER,
        gaze_direction TEXT,
        head_pose TEXT,
        warning_issued INTEGER DEFAULT 0,
        details TEXT,
        FOREIGN KEY (attempt_id) REFERENCES student_attempts(id)
    )
    ''')

    existing_admin = cursor.execute('SELECT * FROM users WHERE username = "admin"').fetchone()
    if not existing_admin:
        cursor.execute(
            'INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)',
            ('admin', hash_password('admin123'), 'System Administrator', 'admin')
        )

    # existing_student = cursor.execute('SELECT * FROM users WHERE username = "student1"').fetchone()
    # if not existing_student:
        # cursor.execute(
            # 'INSERT INTO users (username, password, email, full_name, role) VALUES (?, ?, ?, ?, ?)',
            # ('student1', hash_password('student123'), 'student1@test.com', 'Test Student', 'student')
        # )


    cursor.execute("delete from users where id = '8';")

    # cursor.execute("DELETE FROM exam_reports;")



    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_database()
