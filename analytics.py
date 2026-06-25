# analytics.py
# Generate analytics summary (overall counts + dept+semester breakdowns)
# Produces JSON in static/analytics/summary.json and optional PNG charts in static/analytics/
#
# Usage:
#   python analytics.py
#   python analytics.py --no-plot
#   python analytics.py --out ./static/analytics

import os
import sqlite3
import json
import argparse
from datetime import datetime

# plotting (optional)
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except Exception:
    plt = None

DEFAULT_DB = 'users.db'
DEFAULT_OUT = os.path.join('static', 'analytics')


def ensure_dir(d):
    os.makedirs(d, exist_ok=True)


def query_one(conn, q, params=()):
    cur = conn.cursor()
    try:
        cur.execute(q, params)
        row = cur.fetchone()
        return row[0] if row is not None else 0
    except Exception:
        return 0


def fetchall_dict(conn, q, params=()):
    cur = conn.cursor()
    cur.execute(q, params)
    cols = [c[0] for c in cur.description] if cur.description else []
    rows = []
    for r in cur.fetchall():
        rows.append(dict(zip(cols, r)))
    return rows


def generate_summary(db_path=DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # overall counts
    counts = {
        'users': query_one(conn, "SELECT COUNT(*) FROM users WHERE username != 'admin'"),
        'admin_exists': bool(query_one(conn, "SELECT COUNT(*) FROM users WHERE username = 'admin'")),
        'books': query_one(conn, "SELECT COUNT(*) FROM library"),
        'subjects': query_one(conn, "SELECT COUNT(*) FROM subjects"),
        'courses': query_one(conn, "SELECT COUNT(*) FROM courses"),
        'feedbacks': query_one(conn, "SELECT COUNT(*) FROM feedback"),
        'messages': query_one(conn, "SELECT COUNT(*) FROM contact_messages"),
    }

    # subjects by department & semester
    subj_by_dept_sem = []
    try:
        subj_by_dept_sem = fetchall_dict(conn,
            """
            SELECT department, semester, COUNT(*) as count
            FROM subjects
            GROUP BY department, semester
            ORDER BY department, CAST(semester AS INTEGER)
            """
        )
    except Exception:
        subj_by_dept_sem = []

    # feedbacks by department & semester (from feedback table)
    fb_by_dept_sem = []
    try:
        fb_by_dept_sem = fetchall_dict(conn,
            """
            SELECT department, semester, COUNT(*) as count
            FROM feedback
            GROUP BY department, semester
            ORDER BY department, CAST(semester AS INTEGER)
            """
        )
    except Exception:
        fb_by_dept_sem = []

    # users by department
    users_by_dept = []
    try:
        users_by_dept = fetchall_dict(conn,
            """
            SELECT department, COUNT(*) as count
            FROM users
            GROUP BY department
            ORDER BY department
            """
        )
    except Exception:
        users_by_dept = []

    # Attempt join: feedbacks linked to users (only when feedback.name == users.username)
    feedbacks_joined_users = []
    try:
        feedbacks_joined_users = fetchall_dict(conn,
            """
            SELECT u.department as user_department, f.semester as semester, COUNT(*) as count
            FROM feedback f
            JOIN users u ON f.name = u.username
            GROUP BY u.department, f.semester
            ORDER BY u.department, CAST(f.semester AS INTEGER)
            """
        )
    except Exception:
        feedbacks_joined_users = []

    summary = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'counts': counts,
        'subjects_by_dept_sem': subj_by_dept_sem,
        'feedbacks_by_dept_sem': fb_by_dept_sem,
        'users_by_dept': users_by_dept,
        'feedbacks_joined_users_by_dept_sem': feedbacks_joined_users
    }

    conn.close()
    return summary


def save_json(summary, out_dir):
    ensure_dir(out_dir)
    path = os.path.join(out_dir, 'summary.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    return path


def plot_breakdowns(summary, out_dir):
    """
    Create simple PNG charts for some breakdowns (requires matplotlib).
    Returns dict with created file paths.
    """
    if plt is None:
        print("matplotlib not available — skipping plots.")
        return {}

    ensure_dir(out_dir)
    plots = {}

    # Users by department
    users = summary.get('users_by_dept', [])
    if users:
        labels = [u.get('department') or 'Unknown' for u in users]
        vals = [u.get('count', 0) for u in users]
        fig, ax = plt.subplots(figsize=(8, 4))
        bars = ax.bar(labels, vals)
        ax.set_title('Users by Department')
        ax.set_ylabel('Count')
        for rect in bars:
            h = rect.get_height()
            ax.annotate(str(int(h)), xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 4), textcoords='offset points', ha='center', va='bottom')
        plt.xticks(rotation=20)
        plt.tight_layout()
        p1 = os.path.join(out_dir, 'users_by_dept.png')
        fig.savefig(p1, dpi=120)
        plt.close(fig)
        plots['users_by_dept'] = p1

    # Subjects by Dept+Sem
    subs = summary.get('subjects_by_dept_sem', [])
    if subs:
        labels = [f"{r.get('department') or 'Unknown'} - Sem{r.get('semester')}" for r in subs]
        vals = [r.get('count', 0) for r in subs]
        fig, ax = plt.subplots(figsize=(10, 4))
        bars = ax.bar(labels, vals)
        ax.set_title('Subjects by Dept & Semester')
        ax.set_ylabel('Count')
        for rect in bars:
            h = rect.get_height()
            ax.annotate(str(int(h)), xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 4), textcoords='offset points', ha='center', va='bottom', fontsize=8)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        p2 = os.path.join(out_dir, 'subjects_by_dept_sem.png')
        fig.savefig(p2, dpi=120)
        plt.close(fig)
        plots['subjects_by_dept_sem'] = p2

    # Feedbacks joined to users by dept+sem
    fj = summary.get('feedbacks_joined_users_by_dept_sem', [])
    if fj:
        labels = [f"{r.get('user_department') or 'Unknown'} - Sem{r.get('semester')}" for r in fj]
        vals = [r.get('count', 0) for r in fj]
        fig, ax = plt.subplots(figsize=(10, 4))
        bars = ax.bar(labels, vals)
        ax.set_title('Feedbacks (joined to users) by Dept & Sem')
        ax.set_ylabel('Count')
        for rect in bars:
            h = rect.get_height()
            ax.annotate(str(int(h)), xy=(rect.get_x() + rect.get_width() / 2, h),
                        xytext=(0, 4), textcoords='offset points', ha='center', va='bottom', fontsize=8)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        p3 = os.path.join(out_dir, 'feedbacks_joined_users_by_dept_sem.png')
        fig.savefig(p3, dpi=120)
        plt.close(fig)
        plots['feedbacks_joined_users_by_dept_sem'] = p3

    return plots


def generate(db=DEFAULT_DB, out_dir=DEFAULT_OUT, do_plot=True):
    summary = generate_summary(db)
    json_path = save_json(summary, out_dir)
    plots = {}
    if do_plot:
        plots = plot_breakdowns(summary, out_dir)
    return {'summary': summary, 'json': json_path, 'plots': plots}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=DEFAULT_DB)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--no-plot', action='store_true')
    args = ap.parse_args()
    res = generate(db=args.db, out_dir=args.out, do_plot=not args.no_plot)
    print("Analytics generated.")
    print("JSON:", res['json'])
    print("Plots:", res['plots'])


if __name__ == '__main__':
    main()
