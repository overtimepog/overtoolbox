import undetected_chromedriver as uc
import requests
from time import sleep
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.common.keys import Keys
import logging
import openai
import base64
from io import BytesIO
from PIL import Image
import re
from bs4 import BeautifulSoup
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
import os

def find_element_with_retry(driver, by, value, retries=5, delay=1, log_attempts=True):
    """
    Tries to find an element in the DOM. Retries if it is not found.
    
    :param driver: The Selenium WebDriver instance.
    :param by: The By selector type.
    :param value: The selector value.
    :param retries: Number of retries to find the element.
    :param delay: Delay between retries in seconds.
    :return: WebElement if found, None otherwise.
    """
    for attempt in range(retries):
        try:
            if log_attempts:
                logging.info(f"Attempt {attempt + 1}/{retries}: Finding element with {by}='{value}'...")
            element = driver.find_element(by, value)
            if element:
                if log_attempts:
                    logging.info(f"Element found: {element.tag_name} with {by}='{value}'")
                return element
            else:
                if log_attempts:
                    logging.warning(f"Element not found. Retrying in {delay} seconds...")
                sleep(delay)
        except NoSuchElementException:
            if log_attempts:
                logging.warning(f"Element not found. Retrying in {delay} seconds...")
            sleep(delay)
    if log_attempts:
        logging.error(f"Element not found after {retries} attempts with {by}='{value}'.")
    return None

def find_elements_with_retry(driver, by, value, retries=5, delay=1, log_attempts=True):
    """
    Tries to find multiple elements in the DOM. Retries if none are found.
    
    :param driver: The Selenium WebDriver instance.
    :param by: The By selector type.
    :param value: The selector value.
    :param retries: Number of retries to find the elements.
    :param delay: Delay between retries in seconds.
    :return: List of WebElements if found, empty list otherwise.
    """
    for attempt in range(retries):
        try:
            if log_attempts:
                logging.info(f"Attempt {attempt + 1}/{retries}: Finding elements with {by}='{value}'...")
            elements = driver.find_elements(by, value)
            if elements:
                if log_attempts:
                    logging.info(f"Found {len(elements)} elements with {by}='{value}'.")
                return elements
            else:
                if log_attempts:
                    logging.warning(f"No elements found. Retrying in {delay} seconds...")
                sleep(delay)
        except NoSuchElementException:
            if log_attempts:
                logging.warning(f"Exception occurred. Retrying in {delay} seconds...")
            sleep(delay)
    if log_attempts:
        logging.error(f"No elements found after {retries} attempts with {by}='{value}'.")
    return []

def find_element_in_parent_with_retry(parent_element, by, value, retries=5, delay=1, log_attempts=True):
    """
    Tries to find an element within a parent element in the DOM. Retries if it is not found.
    
    :param parent_element: The parent WebElement to search within.
    :param by: The By selector type.
    :param value: The selector value.
    :param retries: Number of retries to find the element.
    :param delay: Delay between retries in seconds.
    :return: WebElement if found, None otherwise.
    """
    for attempt in range(retries):
        try:
            if log_attempts:
                logging.info(f"Attempt {attempt + 1}/{retries}: Finding element within parent with {by}='{value}'...")
            element = parent_element.find_element(by, value)
            if element:
                if log_attempts:
                    logging.info(f"Element found within parent: {element.tag_name} with {by}='{value}'")
                return element
            else:
                if log_attempts:
                    logging.warning(f"Element not found within parent. Retrying in {delay} seconds...")
                sleep(delay)
        except NoSuchElementException:
            if log_attempts:
                logging.warning(f"Element not found within parent. Retrying in {delay} seconds...")
            sleep(delay)
    if log_attempts:
        logging.error(f"Element not found within parent after {retries} attempts with {by}='{value}'.")
    return None

