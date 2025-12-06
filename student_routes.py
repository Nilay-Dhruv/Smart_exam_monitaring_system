from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import json
import random
from datetime import datetime

student_bp = Blueprint('student', __name__, url_prefix='/student')

def get_db():
    conn = sqlite3.connect('exam_system.db')
    conn.row_factory = sqlite3.Row
    return conn

@student_bp.route('/start-exam/<int:exam_id>')
def start_exam(exam_id):
    if session.get('role') != 'student':
        return redirect(url_for('student_login'))
    
    conn = get_db()
    
    existing_attempt = conn.execute('SELECT * FROM student_attempts WHERE student_id = ? AND exam_id = ?',
                                   (session['user_id'], exam_id)).fetchone()
    
    if existing_attempt:
        conn.close()
        return "You have already attempted this exam", 403
    
    exam = conn.execute('SELECT * FROM exams WHERE id = ?', (exam_id,)).fetchone()
    questions = conn.execute('SELECT * FROM questions WHERE exam_id = ? ORDER BY RANDOM()', (exam_id,)).fetchall()
    
    if not questions:
        conn.close()
        return "No questions available for this exam", 400
    
    cursor = conn.execute('INSERT INTO student_attempts (student_id, exam_id, total_marks, status) VALUES (?, ?, ?, ?)',
                         (session['user_id'], exam_id, len(questions), 'in_progress'))
    attempt_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    session['attempt_id'] = attempt_id
    session['exam_id'] = exam_id
    
    return render_template('student/exam_interface.html', exam=exam, questions=questions, attempt_id=attempt_id)

@student_bp.route('/submit-answer', methods=['POST'])
def submit_answer():
    if session.get('role') != 'student':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    question_id = data.get('question_id')
    answer = data.get('answer')
    attempt_id = session.get('attempt_id')
    
    conn = get_db()
    attempt = conn.execute('SELECT answers FROM student_attempts WHERE id = ?', (attempt_id,)).fetchone()
    
    answers = json.loads(attempt['answers']) if attempt['answers'] else {}
    answers[str(question_id)] = answer
    
    conn.execute('UPDATE student_attempts SET answers = ? WHERE id = ?',
                (json.dumps(answers), attempt_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@student_bp.route('/log-monitoring', methods=['POST'])
def log_monitoring():
    if session.get('role') != 'student':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    attempt_id = session.get('attempt_id')
    
    conn = get_db()
    conn.execute('''INSERT INTO monitoring_logs 
                   (attempt_id, event_type, face_detected, gaze_direction, head_pose, warning_issued, details)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (attempt_id, data.get('event_type'), data.get('face_detected'),
                 data.get('gaze_direction'), data.get('head_pose'),
                 data.get('warning_issued', 0), data.get('details', '')))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@student_bp.route('/issue-warning', methods=['POST'])
def issue_warning():
    if session.get('role') != 'student':
        return jsonify({'error': 'Unauthorized'}), 403
    
    attempt_id = session.get('attempt_id')
    
    conn = get_db()
    attempt = conn.execute('SELECT warnings_count FROM student_attempts WHERE id = ?', (attempt_id,)).fetchone()
    
    new_count = attempt['warnings_count'] + 1
    
    conn.execute('UPDATE student_attempts SET warnings_count = ? WHERE id = ?',
                (new_count, attempt_id))
    
    conn.execute('''INSERT INTO monitoring_logs 
                   (attempt_id, event_type, warning_issued, details)
                   VALUES (?, ?, ?, ?)''',
                (attempt_id, 'WARNING', 1, f'Warning {new_count} issued'))
    
    conn.commit()
    conn.close()
    
    if new_count >= 3:
        return jsonify({'success': True, 'terminate': True, 'warnings': new_count})
    
    return jsonify({'success': True, 'terminate': False, 'warnings': new_count})

@student_bp.route('/submit-exam', methods=['POST'])
def submit_exam():
    if session.get('role') != 'student':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    attempt_id = session.get('attempt_id')
    reason = data.get('reason', 'manual_submit')
    
    conn = get_db()
    attempt = conn.execute('SELECT * FROM student_attempts WHERE id = ?', (attempt_id,)).fetchone()
    
    answers = json.loads(attempt['answers']) if attempt['answers'] else {}
    questions = conn.execute('SELECT * FROM questions WHERE exam_id = ?', 
                            (attempt['exam_id'],)).fetchall()
    
    score = 0
    for question in questions:
        student_answer = answers.get(str(question['id']))
        if student_answer and student_answer.upper() == question['correct_answer'].upper():
            score += question['marks']
    
    status = 'terminated' if reason == 'violations' else 'completed'
    
    conn.execute('''UPDATE student_attempts 
                   SET score = ?, submitted_at = ?, status = ?, violation_reason = ?
                   WHERE id = ?''',
                (score, datetime.now(), status, reason, attempt_id))
    
    conn.execute('''INSERT INTO monitoring_logs 
                   (attempt_id, event_type, details)
                   VALUES (?, ?, ?)''',
                (attempt_id, 'EXAM_SUBMITTED', f'Reason: {reason}'))
    
    conn.commit()
    conn.close()
    
    session.pop('attempt_id', None)
    session.pop('exam_id', None)
    
    return jsonify({'success': True, 'score': score, 'total': len(questions)})
