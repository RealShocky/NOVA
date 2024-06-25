import json
import speech_recognition as sr
import subprocess
import pyttsx3
import os
import openai
import pyautogui
import time
from datetime import datetime, timedelta
import logging
import threading
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Setup logging
logging.basicConfig(level=logging.DEBUG, filename='logs/Nova.log', filemode='a',
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
with open('config.json') as config_file:
    config = json.load(config_file)

# Initialize pyttsx3 engine
engine = pyttsx3.init()
engine_lock = threading.Lock()

# Set OpenAI API key
openai.api_key = config["openai_api_key"]

# Initialize Google Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar']
SERVICE_ACCOUNT_FILE = 'service_account.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
calendar_service = build('calendar', 'v3', credentials=credentials)

# Initialize voice profiles
voice_profiles = {}

class ContextManager:
    def __init__(self):
        self.context = {}

    def update_context(self, user_id, context):
        self.context[user_id] = context

    def get_context(self, user_id):
        return self.context.get(user_id, {})

context_manager = ContextManager()

def list_voices():
    voices = engine.getProperty('voices')
    for voice in voices:
        logging.info(f"ID: {voice.id}, Name: {voice.name}, Languages: {voice.languages}, Gender: {voice.gender}")
        print(f"ID: {voice.id}\nName: {voice.name}\nLanguages: {voice.languages}\nGender: {voice.gender}\n")

def set_voice(voice_id):
    engine.setProperty('voice', voice_id)

def speak(text):
    def run():
        with engine_lock:
            try:
                logging.debug(f"Speaking: {text}")
                engine.say(text)
                engine.runAndWait()
                logging.debug(f"Finished speaking: {text}")
            except Exception as e:
                logging.error(f"Error in speak: {e}")
    threading.Thread(target=run).start()

def recognize_speech():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    with mic as source:
        logging.info("Listening for speech input")
        print("Listening...")
        audio = recognizer.listen(source)
    
    try:
        command = recognizer.recognize_google(audio)
        logging.info(f"Recognized speech: {command}")
        print(f"You said: {command}")
        return command
    except sr.UnknownValueError:
        logging.warning("Could not understand the audio")
        print("Could not understand the audio")
        speak("I didn't catch that. Could you please repeat?")
        return None
    except sr.RequestError as e:
        logging.error(f"Google Speech Recognition service error: {e}")
        print(f"Could not request results from Google Speech Recognition service: {e}.")
        speak("There was an error with the Google Speech Recognition service.")
        return None
    except Exception as e:
        logging.error(f"Unexpected error in recognize_speech: {e}")
        speak("An unexpected error occurred.")
        return None

def parse_command(user_id, command):
    try:
        context = context_manager.get_context(user_id)
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a voice assistant. Respond with the specific action text only."},
                {"role": "user", "content": f"Command: {command}\nContext: {context}"}
            ]
        )
        action = response.choices[0].message['content'].strip()
        logging.info(f"Parsed command: {action}")
        return action
    except Exception as e:
        logging.error(f"Error parsing command: {e}")
        print(f"Error parsing command: {e}")
        speak("Error parsing command.")
        return None

def execute_action(user_id, action):
    if action.startswith("open "):
        program = action.replace("open ", "").strip()
        open_program(program)
    elif action.startswith("close "):
        program = action.replace("close ", "").strip()
        close_program(program)
    elif "current time" in action:
        speak_current_time()
    elif "search " in action:
        query = action.replace("search ", "").strip()
        search_in_brave(query)
    elif "start personal log" in action:
        start_personal_log(user_id)
    elif "set reminder" in action:
        reminder_details = action.replace("set reminder ", "").strip()
        set_reminder(reminder_details)
    elif "stop listening" in action:
        speak("Goodbye!")
        exit()
    else:
        speak("Command not recognized. Please try again.")

def open_program(program):
    program_mapping = config["program_mapping"]

    if program:
        executable = program_mapping.get(program)
        if not executable:
            logging.warning(f"Program '{program}' not recognized.")
            print(f"Program '{program}' not recognized.")
            speak(f"Program '{program}' not recognized.")
            return
        
        try:
            if os.name == 'nt':  # For Windows
                subprocess.run([executable], shell=True)
            elif os.name == 'posix':  # For MacOS/Linux
                subprocess.run(["open", "-a", executable])
            else:
                logging.error("Unsupported operating system")
                print("Unsupported OS")
                speak("Unsupported operating system")
                return
            logging.info(f"Opening {program}")
            print(f"Opening {program}")
            speak(f"Opening {program}")
        except Exception as e:
            logging.error(f"Could not open {program}: {e}")
            print(f"Could not open {program}: {e}")
            speak(f"Could not open {program}")
    else:
        logging.warning("No program specified")
        print("No program specified")
        speak("No program specified")