def find_elements_in_parent_with_retry(parent_element, by, value, retries=5, delay=1, log_attempts=True):
    """
    Tries to find multiple elements within a parent element in the DOM. Retries if none are found.
    
    :param parent_element: The parent WebElement to search within.
    :param by: The By selector type.
    :param value: The selector value.
    :param retries: Number of retries to find the elements.
    :param delay: Delay between retries in seconds.
    :return: List of WebElements if found, empty list otherwise.
    """
    for attempt in range(retries):
        try:
            if log_attempts:
                logging.info(f"Attempt {attempt + 1}/{retries}: Finding elements within parent with {by}='{value}'...")
            elements = parent_element.find_elements(by, value)
            if elements:
                if log_attempts:
                    logging.info(f"Found {len(elements)} elements within parent with {by}='{value}'.")
                return elements
            else:
                if log_attempts:
                    logging.warning(f"No elements found within parent. Retrying in {delay} seconds...")
                sleep(delay)
        except NoSuchElementException:
            if log_attempts:
                logging.warning(f"Exception occurred. Retrying in {delay} seconds...")
            sleep(delay)
    if log_attempts:
        logging.error(f"No elements found within parent after {retries} attempts with {by}='{value}'.")
    return []

def get_answer_from_html(html, question_number):
    """
    Send the entire question HTML to AI and get the answer.

    :param html: The entire HTML of the question.
    :param question_number: The question number for logging purposes.
    :return: A list of answers for each sub-question in plain text format.
    """
    # Initialize OpenAI API key securely (use environment variable instead of hardcoding)
    client = openai.Client(
        base_url="https://openrouter.ai/api/v1",
        api_key="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",  # Use an environment variable
    )

    # Send the parsed math problem to AI
    completion = client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant specialized in mathematics. Your task is to provide answers for math problems in a format suitable for direct input into a calculator interface. "
                    "Use proper mathematical symbols like ∞, ∪, etc. Only Include the information necessary for the answer, not the entire question. "
                    "Use the right arrow symbol (→) to indicate when navigation out of contexts like exponents or fractions is needed. "
                    "Provide each answer in a separate code block for easy copy-pasting."
                )
            },
            {
                "role": "user",
                "content": (
                    f"{html} give me the answer to the math problems (a) (b) (c)... etc provide each answer in a easy copy paste codeblock "
                    f"provide all the answers at the bottom in separate codeblocks, make sure to be using the proper symbols (∞, ∪... etc) "
                    f"don't put the 'f(x) =' part, only put what needs to go into the textboxes. "
                    f"Use the right arrow symbol (→) when navigation out of contexts like exponents or fractions is needed."
                    f"only add one set of answers per question, if there are multiple parts to the question, only add one set of answers."
                    f"Only Include the information necessary for the answer, not the entire question, ie. (f ∘ g)(1) = 7/19 would just be 7/19"
                )
            }
        ]
    )

    # Extract answers from AI response
    response = completion.choices[0].message.content.strip()
    
    print("AI Response: ", response + "\n" + "-"*20)
    
    # Remove any language label from code block markers
    response = re.sub(r'```[a-zA-Z]+', '```', response)
    
    # Extract code blocks from the response
    answers = re.findall(r'```(.*?)```', response, re.DOTALL)
    answers = [answer.strip() for answer in answers]
    
    # Log the answers received for the question
    logging.info(f"AI responses for question {question_number}:")
    for idx, answer in enumerate(answers, start=1):
        logging.info(f"Sub-question {idx}: {answer}")

    return answers

