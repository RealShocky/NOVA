# NOVA - Natural Oral Virtual Assistant

NOVA is an advanced voice assistant application that leverages speech recognition, text-to-speech, and OpenAI's GPT-4 model to execute various commands, open applications, and perform web searches.

## Features

- Continuous voice recognition and command execution.
- Text-to-speech feedback.
- Integration with OpenAI's GPT-4 for natural language understanding.
- Ability to open and close applications.
- Perform web searches using Brave browser.
- Personal log creation with speech-to-text.

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Front-End](#front-end)
- [Back-End](#back-end)
- [License](#license)

## Installation

### Requirements

- Python 3.7 or higher
- pip (Python package installer)
- Brave browser (for web search functionality)

### Steps

1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/nova.git
    cd nova
    ```

2. Create a virtual environment and activate it:
    ```bash
    python -m venv venv
    source venv/bin/activate   # On Windows use `venv\Scripts\activate`
    ```

3. Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

4. Set up the OpenAI API key:
    - Create a `config.json` file in the project root directory with the following content:
      ```json
      {
        "openai_api_key": "your_openai_api_key",
        "voice_id": "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices\\Tokens\\TTS_MS_EN-US_DAVID_11.0",
        "program_mapping": {
          "notepad": "notepad.exe",
          "brave browser": "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
          "visual studio code": "C:\\path\\to\\your\\vscode.exe"
        }
      }
      ```

## Configuration

- `openai_api_key`: Your OpenAI API key.
- `voice_id`: The ID of the voice you want to use for text-to-speech.
- `program_mapping`: A dictionary mapping program names to their executable paths.

## Usage

1. Run the `nova-frontend.py` script to start the front-end server:
    ```bash
    python nova-frontend.py
    ```

2. Open a web browser and go to `http://127.0.0.1:8000`.

3. Run the `nova.py` script to start the voice assistant:
    ```bash
    python nova.py
    ```

4. Speak commands like "open notepad," "current time," or "search brave browser GPTS" to interact with the assistant.

## Front-End

The front-end is a simple Flask application that serves the HTML pages and provides a basic interface for user interactions.

### Files

- `templates/`: Contains HTML templates for various pages.
- `static/`: Contains static files like CSS and JavaScript.
- `nova-frontend.py`: The main Flask application script.

### HTML Pages

- `index.html`: The main dashboard page.
- `login.html`: The login page.
- `register.html`: The registration page.
- `activate.html`: The account activation page.
- `reset_request.html`: The password reset request page.
- `reset_token.html`: The password reset page.
- `edit_program.html`: The page for editing program mappings.

## Back-End

The back-end consists of the main `nova.py` script that handles voice recognition, text-to-speech, and command execution.

### Files

- `nova.py`: The main script for the voice assistant functionality.
- `config.json`: The configuration file for API keys and program mappings.

### Functions

- `recognize_speech()`: Recognizes speech input from the microphone.
- `speak(text)`: Converts text to speech.
- `parse_command(command)`: Parses the recognized command using OpenAI's GPT-4.
- `execute_action(action)`: Executes the parsed action.
- `open_program(program)`: Opens the specified program.
- `close_program(program)`: Closes the specified program.
- `search_in_brave(query)`: Performs a web search using Brave browser.
- `speak_current_time()`: Speaks the current time.
- `save_log_to_file(log_entry)`: Saves a personal log to a file.
- `start_personal_log()`: Starts a personal log entry.
- `continuous_listen()`: Continuously listens for voice commands.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
