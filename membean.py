from __future__ import print_function
import re
import os
import sys
import time
import random
from time import sleep
from itertools import groupby
from selenium import webdriver
import sys, getopt
import asyncio
import undetected_chromedriver as uc
import docker
import tempfile
import shutil
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import ElementNotInteractableException
import requests
from bs4 import BeautifulSoup
from openai import OpenAI, OpenAIError
import time

async def run_in_docker(email, password, grade, quiz, openai_key=None):
    client = docker.from_env()
    print("Starting Docker container...")
    
    try:
        # Build the Docker image
        print("Building Docker image...")
        image, _ = client.images.build(
            path=".",
            dockerfile="Dockerfile",
            tag="membean-bot:latest"
        )
        
        # Run the container
        print("Running container...")
        command = f"python membean.py -e {email} -p {password} -g {grade} -q {quiz}"
        if openai_key:
            command += f" -k {openai_key}"
            
        container = client.containers.run(
            "membean-bot:latest",
            command=command,
            detach=True,
            auto_remove=True,
            environment={
                "DISPLAY": ":99",
                "PYTHONUNBUFFERED": "1",
                "DBUS_SESSION_BUS_ADDRESS": "/dev/null"
            },
            volumes={
                '/tmp/.X11-unix': {
                    'bind': '/tmp/.X11-unix',
                    'mode': 'rw'
                }
            },
            shm_size='2g'  # Increase shared memory for Chrome
        )
        
        # Stream logs
        for line in container.logs(stream=True, follow=True):
            print(line.decode().strip())
            
    except docker.errors.BuildError as e:
        print(f"Error building Docker image: {e}")
        return False
    except docker.errors.APIError as e:
        print(f"Docker API error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False
    finally:
        # Cleanup
        try:
            container.stop()
        except:
            pass
    
    return True

async def membean(argv):
    # Set up arguments for the email and password
    try:
        opts, args = getopt.getopt(argv,"he:p:g:q:k:",["email=","password=","grade=","quiz=","openai_key="])
    except getopt.GetoptError:
        print('membean.py -e <email> -p <password> -g <grade> -q <quiz> -k <openai_key>')
        await sys.exit(2)
        
    email = None
    password = None
    grade = None
    quiz = None
    openai_key = None
    for opt, arg in opts:
        if opt == '-h':
            print('membean.py -e <email> -p <password> -g <grade> -q <quiz> -k <openai_key>')
            await sys.exit()
        elif opt in ("-e", "--email"):
            email = arg
        elif opt in ("-p", "--password"):
            password = arg
        elif opt in ("-g", "--grade"):
            grade = arg
        elif opt in ("-q", "--quiz"):
            quiz = arg
        elif opt in ("-k", "--openai_key"):
            openai_key = arg
            
    if not all([email, password, grade]):
        print("Email, password, and grade are required")
        await sys.exit(2)
        
    if quiz == "True" and not openai_key:
        print("OpenAI API key is required when quiz mode is enabled")
        await sys.exit(2)
        
    print('Email:', email)
    print('Grade:', grade)
    print('Quiz mode:', quiz)
    retry_delay = 60
    print('Retry delay:', retry_delay)
    
    # Run in Docker container
    if await run_in_docker(email, password, grade, quiz, openai_key):
        print("Successfully completed Membean session in Docker container")
        await sys.exit(0)
    else:
        print("Failed to complete Membean session in Docker container")
        await sys.exit(1)

    if grade != "A+" and grade != "A" and grade != "A-" and grade != "B+" and grade != "B" and grade != "B-":
        print("Invalid grade - please use A+, A, A-, B+, B, or B-")
        await sys.exit(2)

    # Configure Chrome options for Docker container
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Initialize Chrome driver with Docker-compatible options
    driver = uc.Chrome(options=chrome_options)
    def check_exists_by_xpath(xpath):
        try:
            driver.find_element("xpath", xpath)
        except NoSuchElementException:
            return False
        return True
    def check_exists_by_css(css):
        try:
            driver.find_element(By.CSS_SELECTOR, css)
        except NoSuchElementException:
            return False
        return True
    
    print("Starting login process...")
    sleep(3)
    try:
        driver.get("https://www.membean.com/login")
        sleep(3)
        while True:
            if check_exists_by_xpath('//*[@id="content"]/section/ul/li[1]/a'):
                driver.find_element("xpath", '//*[@id="content"]/section/ul/li[1]/a').click()
                print("Clicked Google login")
                break
            else:
                continue
        #input username
        sleep(2)
        while True:
            if check_exists_by_xpath('//*[@id="identifierId"]'):
                usernamebox = driver.find_element("xpath", '//*[@id="identifierId"]')
                for s in email:
                        usernamebox.send_keys(s)
                print("Username entered:", email)
                break
            else:
                print("Waiting for username box...")
                continue

        #Next Button click
        sleep(2)
        while True:
            if check_exists_by_xpath('//*[@id="identifierNext"]/div/button/span'):
                driver.find_element("xpath", '//*[@id="identifierNext"]/div/button/span').click()
                print("Next button clicked")
                break
            else:
                print("Next button not found")
                continue

        #input password
        sleep(2)
        while True:
            if check_exists_by_xpath('//*[@id="password"]/div[1]/div/div[1]/input'):
                passwordbox = driver.find_element("xpath", '//*[@id="password"]/div[1]/div/div[1]/input')
                for s in password:
                    if s == '?':
                        passwordbox.send_keys('?')
                    else:    
                        passwordbox.send_keys(s)
                print("Password entered")
                break
            else:
                print("Waiting for password box...")
                continue
        sleep(2)
        while True:
            if check_exists_by_css('#view_container > div > div > div.pwWryf.bxPAYd > div > div.WEQkZc > div > form > span > section > div > div > div.SdBahf.Fjk18.Jj6Lae > div.OyEIQ.uSvLId > div:nth-child(2) > span'):
                print("Wrong password - please try again")
                driver.close()
                break
            else:
                print("Password accepted")
                break
                
        sleep(3)
        while True:
            if check_exists_by_xpath('//*[@id="passwordNext"]/div/button/span'):
                driver.find_element("xpath", '//*[@id="passwordNext"]/div/button/span').click()
                print("Next button clicked")
                break
            else:
                print("Next button not found")
                continue
        sleep(2)
        
    except NoSuchElementException as e:
        print("Login failed")
        print(e)
        await sys.exit(2)
    print('\n')
    sleep(3)
    #Start Training Select 15 minutes and Proceed
    #check for the "confirm its you message" from google
    
    while True:
        if check_exists_by_css('#view_container > div > div > div.pwWryf.bxPAYd > div > div.WEQkZc > div > form > span > section > div > div > span > figure > samp'):
            number = driver.find_element(By.CSS_SELECTOR, '#view_container > div > div > div.pwWryf.bxPAYd > div > div.WEQkZc > div > form > span > section > div > div > span > figure > samp').text
            print("verification required")
            print(number)
            print(f"Please confirm you are trying to login by clicking {number} on your phone")
            sleep(3)
            continue
        else:
            print("No Verification Required")
            break
            
    while True:
        if check_exists_by_css("#dashboard-alerts-title"):
            print("Alert Detected")
            print("Alert detected on your membean dashboard, it is most likely that there is a quiz available")
            #click the X button #dashboard-alerts-close
            
            if quiz == "True":
                alert_button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="dashboard-alerts-container"]/ul/li/a'))
                )
                href = alert_button.get_attribute('href')
                print(f"URL: {href}")

                # Extract the ID from the href
                quiz_id = re.findall(r'\d+', href)[0] # extracts digits from the string

                print(f"Quiz ID: {quiz_id}")
                # Set your OpenAI API key
                client = OpenAI(api_key=openai_key)

                # URL of the webpage
                url = href

                # Create a new instance of the Chrome driver

                # Go to the webpage
                driver.get(url)

                # Get the HTML of the page
                html_doc = driver.page_source

                # Parse the HTML
                soup = BeautifulSoup(html_doc, 'html.parser')

                # Find all questions
                questions = soup.find_all(class_="question")

                for question in questions:
                    question_id = question['data-id']
                    question_text = question.find('p').text
                    answers = question.find_all('label')

                    # Prepare the answer choices to be sent to the AI
                    choices_text = " ".join([answer.text.strip() for answer in answers])

                    print(f"\nQuestion: {question_text}")
                    print(f"Choices: {choices_text}")

                    # Check if the question asks for both examples and the meaning
                    if "example of" in question_text and "meaning of" in question_text:
                        # Split the question into two parts
                        example_question = question_text.replace("give either an example of or the meaning of", "show examples of")
                        meaning_question = question_text.replace("give either an example of or the meaning of", "show the meaning of")

                        # Use the OpenAI API to get an answer to the example question
                        while True:
                            try:
                                response_example = client.chat.completions.create(
                                    model="gpt-3.5-turbo-1106",
                                    messages=[
                                        {"role": "system", "content": "You are a helpful assistant."},
                                        {"role": "user", "content": f"please analyze the following question and provide an answer(s) based on the choices, only respond with the answer(s), you must supply at least one answer {example_question} choices: {choices_text}"},
                                    ]
                                )
                                break
                            except OpenAIError as e:
                                if e.http_status == 429:
                                    print("Rate limit reached, sleeping for a while...")
                                    time.sleep(retry_delay)
                                else:
                                    raise e

                        answer_text_example = response_example.choices[0].message.content
                        print(f"AI response (example): {answer_text_example}")

                        # Use the OpenAI API to get an answer to the meaning question
                        while True:
                            try:
                                response_meaning = client.chat.completions.create(
                                    model="gpt-3.5-turbo-1106",
                                    messages=[
                                        {"role": "system", "content": "You are a helpful assistant."},
                                        {"role": "user", "content": f"please analyze the following question and provide an answer(s) based on the choices, only respond with the answer(s), you must supply at least one answer {meaning_question} choices: {choices_text}"},
                                    ]
                                )
                                break
                            except OpenAIError as e:
                                if e.http_status == 429:
                                    print("Rate limit reached, sleeping for a while...")
                                    time.sleep(retry_delay)
                                else:
                                    raise e

                        answer_text_meaning = response_meaning.choices[0].message.content
                        print(f"AI response (meaning): {answer_text_meaning}")

                        answer_text = answer_text_example + " " + answer_text_meaning
                    else:
                        while True:
                            try:
                                response = client.chat.completions.create(
                                    model="gpt-3.5-turbo-1106",
                                    messages=[
                                        {"role": "system", "content": "You are a helpful assistant."},
                                        {"role": "user", "content": f"please analyze the following question and provide an answer(s) based on the choices, only respond with the answer(s), you must supply at least one answer {question_text} choices: {choices_text}"},
                                    ]
                                )
                                break
                            except OpenAIError as e:
                                if e.http_status == 429:
                                    print("Rate limit reached, sleeping for a while...")
                                    time.sleep(retry_delay)
                                else:
                                    raise e

                        answer_text = response.choices[0].message.content
                        print(f"AI response: {answer_text}")

                    # Find the answer(s) that match the one(s) from the API
                    for answer in answers:
                        choice_text = answer.text.strip().lower()
                        # Remove extra characters from the AI response and convert to lowercase
                        cleaned_answer_text = answer_text.lstrip("-").strip().lower()
                        if choice_text in cleaned_answer_text:
                            print(f"Correct answer: {choice_text}")
                            # Find the corresponding input element in the actual webpage and click it
                            input_element = driver.find_element(By.CSS_SELECTOR, f"input[name='answer-{question_id}'][value='{answer.find('input')['value']}']")
                            input_element.click()
                            print(f"Clicked: {input_element.get_attribute('value')}")
                            
                            # Submit the form
                            submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                            submit_button.click()

                            print("Quiz Completed")
                            driver.close()
            else:
                print("Quiz Not Enabled Clicking the X")
                XButton = driver.find_element("css", '#dashboard-alerts-close')
                driver.execute_script("arguments[0].click();", XButton)
                print("Clicked the X button")
                break
        else:
            if quiz == "True":
                print("No Quiz Found")
                break
            print("No Alert Found")
            break
    randomNum = random.randint(5, 25)
    print("sleeping for " + str(randomNum) + " seconds")
    sleep(randomNum)
    while True:
        if check_exists_by_xpath('//*[@id="startTrainingBtn"]'):
            driver.find_element("xpath", '//*[@id="startTrainingBtn"]').click()
            print("start training clicked")
            print(f"Login Successful for {email}")
            break
        else:
            print("start training not found or verification failed")
            continue
    print('\n')
    print("logged in")
    print("Training Session Started")
    randomNum = random.randint(5, 25)
    print("sleeping for " + str(randomNum) + " seconds")
    sleep(randomNum)
    while True:
        if check_exists_by_xpath('//*[@id="15_min_"]'):
            driver.find_element("xpath", '//*[@id="15_min_"]').click()
            randomNum = random.randint(5, 25)
            print("sleeping for " + str(randomNum) + " seconds")
            sleep(randomNum)
            print("session started")
            print(f"Session started for {email}")
            break
        else:
            print("session not started")
            continue
    def run():
        i = 0
        while i < 25:
            i = i + 1
            print("Answering Question " + str(i))
            # Define wrong answer intervals for each grade
            grade_intervals = {
                "B-": {5, 10, 15, 20, 25},
                "B": {5, 10, 15, 20},
                "B+": {5, 10, 15},
                "A-": {5, 10},
                "A": {5},
                "A+": set()
            }
            
            def handle_question(question_type, selector, mark_wrong=False):
                if check_exists_by_css(selector):
                    randomNum = random.randint(5, 25)
                    print(f"sleeping for {randomNum} seconds")
                    sleep(randomNum)
                    
                    event_type = "fail" if mark_wrong else "pass"
                    passEvent = driver.find_element("xpath", f'//*[@id="{event_type}__event"]')
                    driver.execute_script("arguments[0].click();", passEvent)
                    print(f"Question type: {question_type} - Marked {'Wrong' if mark_wrong else 'Correct'}")
                    return True
                return False
            
            # Check if current question should be marked wrong based on grade
            mark_wrong = i in grade_intervals.get(grade, set())
            if mark_wrong:
                print(f"on question {i} checking")
            
            # Handle all question types
            if not handle_question("Single", '#single-question > h3', mark_wrong):
                if not handle_question("Single", '#single-question > p', mark_wrong):
                    if not handle_question("Word Fill", '#word-hint', mark_wrong):
                        if check_exists_by_css('#add-note'):
                            wordform = driver.find_element(By.CSS_SELECTOR, '#wordform-container > h1').text
                            print(f"Word: {wordform}")
                            sleep(2)
                            
                            if check_exists_by_css('#choice-section > li.choice.answer'):
                                selector = '#choice-section > li.choice' if mark_wrong else '#choice-section > li.choice.answer'
                                driver.find_element(By.CSS_SELECTOR, selector).click()
                                print(f"Question type: Wordpage Question - Marked {'Wrong' if mark_wrong else 'Correct'}")
                                randomNum = random.randint(5, 25)
                                print(f"sleeping for {randomNum} seconds")
                                sleep(randomNum)
                            
                            if check_exists_by_xpath('//*[@id="next-btn"]'):
                                driver.find_element("xpath", '//*[@id="next-btn"]').click()
                                randomNum = random.randint(5, 25)
                                print(f"sleeping for {randomNum} seconds")
                                sleep(randomNum)
                        else:
                            if not handle_question("Spelling", '#wordspell-wrapper', mark_wrong):
                                if check_exists_by_xpath('//*[@id="interstitial"]/img'):
                                    randomNum = random.randint(5, 25)
                                    print(f"sleeping for {randomNum} seconds")
                                    sleep(randomNum)
                                    
                                    if check_exists_by_xpath('//*[@id="Click_me_to_stop"]'):
                                        driver.find_element("xpath", '//*[@id="Click_me_to_stop"]').click()
                                        sleep(2)
                                        print("Session Ended")
                                        print(f"Session Ended - Thank you for using AutoMembean {email}")
                                        sleep(2)
                                        print('\n')
                                        driver.close()
                                        break
                                    
                                    if check_exists_by_xpath('//*[@id="Let_rsquo_s_continue"]'):
                                        driver.find_element("xpath", '//*[@id="Let_rsquo_s_continue"]').click()
                                    
                                    if check_exists_by_xpath('//*[@id="Onward"]'):
                                        driver.find_element("xpath", '//*[@id="Onward"]').click()
                                        print("Level Passed")
                                        print('\n')
                                        print(f"Level Passed - {email} passed to the next level")
                                        sleep(3)
                                    sleep(2)
            else:
                # Handle correct answers for non-marked questions
                if check_exists_by_css('#single-question > h3') or check_exists_by_css('#single-question > p'):
                    passEvent = driver.find_element("xpath", '//*[@id="pass__event"]')
                    driver.execute_script("arguments[0].click();", passEvent)
                    print("Question type: Single - Marked Correct")
                    randomNum = random.randint(5, 25)
                    print(f"sleeping for {randomNum} seconds")
                    sleep(randomNum)
                
                elif check_exists_by_css('#word-hint'):
                    passEvent = driver.find_element("xpath", '//*[@id="pass__event"]')
                    driver.execute_script("arguments[0].click();", passEvent)
                    print("Question type: Word Fill - Marked Correct")
                    randomNum = random.randint(5, 25)
                    print(f"sleeping for {randomNum} seconds")
                    sleep(randomNum)
                
                elif check_exists_by_css('#add-note'):
                    wordform = driver.find_element(By.CSS_SELECTOR, '#wordform-container > h1').text
                    print(f"Word: {wordform}")
                    sleep(2)
                    
                    if check_exists_by_css('#choice-section > li.choice.answer'):
                        driver.find_element(By.CSS_SELECTOR, '#choice-section > li.choice.answer').click()
                        print("Question type: Wordpage Question - Marked Correct")
                        randomNum = random.randint(5, 25)
                        print(f"sleeping for {randomNum} seconds")
                        sleep(randomNum)
                    
                    if check_exists_by_xpath('//*[@id="next-btn"]'):
                        driver.find_element("xpath", '//*[@id="next-btn"]').click()
                        randomNum = random.randint(5, 25)
                        print(f"sleeping for {randomNum} seconds")
                        sleep(randomNum)
                
                elif check_exists_by_xpath('//*[@id="wordspell-wrapper"]'):
                    passEvent = driver.find_element("xpath", '//*[@id="pass__event"]')
                    driver.execute_script("arguments[0].click();", passEvent)
                    print("Question type: Spelling - Marked Correct")
                    randomNum = random.randint(5, 25)
                    print(f"sleeping for {randomNum} seconds")
                    sleep(randomNum)
                
                elif check_exists_by_xpath('//*[@id="interstitial"]/img'):
                    randomNum = random.randint(5, 25)
                    print(f"sleeping for {randomNum} seconds")
                    sleep(randomNum)
                    
                    if check_exists_by_xpath('//*[@id="Click_me_to_stop"]'):
                        driver.find_element("xpath", '//*[@id="Click_me_to_stop"]').click()
                        sleep(2)
                        print("Session Ended")
                        print(f"Session Ended - Thank you for using AutoMembean {email}")
                        sleep(2)
                        print('\n')
                        driver.close()
                        break
                    
                    if check_exists_by_xpath('//*[@id="Let_rsquo_s_continue"]'):
                        driver.find_element("xpath", '//*[@id="Let_rsquo_s_continue"]').click()
                    
                    if check_exists_by_xpath('//*[@id="Onward"]'):
                        driver.find_element("xpath", '//*[@id="Onward"]').click()
                        print("Level Passed")
                        print('\n')
                        print(f"Level Passed - {email} passed to the next level")
                        sleep(3)
                    sleep(2)
    
    run()

if __name__ == "__main__":
    asyncio.run(membean(sys.argv[1:]))