def input_answer_into_text_field(driver, element: WebElement, answer):
    """
    Input the answer into a text field, handling both mathpad wrappers and qTextField inputs.
    """
    try:
        # Scroll the element into view
        driver.execute_script("arguments[0].scrollIntoView();", element)
        
        input_field = None
        math_editable_field = None  # Ensure math_editable_field is defined

        # Determine the type of the input and find the actual input field
        if "mathpad-wrapper" in element.get_attribute("class"):
            # Handle MathPad Wrappers
            input_field = find_element_with_retry(element, By.CLASS_NAME, "mq-textarea", retries=5)
            if input_field:
                print("Input Type: MathPad")
                math_editable_field = input_field
                    
        elif "qTextField" in element.get_attribute("class"):
            # Handle qTextField elements
            math_editable_field = find_element_in_parent_with_retry(element, By.XPATH, "./input", retries=5)
            if input_field:
                print("Input Type: Text Field")
                math_editable_field = input_field  # Same as input field for text fields
        else:
            logging.warning("Unknown input field type. Skipping.")
            return
        
        if not input_field or not math_editable_field:
            logging.warning("Input field or MathQuill editable field not found. Skipping.")
            return
        
        # Focus on the MathPad editable field or the input field
        driver.execute_script("arguments[0].focus();", math_editable_field)
        ActionChains(driver).move_to_element(math_editable_field).click().perform()
        
        # Clear the existing content in the input field using a combination of methods
        try:
            # Clear using CTRL/CMD + A, then DELETE
            math_editable_field.send_keys(Keys.CONTROL + 'a')
            math_editable_field.send_keys(Keys.DELETE)
            math_editable_field.send_keys(Keys.BACKSPACE)  # Ensure field is clear

            math_editable_field.send_keys(Keys.COMMAND + 'a')  # For Mac users
            math_editable_field.send_keys(Keys.DELETE)
            math_editable_field.send_keys(Keys.BACKSPACE)  # Ensure field is clear
            
            # Clear the text field again using clear() method if available
            if input_field.tag_name in ['input', 'textarea']:
                input_field.clear()
        except Exception as clear_exception:
            logging.warning(f"Failed to clear using normal methods, error: {clear_exception}")
            # Fallback to JavaScript for clearing the field
            driver.execute_script("arguments[0].value = '';", input_field)
        
        # Clean the answer
        answer_clean = clear_labels(answer)
        if answer_clean == 'skip':
            logging.info("Question is already answered.")
            return
        
        # Type the cleaned answer character by character with right arrow simulation
        for char in answer_clean:
            if char == '→':
                math_editable_field.send_keys(Keys.ARROW_RIGHT)
            else:
                math_editable_field.send_keys(char)
                math_editable_field.send_keys(Keys.ARROW_RIGHT)  # Simulate pressing the right arrow key after each character
            sleep(0.1)  # Small delay between each key press to mimic human typing speed
        
        logging.info(f"Typed answer '{answer_clean}' into text field character by character.")
    except Exception as e:
        logging.error(f"Error inputting answer into text field: {e}")
        # Fallback to using JavaScript if the element is not interactable
        try:
            if math_editable_field:
                driver.execute_script("arguments[0].focus();", math_editable_field)  # Focus on the element using JavaScript
                for char in answer_clean:
                    driver.execute_script("arguments[0].value += arguments[1];", math_editable_field, char)  # Append each character
                    sleep(0.1)  # Mimic typing delay
                logging.info("Used JavaScript to set the value directly character by character.")
            else:
                logging.error("math_editable_field is not defined, cannot use JavaScript fallback.")
        except Exception as js_e:
            logging.error(f"Error using JavaScript to set the value: {str(js_e)}")

def input_answer_into_radio_buttons(driver, radio_buttons, answer):
    """
    Input the answer by selecting the appropriate radio button.
    """
    for radio_button in radio_buttons:
        label = find_element_in_parent_with_retry(radio_button, By.XPATH, f"//label[@for='{radio_button.get_attribute('id')}']", retries=1)
        if label and answer == label.text.strip():
            driver.execute_script("arguments[0].scrollIntoView();", radio_button)
            driver.execute_script("arguments[0].click();", radio_button)
            logging.info(f"Clicked radio button with label '{label.text.strip()}'")
            break

def input_answer_into_dropdown(driver, select_element, answer):
    """
    Input the answer by selecting the appropriate option in a dropdown.
    """
    options = find_elements_in_parent_with_retry(select_element, By.TAG_NAME, 'option', retries=1)
    for option in options:
        if answer == option.text.strip():
            driver.execute_script("arguments[0].scrollIntoView();", select_element)
            driver.execute_script("arguments[0].value = arguments[1];", select_element, option.get_attribute("value"))
            logging.info(f"Selected option '{answer}' in dropdown with id '{select_element.get_attribute('id')}'")
            break
        
def clear_labels(text):
    # Regular expression to match any letter followed by ), :, ., or ,
    cleaned_text = re.sub(r'\b[a-zA-Z][):.,]', '', text)
    return cleaned_text.strip()


def collect_urls_from_math(driver, log_attempts):
    assignment_list = find_element_with_retry(driver, By.CLASS_NAME, 'css-1axo6kt', log_attempts=log_attempts)

    # List to store the hrefs of all assignments
    assignment_hrefs = []

    if assignment_list:
        # Find all <a> elements within the <ul> element using the utility function
        assignment_links = find_elements_in_parent_with_retry(assignment_list, By.TAG_NAME, 'a', log_attempts=log_attempts)

        # Collect hrefs from each <a> element, checking if the assignment is disabled
        for link in assignment_links:
            aria_label = link.get_attribute('aria-label')
            if "disabled" not in aria_label:  # Check if the link is not disabled
                href = link.get_attribute('href')
                if href:
                    assignment_hrefs.append(href)
                    logging.info(f"Enabled Assignment HREF: {href}")
            else:
                logging.info(f"Disabled Assignment Skipped: {aria_label}")

        # Print collected hrefs
        logging.info("Collected Assignment HREFs:")
        for href in assignment_hrefs:
            logging.info(href)
            
    return assignment_hrefs


