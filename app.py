from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash, Response, send_from_directory, make_response
import concurrent.futures
import os
import queue
import threading
from datetime import datetime, timedelta
# import stripe
from ZybookAuto import signin, get_books, get_chapters, solve_sections_in_range, ZyBooksError, solve_section
import asyncio
from membean import membean
from itsdangerous import URLSafeTimedSerializer

# Initialize Flask app with static folder configuration
app = Flask(__name__, 
    static_url_path='/static',
    static_folder='templates/static'
)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersupersupersecretsuperkey')
# stripe.api_key = os.getenv('STRIPE_PRIVATE_KEY')
serializer = URLSafeTimedSerializer(app.secret_key)

# Create queues for output streaming
zybooks_output = queue.Queue()
membean_output = queue.Queue()

# Route for main menu
@app.route('/')
def index():
    return render_template('index.html')

# Membean routes
@app.route('/membean', methods=['GET', 'POST'])
def membean_route():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        grade = request.form['grade']
        quiz = request.form['quiz']
        openai_key = request.form.get('openai_key')
        remember = request.form.get('remember') == 'on'
        
        # Validate OpenAI key is provided when quiz mode is enabled
        if quiz == 'True' and not openai_key:
            flash('OpenAI API key is required when quiz mode is enabled')
            return redirect(url_for('membean_route'))
        
        try:
            args = ['-e', email, '-p', password, '-g', grade, '-q', quiz]
            if quiz == 'True':
                args.extend(['-k', openai_key])
            
            # Create response object
            resp = make_response(redirect(url_for('membean_route')))
            
            # Set cookies if remember me is checked
            if remember:
                # Save credentials and settings
                resp.set_cookie('membean_email', email, max_age=30*24*60*60)  # 30 days
                resp.set_cookie('membean_password', password, max_age=30*24*60*60, secure=True, httponly=True)
                resp.set_cookie('membean_grade', grade, max_age=30*24*60*60)
                resp.set_cookie('membean_quiz', quiz, max_age=30*24*60*60)
                # Save OpenAI key if provided
                if openai_key:
                    resp.set_cookie('membean_openai_key', openai_key, max_age=30*24*60*60, secure=True, httponly=True)
            else:
                # Clear all cookies if remember me is unchecked
                resp.delete_cookie('membean_email')
                resp.delete_cookie('membean_password')
                resp.delete_cookie('membean_grade')
                resp.delete_cookie('membean_quiz')
                resp.delete_cookie('membean_openai_key')
            
            # Start membean in a separate thread
            def run_membean():
                try:
                    capture_output(membean_output, "Starting Membean Docker container...")
                    asyncio.run(membean(args))
                    capture_output(membean_output, "Membean session completed successfully!")
                except Exception as e:
                    capture_output(membean_output, f"Error in Membean: {str(e)}")
            
            thread = threading.Thread(target=run_membean)
            thread.daemon = True
            thread.start()
            
            flash('Membean session started successfully!')
            return resp
            
        except Exception as e:
            flash(f'Error starting Membean: {str(e)}')
            return redirect(url_for('membean_route'))
    
    # For GET request, get saved credentials and settings from cookies
    saved_email = request.cookies.get('membean_email', '')
    saved_password = request.cookies.get('membean_password', '')
    saved_grade = request.cookies.get('membean_grade', '')
    saved_quiz = request.cookies.get('membean_quiz', '')
    saved_openai_key = request.cookies.get('membean_openai_key', '')
    
    return render_template('membean.html', 
                         saved_email=saved_email,
                         saved_password=saved_password,
                         saved_grade=saved_grade,
                         saved_quiz=saved_quiz,
                         saved_openai_key=saved_openai_key)

# Route for login page
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usr = request.form['email']
        pwd = request.form['password']
        try:
            session_data = signin(usr, pwd)
            session['user_id'] = session_data['user_id']
            session['email'] = usr
            session['auth_token'] = serializer.dumps(session_data['auth_token'])
            return redirect(url_for('zybook'))
        except ZyBooksError as e:
            flash(f"Login failed: {str(e)}")
            return render_template('login.html')
    return render_template('login.html')

