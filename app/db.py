import sqlite3
from pathlib import Path
import datetime as dt
import pandas as pd

DB_PATH = Path(__file__).parent / "job_apps.db"
COUNTER_PATH = ".next_id"


# Open connection to DB_PATH
# Turn on foreign keys
# Set a row factory so you access columns by name
# Return connection
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    sql = """
    CREATE TABLE IF NOT EXISTS applications (
        id  INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT    NOT NULL,
        role    TEXT    NOT NULL,
        date_applied    TEXT    NOT NULL,
        status  TEXT    NOT NULL,
        CONSTRAINT  status_allowed  CHECK   (status IN (
            'Applied', 'OA', 'Interview', 'Offer', 'Rejected'
            ))
    );
        """
    
    with get_connection() as conn:
        conn.execute(sql)

    sql_applications_date = """
    CREATE INDEX IF NOT EXISTS idx_applications_status_date ON applications(status, date_applied);
    """

    with get_connection() as conn:
        conn.execute(sql_applications_date)

    sql_company = """
    CREATE INDEX IF NOT EXISTS idx_applications_company ON applications(company)"""

    with get_connection() as conn:
        conn.execute(sql_company)

    print("Database initialized")

    return

def seed_sample_row():
    row_count = """
    SELECT COUNT(*) FROM applications;
    """

    with get_connection() as conn:
        row = conn.execute(row_count).fetchone()
    
    if row[0] > 0:
        return None
    elif row[0] == 0:
        company = "Yash Inc."
        role = "Data Scientist"
        date_applied =dt.date.today().isoformat()
        status = "Applied"

        sql = """
        INSERT INTO applications
        (company, role, date_applied, status)
        VALUES (?, ?, ?, ?)
        """

        with get_connection() as conn:
            cur = conn.execute(sql, (company, role, date_applied, status))
            row_id = cur.lastrowid

        return(row_id)
    
def init_id_counter_if_missing(df):
    """
    Initialize .next_id to max(app_id)+1 (or 1 if empty) if .next_id is empty
    Call once on app startup after loading dataframe
    """
    import os
    if os.path.exists(COUNTER_PATH):
        return
    
    next_id = (int(df["app_id"].max()) + 1) if ("app_id" in df and len(df)) else 1
    with open(COUNTER_PATH, "w") as f:
        f.write(str(next_id))


def get_next_id():
    """Read current next id (int) from .next_id (assuming it exists)"""
    with open(COUNTER_PATH) as f:
        return int(f.read().strip())
    
def bump_next_id():
    """Increment counter by 1 and continue"""
    next_id = get_next_id() + 1
    with open(COUNTER_PATH, "w") as f:
        f.write(str(next_id))

    return next_id
    
def add_application(company: str, role: str, date_applied: dt.date|str, status: str):
    company_input = company
    role_input = role
    date_applied_input = date_applied
    status_input = status

    if company != None and  role != None and date_applied != None and status in {"Applied", "OA", "Interview", "Offer", "Rejected"}:
        sql = """
            INSERT INTO applications
            (company, role, date_applied, status)
            VALUES (?, ?, ?, ?)
            """

        with get_connection() as conn:
            cur = conn.execute(sql, (company_input, role_input, date_applied_input, status_input))
            row_id = cur.lastrowid

    return row_id


def update_status(app_id: int, new_status: str):
    sql = """
        UPDATE applications
        SET status = ?
        WHERE id = ?
        """
    
    with get_connection() as conn:
        conn.execute(sql, (new_status, app_id))
    
    return


def delete_application(app_id: int):
    sql = """
        DELETE FROM applications
        WHERE id = ?
        """
    
    with get_connection() as conn:
        conn.execute(sql, (app_id,))

    return

def delete_all_apps():
    sql = """
        DELETE FROM applications;
        """
    
    with get_connection() as conn:
        conn.execute(sql)

    return

def list_applications_df(limit=100, status=None, date_start=None, date_end=None, company_substr=None, role_substr=None):
    sql = """
        SELECT id, company, role, date_applied, status
        FROM applications
        """
    clauses = []
    params = []

    if status:
        clauses.append("status = ?"); params.append(status)

    if date_start:
        clauses.append("date_applied >= ?"); params.append(date_start)
    
    if date_end:
        clauses.append("date_applied <= ?"); params.append(date_end)

    if company_substr:
        clauses.append("LOWER(company) LIKE LOWER(?)"); params.append(f"%{company_substr}%")

    if role_substr:
        clauses.append("LOWER(role) LIKE LOWER(?)"); params.append(f"%{role_substr}%")
    
    if clauses:
        sql = f"{sql} WHERE " + " AND ".join(clauses)
    else:
        sql = sql

    sql += " ORDER BY id ASC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    df.index += 1


    return df

    