def click_with_retry(element, max_retries=3, retry_delay=2):
    for attempt in range(max_retries):
        try:
            element.click()
            return True
        except WebDriverException as e:
            if attempt < max_retries - 1:
                logging.warning(f"Click failed. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                sleep(retry_delay)
            else:
                logging.error(f"Click failed after {max_retries} attempts. Error: {str(e)}")
                return False
            
            
def select_dropdown_option(driver, element_id, option_value, retries=5, delay=1):
    """
    Selects an option in a dropdown by its value attribute.
    
    :param driver: The Selenium WebDriver instance.
    :param element_id: The ID of the dropdown element.
    :param option_value: The value of the option to select.
    :param retries: Number of retries if the dropdown or option is not found.
    :param delay: Delay between retries in seconds.
    """
    dropdown = find_element_with_retry(driver, By.ID, element_id, retries, delay)
    
    if dropdown:
        # Use JavaScript to set the value directly
        driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));", dropdown, option_value)
        logging.info(f"Selected option '{option_value}' in dropdown with id '{element_id}'")
    else:
        logging.error(f"Dropdown with id '{element_id}' not found.")
        
def fetch_grades_page(url):
    """
    Fetches the HTML content of the grades page.
    :param url: URL of the grades page.
    :return: HTML content of the page.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error if the request failed
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching the page: {e}")
        return None

def parse_grades(html_content):
    """
    Parses the HTML content and extracts the grades information.
    :param html_content: HTML content of the page.
    :return: List of assignments with their details.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    grades_table = soup.find('table', {'id': 'grades_summary'})

    if not grades_table:
        logging.error("Grades table not found on the page.")
        return []

    assignments = []
    for row in grades_table.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) > 0:
            assignment_name = row.find('th').text.strip()
            due_date = cells[0].text.strip()
            submitted_date = cells[1].text.strip()
            status = cells[2].text.strip()
            score = cells[3].text.strip()

            assignments.append({
                'Assignment': assignment_name,
                'Due Date': due_date,
                'Submitted Date': submitted_date,
                'Status': status,
                'Score': score,
            })

    return assignments

def display_grades(assignments):
    """
    Displays the list of assignments with their details.
    :param assignments: List of assignment dictionaries.
    """
    if not assignments:
        logging.info("No assignments to display.")
        return

    for assignment in assignments:
        logging.info(f"Assignment: {assignment['Assignment']}")
        logging.info(f"Due Date: {assignment['Due Date']}")
        logging.info(f"Submitted Date: {assignment['Submitted Date']}")
        logging.info(f"Status: {assignment['Status']}")
        logging.info(f"Score: {assignment['Score']}")
        logging.info('---')

def get_missing_assignments(assignments):
    """
    Finds and returns a list of missing or unsubmitted assignments.
    :param assignments: List of assignment dictionaries.
    :return: List of missing/unsubmitted assignments.
    """
    missing = []
    for assignment in assignments:
        if assignment['Status'].lower() == "unsubmitted" or assignment['Score'] == '-':
            missing.append(assignment)

    return missing

def encode_image(image_bytes):
    return base64.b64encode(image_bytes).decode('utf-8')

# You might want to add a function to initialize the OpenAI client
def initialize_openai_client():
    return openai.Client(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENAI_API_KEY")  # Use environment variable
    )

# Function to capture and process question
def capture_and_process_question(driver, question_element):
    # Take screenshot of the question element
    image_bytes = question_element.screenshot_as_png
    
    # Convert to base64
    base64_image = encode_image(image_bytes)
    
    # Process with OpenAI Vision
    client = initialize_openai_client()
    response = client.chat.completions.create(
        model="openai/gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's the question in this image and what's the answer?"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        max_tokens=300
    )
    
    # Extract and return the answer
    return response.choices[0].message.content.strip()

