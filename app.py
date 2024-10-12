import os
import sys
import json
import hashlib  # Added to resolve "hashlib" is not defined
import requests
import random
import time
import concurrent.futures
from typing import Union  # Added to resolve "Union" is not defined
from urllib import parse  # Added to resolve "parse" is not defined
from datetime import datetime, timedelta
from html.parser import HTMLParser
from flask import Flask, render_template, request, redirect, url_for, flash, session as flask_session, Response, abort

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure secret key for production

session = requests.Session()
t_spfd = 0
progress_data = []  # This will hold the real-time progress data

# Session timeout limit (e.g., 30 minutes)
SESSION_TIMEOUT = timedelta(minutes=30)

class ZyBooksError(Exception):
    pass

# Helper function to check if the user is authenticated
def is_authenticated():
    """Check if the user is authenticated and the session is still valid."""
    return 'auth_token' in flask_session and 'user_id' in flask_session

# Helper function to require login for routes
def login_required(func):
    """Decorator to enforce login on routes."""
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            flash("You need to log in first.", 'danger')
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return wrapper

# Session timeout management
@app.before_request
def check_session_timeout():
    """Check if the session has timed out."""
    if 'last_active' in flask_session:
        now = datetime.now()
        last_active = flask_session['last_active']
        if now - last_active > SESSION_TIMEOUT:
            flask_session.clear()
            flash("Session timed out. Please log in again.", 'danger')
            return redirect(url_for('index'))
    flask_session['last_active'] = datetime.now()  # Update last activity time

# All ZyBooks solver functions below:

def signin(usr: str, pwd: str) -> dict:
    try:
        response = session.post("https://zyserver.zybooks.com/v1/signin", json={"email": usr, "password": pwd})
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            raise ZyBooksError("Failed to sign in")
        return data["session"]
    except requests.RequestException as e:
        raise ZyBooksError(f"Network error during sign-in: {e}")

def get_books(auth: str, usr_id: str) -> list:
    try:
        response = session.get(f"https://zyserver.zybooks.com/v1/user/{usr_id}/items?items=%5B%22zybooks%22%5D&auth_token={auth}")
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            raise ZyBooksError("Failed to retrieve books")
        return [book for book in data["items"]["zybooks"] if not book["autosubscribe"]]
    except requests.RequestException as e:
        raise ZyBooksError(f"Error fetching books: {e}")

def get_chapters(code: str, auth: str) -> list:
    try:
        response = session.get(f"https://zyserver.zybooks.com/v1/zybooks?zybooks=%5B%22{code}%22%5D&auth_token={auth}")
        response.raise_for_status()
        return response.json()["zybooks"][0]["chapters"]
    except requests.RequestException as e:
        raise ZyBooksError(f"Error fetching chapters: {e}")

def get_problems(code: str, chapter: int, section: int, auth: str) -> list:
    try:
        response = session.get(f"https://zyserver.zybooks.com/v1/zybook/{code}/chapter/{chapter}/section/{section}?auth_token={auth}")
        response.raise_for_status()
        return response.json()["section"]["content_resources"]
    except requests.RequestException as e:
        raise ZyBooksError(f"Error fetching problems: {e}")

def solve_sections_in_range(section_input: str, chapters: list, code: str, auth: str):
    global progress_data
    progress_data.clear()  # Clear progress data before starting

    sections_to_solve = parse_section_input(section_input)
    for chapter_num, section_nums in sections_to_solve.items():
        for chapter in chapters:
            if int(chapter['number']) == chapter_num:
                for section in chapter['sections']:
                    if int(section['number']) in section_nums:
                        solve_section(section, code, chapter, auth)

def parse_section_input(section_input: str) -> dict:
    # Simple validation for the section input format
    if not section_input or any(char in section_input for char in "<>{}[]"):
        raise ValueError("Invalid section input format.")

    sections = section_input.replace(" ", "").split(",")
    parsed_sections = {}
    for sec in sections:
        if "-" in sec:
            start, end = sec.split("-")
            start_ch, start_sec = map(int, start.split("."))
            end_ch, end_sec = map(int, end.split("."))
            for ch in range(start_ch, end_ch + 1):
                if ch not in parsed_sections:
                    parsed_sections[ch] = set()
                parsed_sections[ch].update(range(start_sec if ch == start_ch else 1, end_sec + 1 if ch == end_ch else 100))
        else:
            ch, sec = map(int, sec.split("."))
            if ch not in parsed_sections:
                parsed_sections[ch] = set()
            parsed_sections[ch].add(sec)
    return parsed_sections

def solve_section(section, code, chapter, auth):
    sec_name = f"{chapter['number']}.{section['number']}"
    sec_id = section["canonical_section_id"]

    try:
        problems = get_problems(code, chapter["number"], section["number"], auth)
    except Exception as e:
        progress_data.append(f"Failed solving {sec_name}, skipping section due to error: {e}")
        return

    progress_data.append(f"Starting section {sec_name}: {section['title']}")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        for problem in problems:
            act_id = problem["id"]
            parts = problem.get("parts", 1)
            for part in range(parts):
                executor.submit(solve_part, act_id, sec_id, auth, part, code)