def close_program(program):
    program_mapping = config["program_mapping"]

    executable = program_mapping.get(program)
    if not executable:
        logging.warning(f"Program '{program}' not recognized for closing.")
        print(f"Program '{program}' not recognized for closing.")
        speak(f"Program '{program}' not recognized for closing.")
        return
    
    try:
        if os.name == 'nt':  # For Windows
            subprocess.run(["taskkill", "/f", "/im", executable], shell=True)
        else:
            logging.error(f"Closing {program} is only supported on Windows")
            print(f"Closing {program} is only supported on Windows")
            speak(f"Closing {program} is only supported on Windows")
    except Exception as e:
        logging.error(f"Could not close {program}: {e}")
        print(f"Could not close {program}: {e}")
        speak(f"Could not close {program}")

def generate_code_description(prompt, platform):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an advanced programming bot. Provide detailed code for the given prompt."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150
        )
        description = response.choices[0].message['content'].strip()
        logging.info(f"Generated code description: {description}")
        print(description)

        if platform.lower() == "notepad":
            close_program("notepad")
            time.sleep(1)
            subprocess.run(["notepad.exe"])
            time.sleep(2)
            pyautogui.typewrite(description, interval=0)
        
        elif platform.lower() == "visual studio code":
            close_program("visual studio code")
            time.sleep(1)
            subprocess.run([config["program_mapping"]["visual studio code"]])
            time.sleep(5)
            pyautogui.hotkey('win', 'down')
            time.sleep(1)
            pyautogui.hotkey('win', 'up')
            time.sleep(1)
            pyautogui.typewrite(description, interval=0)
        
        speak("Here is the code you requested.")
    except Exception as e:
        logging.error(f"Error generating code description: {e}")
        print(f"Error generating code description: {e}")
        speak(f"Error generating code description")

def search_in_brave(query):
    brave_path = config["program_mapping"]["brave browser"]
    try:
        logging.info(f"Opening Brave browser for search: {query}")
        subprocess.run([brave_path], shell=True)
        time.sleep(5)
        pyautogui.typewrite(query)
        pyautogui.press('enter')
        logging.info(f"Searching for {query} in Brave browser")
        speak(f"Searching for {query} in Brave browser.")
    except Exception as e:
        logging.error(f"Could not search in Brave: {e}")
        print(f"Could not search in Brave: {e}")
        speak(f"Could not search in Brave browser")

def speak_current_time():
    current_time = datetime.now().strftime("%H:%M:%S")
    logging.info(f"Current time is {current_time}")
    print(f"Current time is {current_time}")
    speak(f"The current time is {current_time}")

def save_log_to_file(log_entry):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"personal_log_{timestamp}.txt"
        with open(filename, "w") as file:
            file.write(log_entry)
        logging.info(f"Personal log saved as {filename}")
        print(f"Personal log saved as {filename}")
        speak(f"Personal log saved as {filename}")
    except Exception as e:
        logging.error(f"Could not save personal log: {e}")
        print(f"Could not save personal log: {e}")
        speak(f"Could not save personal log")

def start_personal_log(user_id):
    try:
        speak("Please dictate your personal log.")
        personal_log = recognize_speech()

        if personal_log:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Rewrite the following as a personal log entry similar to Star Trek logs:"},
                    {"role": "user", "content": personal_log}
                ],
                max_tokens=150
            )
            rewritten_log = response.choices[0].message['content'].strip()
            logging.info(f"Rewritten personal log: {rewritten_log}")
            print(rewritten_log)
            save_log_to_file(rewritten_log)
            context_manager.update_context(user_id, {"last_log": rewritten_log})
        
        speak("Personal log entry created.")
    except Exception as e:
        logging.error(f"Could not start personal log: {e}")
        print(f"Could not start personal log: {e}")
        speak(f"Could not start personal log")

def set_reminder(event_details):
    event = {
        'summary': event_details,
        'start': {
            'dateTime': datetime.now().isoformat(),
            'timeZone': 'America/Los_Angeles',
        },
        'end': {
            'dateTime': (datetime.now() + timedelta(hours=1)).isoformat(),
            'timeZone': 'America/Los_Angeles',
        },
    }

    try:
        event = calendar_service.events().insert(calendarId='primary', body=event).execute()
        logging.info(f"Reminder set: {event_details}")
        speak("Reminder has been set.")
    except Exception as e:
        logging.error(f"Error setting reminder: {e}")
        speak("Could not set the reminder.")

def continuous_listen():
    while True:
        try:
            command = recognize_speech()
            if command:
                user_id = "default_user"  # This should be dynamically set for multi-user environments
                action = parse_command(user_id, command)
                if action:
                    execute_action(user_id, action)
        except Exception as e:
            logging.error(f"Error in continuous listening loop: {e}")
            print(f"Error in continuous listening loop: {e}")
            speak("There was an error. Restarting listening.")

def main():
    speak("Hello, I am ready for your command")
    list_voices()
    set_voice(config["voice_id"])
    listener_thread = threading.Thread(target=continuous_listen)
    listener_thread.daemon = True
    listener_thread.start()

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Nova program terminated by user.")
        print("Nova program terminated by user.")
        speak("Goodbye!")

if __name__ == "__main__":
    main()
