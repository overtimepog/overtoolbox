from __future__ import annotations
import os
import sys
import json
import requests
import hashlib
import random
import argparse
import time
import concurrent.futures
from typing import Union
from urllib import parse
from datetime import datetime, timedelta
from html.parser import HTMLParser
from halo import Halo

session = requests.Session()

# Custom exception for better error handling
class ZyBooksError(Exception):
    pass

# Global variables to track time spent and progress
t_spfd = 0
progress = {
    "chapter": None,
    "section": None,
    "problem": None,
    "part": None,
    "total_problems": None,
    "current_problem": None
}

def signin(usr: str, pwd: str) -> dict:
    """Sign in to ZyBooks and return the session details."""
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
    """Retrieve books for the given user."""
    try:
        response = session.get(f"https://zyserver.zybooks.com/v1/user/{usr_id}/items?items=%5B%22zybooks%22%5D&auth_token={auth}")
        response.raise_for_status()
        data = response.json()
        if not data.get("success"):
            raise ZyBooksError("Failed to retrieve books")

        # Filter out autosubscribed books
        return [book for book in data["items"]["zybooks"] if not book["autosubscribe"]]
    except requests.RequestException as e:
        raise ZyBooksError(f"Error fetching books: {e}")

def get_chapters(code: str, auth: str) -> list:
    """Get all chapters and sections for a book."""
    try:
        response = session.get(f"https://zyserver.zybooks.com/v1/zybooks?zybooks=%5B%22{code}%22%5D&auth_token={auth}")
        response.raise_for_status()
        return response.json()["zybooks"][0]["chapters"]
    except requests.RequestException as e:
        raise ZyBooksError(f"Error fetching chapters: {e}")

def get_problems(code: str, chapter: int, section: int, auth: str) -> list:
    """Retrieve problems from a specific chapter and section."""
    try:
        response = session.get(f"https://zyserver.zybooks.com/v1/zybook/{code}/chapter/{chapter}/section/{section}?auth_token={auth}")
        response.raise_for_status()
        return response.json()["section"]["content_resources"]
    except requests.RequestException as e:
        raise ZyBooksError(f"Error fetching problems: {e}")

def spend_time(auth: str, sec_id: str, act_id: str, part: int, code: str) -> bool:
    """Simulate time spent on a problem, and return success status."""
    global t_spfd
    try:
        time_spent = max(random.randint(20, 60), 20)  # Ensure minimum of 20 seconds
        t_spfd += time_spent
        #time.sleep(time_spent)  # Simulate the time delay
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
        print(f"Error in spend_time: {e}")
        return False

def gen_timestamp() -> str:
    """Generate a current timestamp with a randomized millisecond component."""
    global t_spfd
    current_time = datetime.now() + timedelta(seconds=t_spfd)
    ms = f"{random.randint(0, 999):03}"
    return current_time.strftime(f"%Y-%m-%dT%H:%M:%S.{ms}Z")

def gen_chksum(act_id: str, ts: str, auth: str, part: int) -> str:
    """Generate MD5 checksum for verification."""
    md5 = hashlib.md5()
    data = f"content_resource/{act_id}/activity{ts}{auth}{act_id}{part}true{get_buildkey()}"
    md5.update(data.encode("utf-8"))
    return md5.hexdigest()

def get_buildkey() -> str:
    """Retrieve the build key from the ZyBooks environment."""
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

def solve_part(act_id: str, sec_id: str, auth: str, part: int, code: str) -> bool:
    """Solve a specific part of a problem, and track progress."""
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
        return response.json().get("success", False)
    except Exception as e:
        print(f"\nError solving part {part+1} of activity {act_id}: {e}")
        return False  # Skip to the next part or problem

def solve_section(section, code, chapter, auth):
    """Solve all problems in the given section, tracking progress."""
    sec_name = f"{chapter['number']}.{section['number']}"
    print(f"\nStarting section {sec_name}: {section['title']}")
    sec_id = section["canonical_section_id"]

    # Update progress
    progress["chapter"] = chapter["number"]
    progress["section"] = section["number"]

    try:
        problems = get_problems(code, chapter["number"], section["number"], auth)
    except Exception as e:
        print(f"Failed solving {sec_name}, skipping section due to error: {e}")
        return

    progress["total_problems"] = len(problems)
    progress["current_problem"] = 0

    # Initialize the spinner
    spinner = Halo(spinner='dots', text='', color='cyan', stream=sys.stdout)
    spinner.start()

    # Solving all problems concurrently in the section
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        p = 1
        for problem in problems:
            act_id = problem["id"]
            parts = problem.get("parts", 1)

            # Update problem progress
            progress["problem"] = p
            progress["current_problem"] += 1

            for part in range(parts):
                progress["part"] = part + 1
                spinner.text = f"{chapter['number']}.{section['number']} | Question {progress['current_problem']}/{progress['total_problems']} | Sub Question {part+1}/{parts}| Solving..."
                futures.append(executor.submit(solve_part, act_id, sec_id, auth, part, code))
            p += 1

        # Wait for all futures to complete
        concurrent.futures.wait(futures)

    spinner.stop_and_persist(symbol='✔', text=f"Completed section {sec_name}")

    # Reset progress after completing section
    progress["problem"] = None
    progress["part"] = None

def solve_sections_in_range(start_chapter, start_section, end_chapter, end_section, chapters, code, auth):
    """Solve sections in a range across chapters."""
    for chapter in chapters:
        chapter_num = int(chapter['number'])

        if chapter_num < start_chapter:
            continue  # Skip chapters before the start chapter

        if chapter_num > end_chapter:
            break  # Stop once we pass the end chapter

        for section in chapter['sections']:
            section_num = int(section['number'])

            if chapter_num == start_chapter and section_num < start_section:
                continue  # Skip sections before the start section in the start chapter

            if chapter_num == end_chapter and section_num > end_section:
                break  # Stop once we pass the end section in the end chapter

            # Solve the current section
            solve_section(section, code, chapter, auth)

def find_section(chapters, chapter_num, section_num):
    """Find and return the section object based on chapter and section numbers."""
    for chapter in chapters:
        if int(chapter['number']) == chapter_num:
            for section in chapter['sections']:
                if int(section['number']) == section_num:
                    return chapter, section
    return None, None

def get_start_end_input():
    """Get start and end chapter/section inputs from the user."""
    while True:
        try:
            start_input = input("Enter the start chapter.section (e.g., 4.1): ").strip()
            end_input = input("Enter the end chapter.section (e.g., 4.3): ").strip()
            start_chapter, start_section = map(int, start_input.split('.'))
            end_chapter, end_section = map(int, end_input.split('.'))
            return start_chapter, start_section, end_chapter, end_section
        except ValueError:
            print("Invalid input. Please enter chapter and section in the format 'chapter.section' (e.g., 4.1).")