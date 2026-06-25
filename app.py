# app.py
# Complete, ready-to-run Flask app for Edunexus (public /library route ensured)

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, jsonify
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename

# ---------------- CONFIG ----------------
app = Flask(__name__)
app.secret_key = 'secretkey123'  # change for production

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOOKS = os.path.join(BASE_DIR, 'static', 'books')
UPLOAD_NOTES = os.path.join(BASE_DIR, 'static', 'notes')
UPLOAD_LIBRARY = os.path.join(BASE_DIR, 'static', 'library')
ANALYTICS_DIR = os.path.join(BASE_DIR, 'static', 'analytics')

for d in (UPLOAD_BOOKS, UPLOAD_NOTES, UPLOAD_LIBRARY, ANALYTICS_DIR):
    os.makedirs(d, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, 'users.db')

# ---------------- DB INIT ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        department TEXT NOT NULL,
        last_login TEXT,
        registered_on TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        department TEXT,
        semester TEXT,
        subject_name TEXT,
        subject_code TEXT,
        filename TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS library (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        author TEXT,
        filename TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        department TEXT,
        semester TEXT,
        feedback TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS contact_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        subject TEXT,
        message TEXT,
        timestamp TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
    ''')

    conn.commit()
    conn.close()

init_db()

# ---------------- CONTEXT ----------------
@app.context_processor
def inject_site_info():
    return dict(site_title="Edunexus", current_year=datetime.now().year)


# ---------------- Helpers ----------------
def table_exists(cursor, table_name):
    """Return True if table exists in the connected DB cursor."""
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return cursor.fetchone() is not None
    except Exception:
        return False


def is_admin():
    return ('user' in session) and (session['user'] == 'admin')


# ---------------- ROUTES ----------------
@app.route('/')
def home():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT name, department, semester, feedback FROM feedback ORDER BY id DESC LIMIT 6")
        feedbacks = c.fetchall()
    except Exception:
        feedbacks = []
    conn.close()
    return render_template('index.html', feedbacks=feedbacks)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT username, password FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and user[1] == password:
            session['user'] = user[0]
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE users SET last_login = ? WHERE username = ?", (now, username))
            conn.commit()
            conn.close()
            if username == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        else:
            return render_template('login.html', message="Invalid credentials")
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        department = request.form['department'].strip()
        password = request.form['password']
        registered_on = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO users (username, department, password, registered_on) VALUES (?, ?, ?, ?)",
                      (username, department, password, registered_on))
            conn.commit()
            conn.close()
            flash("Registration successful. You can login now.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error_message="Username already exists.")
        except Exception as e:
            return render_template('register.html', error_message=str(e))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        semester = request.form['semester']
        feedback_text = request.form['feedback']

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO feedback (name, department, semester, feedback) VALUES (?, ?, ?, ?)",
                  (name, department, semester, feedback_text))
        conn.commit()
        conn.close()

        flash("Thank you for your feedback!")
        return redirect(url_for('home'))
    return render_template('feedback.html')


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    success = None
    if request.method == 'POST':
        if request.form.get('botcheck'):
            return redirect(url_for('home'))

        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO contact_messages (name, email, subject, message, timestamp) VALUES (?, ?, ?, ?, ?)",
                  (name, email, subject, message, timestamp))
        conn.commit()
        conn.close()
        success = "Thank you for contacting us! We'll get back to you soon."

    return render_template("contact.html", success=success)


# ---------------- USER DASHBOARD ----------------
@app.route('/user_dashboard', methods=['GET', 'POST'])
def user_dashboard():
    if 'user' not in session or session['user'] == 'admin':
        return redirect(url_for('login'))

    username = session['user']

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT department FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    if not row:
        conn.close()
        return "User not found", 404

    department = row['department']
    selected_semester = None
    subject_code = None
    subjects = []
    notes = []

    if request.method == 'POST':
        selected_semester = request.form.get('semester')
        subject_code = request.form.get('subject_code')

        if selected_semester:
            subjects = c.execute("SELECT subject_name, subject_code FROM subjects WHERE department = ? AND semester = ?",
                                 (department, selected_semester)).fetchall()

        if subject_code:
            notes = c.execute("SELECT subject_name, subject_code, filename FROM subjects WHERE department = ? AND semester = ? AND subject_code = ?",
                              (department, selected_semester, subject_code)).fetchall()

    conn.close()
    return render_template('user_dashboard.html',
                           username=username,
                           department=department,
                           selected_semester=int(selected_semester) if selected_semester else None,
                           subject_code=subject_code,
                           subjects=subjects,
                           notes=notes)


# ---------------- LIBRARY (PUBLIC) ----------------
@app.route('/library')
def library():
    # public route - no login required
    print("DEBUG: /library requested; session user:", session.get('user'))
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT id, title, author, filename FROM library")
        books = c.fetchall()
    except Exception:
        books = []
    conn.close()
    return render_template('library.html', books=books)


# ---------------- ADMIN DASHBOARD (protected) ----------------
@app.route('/admin-dashboard')
def admin_dashboard():
    if not is_admin():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT username, department, last_login, registered_on FROM users WHERE username != 'admin'")
    users = c.fetchall()

    c.execute("SELECT id, title, author, filename FROM library")
    books = c.fetchall()

    c.execute("SELECT id, department, semester, subject_name, subject_code, filename FROM subjects")
    subjects = c.fetchall()

    c.execute("SELECT id, name FROM courses ORDER BY name")
    courses = c.fetchall()

    c.execute("SELECT id, name, department, semester, feedback FROM feedback ORDER BY id DESC")
    feedbacks = c.fetchall()

    c.execute("SELECT id, name, email, subject, message, timestamp FROM contact_messages ORDER BY timestamp DESC")
    messages = c.fetchall()

    conn.close()
    return render_template('admin_dashboard.html',
                           courses=courses,
                           users=users,
                           books=books,
                           subjects=subjects,
                           feedbacks=feedbacks,
                           messages=messages)


# ---------------- ADMIN ACTIONS ----------------
@app.route('/analytics')
def analytics_page():
    # Only admin can view analytics page
    if not is_admin():
        return redirect(url_for('login'))
    # The page itself fetches live JSON from /admin/analytics_json
    return render_template('analytics.html')


@app.route('/add_course', methods=['POST'])
def add_course():
    if not is_admin():
        return redirect(url_for('login'))
    name = request.form.get('course_name', '').strip()
    if name:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT OR IGNORE INTO courses (name) VALUES (?)", (name,))
    return redirect(url_for('admin_dashboard'))


@app.route('/delete_course/<int:course_id>')
def delete_course(course_id):
    if not is_admin():
        return redirect(url_for('login'))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    return redirect(url_for('admin_dashboard'))


@app.route('/add_subject', methods=['POST'])
def add_subject():
    if not is_admin():
        return redirect(url_for('login'))

    dept = request.form.get('department', '').strip()
    sem = request.form.get('semester', '').strip()
    name = request.form.get('subject_name', '').strip()
    code = request.form.get('subject_code', '').strip()
    file = request.files.get('note_file')

    filename = None
    if file and file.filename.lower().endswith('.pdf'):
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_NOTES, filename))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO subjects (department, semester, subject_name, subject_code, filename) VALUES (?, ?, ?, ?, ?)",
              (dept, sem, name, code, filename))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/delete_subject/<int:subject_id>')
def delete_subject(subject_id):
    if not is_admin():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename FROM subjects WHERE id = ?", (subject_id,))
    file = c.fetchone()
    if file and file[0]:
        file_path = os.path.join(UPLOAD_NOTES, file[0])
        if os.path.exists(file_path):
            os.remove(file_path)
    c.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/add_book', methods=['POST'])
def add_book():
    if not is_admin():
        return redirect(url_for('login'))

    title = request.form.get('title', '').strip()
    author = request.form.get('author', '').strip()
    book_file = request.files.get('book_file')

    filename = None
    if book_file and book_file.filename.lower().endswith('.pdf'):
        filename = secure_filename(book_file.filename)
        save_path = os.path.join(UPLOAD_BOOKS, filename)
        book_file.save(save_path)

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO library (title, author, filename) VALUES (?, ?, ?)", (title, author, filename))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/delete_book/<int:book_id>')
def delete_book(book_id):
    if not is_admin():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename FROM library WHERE id = ?", (book_id,))
    book = c.fetchone()
    if book and book[0]:
        file_path = os.path.join(UPLOAD_BOOKS, book[0])
        if os.path.exists(file_path):
            os.remove(file_path)
    c.execute("DELETE FROM library WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/delete_feedback/<int:feedback_id>')
def delete_feedback(feedback_id):
    if not is_admin():
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/delete_message/<int:message_id>')
def delete_message(message_id):
    if not is_admin():
        return redirect(url_for('login'))

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM contact_messages WHERE id = ?", (message_id,))
        conn.commit()
    return redirect(url_for('admin_dashboard'))


@app.route('/download_book/<path:filename>')
def download_book(filename):
    return send_from_directory(UPLOAD_BOOKS, filename, as_attachment=True)


@app.route('/download_note/<path:filename>')
def download_note(filename):
    return send_from_directory(UPLOAD_NOTES, filename, as_attachment=True)


# ---------------- Analytics endpoints ----------------
@app.route('/admin/analytics_json')
def admin_analytics_json():
    """Return real-time analytics JSON. Admin-only."""
    if not is_admin():
        return jsonify({'error': 'unauthorized'}), 401

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    counts = {}
    counts['users'] = c.execute("SELECT COUNT(*) FROM users WHERE username != 'admin'").fetchone()[0] if table_exists(c, 'users') else 0
    counts['books'] = c.execute("SELECT COUNT(*) FROM library").fetchone()[0] if table_exists(c, 'library') else 0
    counts['subjects'] = c.execute("SELECT COUNT(*) FROM subjects").fetchone()[0] if table_exists(c, 'subjects') else 0
    counts['courses'] = c.execute("SELECT COUNT(*) FROM courses").fetchone()[0] if table_exists(c, 'courses') else 0
    counts['feedbacks'] = c.execute("SELECT COUNT(*) FROM feedback").fetchone()[0] if table_exists(c, 'feedback') else 0
    counts['messages'] = c.execute("SELECT COUNT(*) FROM contact_messages").fetchone()[0] if table_exists(c, 'contact_messages') else 0
    counts['generated_at'] = datetime.utcnow().isoformat() + 'Z'

    subj_list = []
    if table_exists(c, 'subjects'):
        subj_rows = c.execute("""
            SELECT department, semester, COUNT(*) as cnt
            FROM subjects
            GROUP BY department, semester
            ORDER BY department, CAST(semester AS INTEGER)
        """).fetchall()
        subj_list = [dict(r) for r in subj_rows]

    fb_list = []
    if table_exists(c, 'feedback'):
        fb_rows = c.execute("""
            SELECT department, semester, COUNT(*) as cnt
            FROM feedback
            GROUP BY department, semester
            ORDER BY department, CAST(semester AS INTEGER)
        """).fetchall()
        fb_list = [dict(r) for r in fb_rows]

    users_by_dept = []
    if table_exists(c, 'users'):
        u_rows = c.execute("""
            SELECT department, COUNT(*) as cnt
            FROM users
            GROUP BY department
            ORDER BY department
        """).fetchall()
        users_by_dept = [dict(r) for r in u_rows]

    conn.close()
    return jsonify({
        'counts': counts,
        'subjects_by_dept_sem': subj_list,
        'feedbacks_by_dept_sem': fb_list,
        'users_by_dept': users_by_dept
    })


@app.route('/admin/regenerate_analytics', methods=['POST'])
def admin_regenerate_analytics():
    if not is_admin():
        return jsonify({'error': 'unauthorized'}), 401

    try:
        from analytics import generate as analytics_generate
    except Exception as e:
        return jsonify({'error': 'analytics import failed', 'details': str(e)}), 500

    try:
        res = analytics_generate(db=DB_PATH, out_dir=ANALYTICS_DIR, do_plot=True)
        return jsonify({'status': 'ok', 'json': res.get('json'), 'plots': res.get('plots')})
    except Exception as e:
        return jsonify({'error': 'generate failed', 'details': str(e)}), 500


# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