# Route for selecting ZyBook and sections
@app.route('/zybook', methods=['GET', 'POST'])
def zybook():
    if request.method == 'POST':
        usr = request.form['email']
        pwd = request.form['password']
        remember = request.form.get('remember') == 'on'
        
        try:
            session_data = signin(usr, pwd)
            session['user_id'] = session_data['user_id']
            session['email'] = usr
            session['auth_token'] = serializer.dumps(session_data['auth_token'])
            
            # Create response object for redirect
            resp = make_response(redirect(url_for('select_sections')))
            
            # Set cookies if remember me is checked
            if remember:
                resp.set_cookie('zybooks_email', usr, max_age=30*24*60*60)  # 30 days
                resp.set_cookie('zybooks_password', pwd, max_age=30*24*60*60, secure=True, httponly=True)
            else:
                resp.delete_cookie('zybooks_email')
                resp.delete_cookie('zybooks_password')
            
            return resp
            
        except ZyBooksError as e:
            flash(f"Login failed: {str(e)}")
            return redirect(url_for('zybook'))

    # For GET request, get saved credentials from cookies
    saved_email = request.cookies.get('zybooks_email', '')
    saved_password = request.cookies.get('zybooks_password', '')
    
    # Get list of ZyBooks if user is authenticated
    try:
        if 'auth_token' in session:
            auth = serializer.loads(session['auth_token'], max_age=3600)
            usr_id = session['user_id']
            books = get_books(auth, usr_id)
        else:
            books = []
    except Exception:
        books = []
        
    return render_template('zybook.html', books=books, saved_email=saved_email, saved_password=saved_password)

# Route for selecting sections and solving
@app.route('/select_sections', methods=['GET', 'POST'])
def select_sections():
    if 'zybook_code' not in session:
        return redirect(url_for('zybook'))

    try:
        auth = serializer.loads(session['auth_token'], max_age=3600)
    except Exception:
        flash("Session expired. Please log in again.")
        return redirect(url_for('login'))

    zybook_code = session['zybook_code']
    chapters = get_chapters(zybook_code, auth)

    if request.method == 'POST':
        # Parse the input string (e.g., "5.6-5.7, 5.9")
        section_ranges = request.form['sections'].split(',')
        section_count = 0

        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Loop through each range and calculate the sections
            futures = []
            for section_range in section_ranges:
                section_range = section_range.strip()
                if '-' in section_range:
                    # Range format (e.g., "5.6-5.7")
                    start, end = section_range.split('-')
                    start_chapter, start_section = map(int, start.split('.'))
                    end_chapter, end_section = map(int, end.split('.'))
                else:
                    # Single section format (e.g., "5.9")
                    start_chapter, start_section = map(int, section_range.split('.'))
                    end_chapter, end_section = start_chapter, start_section

                # Calculate the number of sections for the current range
                section_count += calculate_sections(chapters, start_chapter, start_section, end_chapter, end_section)

                # Start solving sections using thread pool
                futures.append(executor.submit(solve_sections_in_range, start_chapter, start_section, end_chapter, end_section, chapters, zybook_code, auth))

        flash(f"Started solving {section_count} sections. Check the console for progress.")
        return redirect(url_for('select_sections'))

    return render_template('select_sections.html', chapters=chapters)

def calculate_sections(chapters, start_chapter, start_section, end_chapter, end_section):
    section_count = 0
    counting_started = False

    print(f"Start counting from chapter {start_chapter}.{start_section} to chapter {end_chapter}.{end_section}")

    for chapter in chapters:
        chapter_num = int(chapter['number'])
        print(f"Checking chapter {chapter_num}...")

        # Start counting when we hit the start chapter
        if chapter_num == start_chapter:
            print(f"Reached start chapter: {chapter_num}")
            section_idx = 0  # Index to loop through sections in chapter
            while section_idx < len(chapter['sections']):
                section = chapter['sections'][section_idx]
                section_num = int(section['number'])
                print(f"Checking section {chapter_num}.{section_num}...")

                # Only count sections from the start section onward
                if section_num >= start_section:
                    section_count += 1
                    print(f"Counting section {chapter_num}.{section_num}, total count: {section_count}")

                # Stop if we reach the end section in the start chapter
                if chapter_num == end_chapter and section_num == end_section:
                    print(f"Reached end section: {chapter_num}.{section_num}. Stopping.")
                    return section_count

                section_idx += 1

            counting_started = True

        # If counting has started and we're in an intermediate chapter, count all sections
        elif counting_started and start_chapter < chapter_num < end_chapter:
            print(f"Counting all sections in chapter {chapter_num}")
            section_count += len(chapter['sections'])
            print(f"Added {len(chapter['sections'])} sections, total count: {section_count}")

        # If we're at the end chapter, use a while loop to count sections up to end section and stop
        elif chapter_num == end_chapter:
            print(f"Reached end chapter: {chapter_num}")
            section_idx = 0
            while section_idx < len(chapter['sections']):
                section = chapter['sections'][section_idx]
                section_num = int(section['number'])
                print(f"Checking section {chapter_num}.{section_num}...")

                # Count sections up to and including the end section
                if section_num <= end_section:
                    section_count += 1
                    print(f"Counting section {chapter_num}.{section_num}, total count: {section_count}")

                # Stop once the end section is reached
                if section_num == end_section:
                    print(f"Reached end section: {chapter_num}.{section_num}. Stopping.")
                    return section_count

                section_idx += 1

    return section_count