def solve_part(act_id: str, sec_id: str, auth: str, part: int, code: str) -> bool:
    try:
        spend_time(auth, sec_id, act_id, part, code)
        ts = gen_timestamp()
        chksm = gen_chksum(act_id, ts, auth, part)
        url = f"https://zyserver.zybooks.com/v1/content_resource/{act_id}/activity"
        headers = {
            "Host": "zyserver.zybooks.com",
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "Origin": "https://learn.zybooks.com"
        }
        data = {
            "part": part,
            "complete": True,
            "metadata": "{}",
            "zybook_code": code,
            "auth_token": auth,
            "timestamp": ts,
            "__cs__": chksm
        }

        response = session.post(url, json=data, headers=headers)
        response.raise_for_status()
        progress_data.append(f"Solved part {part+1} of activity {act_id}")
        return response.json().get("success", False)
    except Exception as e:
        progress_data.append(f"Error solving part {part+1} of activity {act_id}: {e}")
        return False

def spend_time(auth: str, sec_id: str, act_id: str, part: int, code: str) -> bool:
    global t_spfd
    try:
        time_spent = max(random.randint(20, 60), 20)
        t_spfd += time_spent
        data = {
            "time_spent_records": [
                {
                    "canonical_section_id": sec_id,
                    "content_resource_id": act_id,
                    "part": part,
                    "time_spent": time_spent,
                    "timestamp": gen_timestamp()
                }
            ],
            "auth_token": auth
        }
        response = session.post(f"https://zyserver2.zybooks.com/v1/zybook/{code}/time_spent", json=data)
        response.raise_for_status()
        return response.json().get("success", False)
    except requests.RequestException as e:
        progress_data.append(f"Error in spend_time: {e}")
        return False

def gen_timestamp() -> str:
    global t_spfd
    current_time = datetime.now() + timedelta(seconds=t_spfd)
    ms = f"{random.randint(0, 999):03}"
    return current_time.strftime(f"%Y-%m-%dT%H:%M:%S.{ms}Z")

def gen_chksum(act_id: str, ts: str, auth: str, part: int) -> str:
    md5 = hashlib.md5()
    data = f"content_resource/{act_id}/activity{ts}{auth}{act_id}{part}true{get_buildkey()}"
    md5.update(data.encode("utf-8"))
    return md5.hexdigest()

def get_buildkey() -> str:
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.data = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, Union[str, None]]]) -> None:
            if tag == "meta" and attrs[0][1] == "zybooks-web/config/environment":
                self.data = json.loads(parse.unquote(attrs[1][1]))['APP']['BUILDKEY']

    try:
        response = session.get("https://learn.zybooks.com")
        response.raise_for_status()
        p = Parser()
        p.feed(response.text)
        return p.data
    except requests.RequestException as e:
        raise ZyBooksError(f"Error fetching build key: {e}")

# Flask routes
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        usr = request.form.get('username')
        pwd = request.form.get('password')
        try:
            response = signin(usr, pwd)
            flask_session['auth_token'] = response["auth_token"]
            flask_session['user_id'] = response["user_id"]
            return redirect(url_for('select_book'))
        except ZyBooksError as e:
            flash(f"Login failed: {str(e)}", 'danger')

    return render_template('index.html')

@app.route('/select_book', methods=['GET', 'POST'])
@login_required  # Enforce login for this route
def select_book():
    auth_token = flask_session['auth_token']
    user_id = flask_session['user_id']

    if request.method == 'POST':
        selected_book = request.form.get('book')
        section_input = request.form.get('sections')
        flask_session['selected_book'] = selected_book
        flask_session['section_input'] = section_input
        return redirect(url_for('solve'))

    try:
        books = get_books(auth_token, user_id)
        return render_template('select_book.html', books=books)
    except ZyBooksError as e:
        flash(f"Failed to load books: {str(e)}", 'danger')
        return redirect(url_for('index'))

@app.route('/solve', methods=['GET'])
@login_required  # Enforce login for this route
def solve():
    auth_token = flask_session['auth_token']
    selected_book = flask_session['selected_book']
    section_input = flask_session['section_input']

    try:
        chapters = get_chapters(selected_book, auth_token)
        solve_sections_in_range(section_input, chapters, selected_book, auth_token)
        flash(f'Successfully solved sections {section_input} for {selected_book}.', 'success')
    except Exception as e:
        flash(f"Error solving sections: {str(e)}", 'danger')
    
    return render_template('progress.html')

# Route to stream progress updates
@app.route('/progress_stream')
@login_required  # Protect the progress stream from unauthorized access
def progress_stream():
    def generate():
        while True:
            if progress_data:
                data = progress_data.pop(0)
                yield f"data: {data}\n\n"
            time.sleep(0.5)  # Introduce a short delay to simulate real-time updates
    return Response(generate(), mimetype='text/event-stream')

if __name__ == "__main__":
    app.run(debug=True)
