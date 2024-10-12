from flask import Flask, jsonify, render_template, request, redirect, url_for, session, flash
import concurrent.futures
import os
import stripe
from ZybookAuto import signin, get_books, get_chapters, solve_sections_in_range, ZyBooksError
from itsdangerous import URLSafeTimedSerializer

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersupersupersecretkey')
stripe.api_key = os.getenv('STRIPE_PRIVATE_KEY')
serializer = URLSafeTimedSerializer(app.secret_key)

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
    if 'auth_token' not in session:
        return redirect(url_for('login'))

    try:
        auth = serializer.loads(session['auth_token'], max_age=3600)
    except Exception:
        flash("Session expired. Please log in again.")
        return redirect(url_for('login'))

    usr_id = session['user_id']

    # Get list of ZyBooks
    try:
        books = get_books(auth, usr_id)
        if request.method == 'POST':
            selected_book_index = int(request.form['zybook']) - 1
            selected_book = books[selected_book_index]
            session['zybook_code'] = selected_book['zybook_code']
            return redirect(url_for('select_sections'))
        return render_template('zybook.html', books=books)
    except ZyBooksError as e:
        flash(f"Failed to retrieve ZyBooks: {str(e)}")
        return redirect(url_for('login'))

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

@app.route('/create-checkout-session/<sections>', methods=['GET'])
def create_checkout_session(sections):
    try:
        # Get the chapters from the session (since they were already retrieved during section selection)
        if 'zybook_code' not in session or 'auth_token' not in session:
            return redirect(url_for('login'))

        try:
            auth = serializer.loads(session['auth_token'], max_age=3600)
        except Exception:
            flash("Session expired. Please log in again.")
            return redirect(url_for('login'))

        zybook_code = session['zybook_code']
        chapters = get_chapters(zybook_code, auth)

        # Parse the input string (e.g., "5.6-5.7, 5.9")
        section_ranges = sections.split(',')
        section_count = 0

        # Loop through each range and calculate the sections
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

        # Calculate the total price (in cents) at $1.25 per section
        price_per_section = 125 # $1.25 in cents
        total_price = section_count * price_per_section

        # Create a new Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'ZyBooks Section Solver',
                        'description': f'Solving {section_count} sections: {sections}',
                    },
                    'unit_amount': total_price,  # Total price based on number of sections
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=url_for('success', _external=True),
            cancel_url=url_for('cancel', _external=True),
        )
        return jsonify({'id': checkout_session.id})
    except Exception as e:
        return str(e)
    
@app.route('/success')
def success():
    return "Payment was successful! We are now solving your ZyBook sections."

@app.route('/cancel')
def cancel():
    return "Payment was cancelled. Please try again."

if __name__ == '__main__':
    app.run(debug=False)