# Stripe routes commented out
# @app.route('/create-checkout-session/<sections>', methods=['GET'])
# def create_checkout_session(sections):
#     try:
#         # Get the chapters from the session (since they were already retrieved during section selection)
#         if 'zybook_code' not in session or 'auth_token' not in session:
#             return redirect(url_for('login'))
# 
#         try:
#             auth = serializer.loads(session['auth_token'], max_age=3600)
#         except Exception:
#             flash("Session expired. Please log in again.")
#             return redirect(url_for('login'))
# 
#         zybook_code = session['zybook_code']
#         chapters = get_chapters(zybook_code, auth)
# 
#         # Parse the input string (e.g., "5.6-5.7, 5.9")
#         section_ranges = sections.split(',')
#         section_count = 0
# 
#         # Loop through each range and calculate the sections
#         for section_range in section_ranges:
#             section_range = section_range.strip()
#             if '-' in section_range:
#                 # Range format (e.g., "5.6-5.7")
#                 start, end = section_range.split('-')
#                 start_chapter, start_section = map(int, start.split('.'))
#                 end_chapter, end_section = map(int, end.split('.'))
#             else:
#                 # Single section format (e.g., "5.9")
#                 start_chapter, start_section = map(int, section_range.split('.'))
#                 end_chapter, end_section = start_chapter, start_section
# 
#             # Calculate the number of sections for the current range
#             section_count += calculate_sections(chapters, start_chapter, start_section, end_chapter, end_section)
# 
#         # Calculate the total price (in cents) at $1.25 per section
#         price_per_section = 125 # $1.25 in cents
#         total_price = section_count * price_per_section
# 
#         # Create a new Stripe Checkout Session
#         checkout_session = stripe.checkout.Session.create(
#             payment_method_types=['card'],
#             line_items=[{
#                 'price_data': {
#                     'currency': 'usd',
#                     'product_data': {
#                         'name': 'ZyBooks Section Solver',
#                         'description': f'Solving {section_count} sections: {sections}',
#                     },
#                     'unit_amount': total_price,  # Total price based on number of sections
#                 },
#                 'quantity': 1,
#             }],
#             mode='payment',
#             success_url=url_for('success', _external=True),
#             cancel_url=url_for('cancel', _external=True),
#         )
#         return jsonify({'id': checkout_session.id})
#     except Exception as e:
#         return str(e)
#     
# @app.route('/success')
# def success():
#     return "Payment was successful! We are now solving your ZyBook sections."
# 
# @app.route('/cancel')
# def cancel():
#     return "Payment was cancelled. Please try again."

# Route for streaming Zybooks terminal output
@app.route('/terminal-output')
def terminal_output():
    def generate():
        while True:
            try:
                # Get output from queue with timeout
                output = zybooks_output.get(timeout=1)
                yield f"data: {output}\n\n"
            except queue.Empty:
                # If no output for 1 second, send heartbeat
                yield f"data: {datetime.now().isoformat()}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

# Route for streaming Docker container output
@app.route('/docker-output')
def docker_output():
    def generate():
        while True:
            try:
                # Get output from queue with timeout
                output = membean_output.get(timeout=1)
                yield f"data: {output}\n\n"
            except queue.Empty:
                # If no output for 1 second, send heartbeat
                yield f"data: {datetime.now().isoformat()}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

# Helper function to capture and queue output
def capture_output(queue_obj, output_str):
    queue_obj.put(output_str)

# Update the solve_sections_in_range function to capture output
def solve_sections_in_range(start_chapter, start_section, end_chapter, end_section, chapters, code, auth):
    """Solve sections in a range across chapters."""
    for chapter in chapters:
        chapter_num = int(chapter['number'])

        if chapter_num < start_chapter:
            continue

        if chapter_num > end_chapter:
            break

        for section in chapter['sections']:
            section_num = int(section['number'])

            if chapter_num == start_chapter and section_num < start_section:
                continue

            if chapter_num == end_chapter and section_num > end_section:
                break

            # Capture output for the current section
            output = f"Solving section {chapter_num}.{section_num}..."
            capture_output(zybooks_output, output)
            
            try:
                solve_section(section, code, chapter, auth)
                capture_output(zybooks_output, f"Completed section {chapter_num}.{section_num}")
            except Exception as e:
                capture_output(zybooks_output, f"Error in section {chapter_num}.{section_num}: {str(e)}")

if __name__ == '__main__':
    app.run(debug=False)