def answer_smartbooks_question(driver, question_element, answer):
    """
    Answers a question in SmartBooks based on the question type.
    """
    # Identify the question type
    if find_element_in_parent_with_retry(question_element, By.CLASS_NAME, "mathpad-wrapper"):
        # MathPad question
        input_field = find_element_in_parent_with_retry(question_element, By.CLASS_NAME, "mathpad-wrapper")
        input_answer_into_text_field(driver, input_field, answer)
    elif find_element_in_parent_with_retry(question_element, By.CLASS_NAME, "qTextField"):
        # Text field question
        input_field = find_element_in_parent_with_retry(question_element, By.CLASS_NAME, "qTextField")
        input_answer_into_text_field(driver, input_field, answer)
    elif find_elements_in_parent_with_retry(question_element, By.CSS_SELECTOR, 'input[type="radio"]'):
        # Multiple choice question
        radio_buttons = find_elements_in_parent_with_retry(question_element, By.CSS_SELECTOR, 'input[type="radio"]')
        input_answer_into_radio_buttons(driver, radio_buttons, answer)
    elif find_element_in_parent_with_retry(question_element, By.TAG_NAME, "select"):
        # Dropdown question
        select_element = find_element_in_parent_with_retry(question_element, By.TAG_NAME, "select")
        input_answer_into_dropdown(driver, select_element, answer)
    else:
        logging.warning("Unknown question type in SmartBooks. Unable to answer.")

def answer_canvas_question(driver, question_element, answer):
    """
    Answers a question in Canvas based on the question type.
    """
    # Identify the question type
    if find_element_in_parent_with_retry(question_element, By.CLASS_NAME, "mce-content-body"):
        # Essay question
        input_field = find_element_in_parent_with_retry(question_element, By.CLASS_NAME, "mce-content-body")
        input_answer_into_text_field(driver, input_field, answer)
    elif find_element_in_parent_with_retry(question_element, By.CSS_SELECTOR, 'input[type="text"]'):
        # Short answer question
        input_field = find_element_in_parent_with_retry(question_element, By.CSS_SELECTOR, 'input[type="text"]')
        input_answer_into_text_field(driver, input_field, answer)
    elif find_elements_in_parent_with_retry(question_element, By.CSS_SELECTOR, 'input[type="radio"]'):
        # Multiple choice question
        radio_buttons = find_elements_in_parent_with_retry(question_element, By.CSS_SELECTOR, 'input[type="radio"]')
        input_answer_into_radio_buttons(driver, radio_buttons, answer)
    elif find_elements_in_parent_with_retry(question_element, By.CSS_SELECTOR, 'input[type="checkbox"]'):
        # Multiple answer question
        checkboxes = find_elements_in_parent_with_retry(question_element, By.CSS_SELECTOR, 'input[type="checkbox"]')
        for checkbox in checkboxes:
            label = find_element_in_parent_with_retry(checkbox.find_element(By.XPATH, ".."), By.TAG_NAME, "label")
            if label and label.text.strip() in answer:
                checkbox.click()
    elif find_element_in_parent_with_retry(question_element, By.TAG_NAME, "select"):
        # Dropdown question
        select_element = find_element_in_parent_with_retry(question_element, By.TAG_NAME, "select")
        input_answer_into_dropdown(driver, select_element, answer)
    else:
        logging.warning("Unknown question type in Canvas. Unable to answer.")

def process_smartbooks_questions(driver):
    """
    Processes all questions on a SmartBooks page.
    """
    questions = find_elements_with_retry(driver, By.CLASS_NAME, "dlc_question")
    for idx, question in enumerate(questions, 1):
        answer = capture_and_process_question(driver, question)
        logging.info(f"SmartBooks Question {idx}: {answer}")
        answer_smartbooks_question(driver, question, answer)

def process_canvas_questions(driver):
    """
    Processes all questions on a Canvas page.
    """
    questions = find_elements_with_retry(driver, By.CLASS_NAME, "question")
    for idx, question in enumerate(questions, 1):
        answer = capture_and_process_question(driver, question)
        logging.info(f"Canvas Question {idx}: {answer}")
        answer_canvas_question(driver, question, answer)

# Update the main processing function to handle both platforms
def process_questions_on_page(driver, platform):
    if platform.lower() == 'smartbooks':
        process_smartbooks_questions(driver)
    elif platform.lower() == 'canvas':
        process_canvas_questions(driver)
    else:
        logging.error(f"Unknown platform: {platform}")