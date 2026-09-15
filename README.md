# Jarvis: Autonomous AI Assistant

An advanced, fully autonomous AI assistant powered by a cutting-edge dual-model architecture: **GPT-Live-1** for real-time voice sessions and **GPT-4o** for delegated complex reasoning and computer use tools. Jarvis can see your screen, hear your voice, and seamlessly control your computer by autonomously identifying and interacting with UI elements in real-time.

## Features

- **Dual-Model Architecture**: Uses `gpt-live-1` for the core ultra-low latency WebSocket session, while seamlessly delegating complex tool calls and reasoning (like computer use) to the heavyweight `gpt-4o` model.
- **Continuous Voice Interaction**: Speaks and listens concurrently using the OpenAI Realtime API.
- **Autonomous Computer Use**: Features a custom "Macro Engine" that uses fuzzy-matching to instantly locate and interact with any UI button, text field, or element on your screen.
- **Limitless Vision**: Sees exactly what you see and parses screen contents seamlessly, allowing it to navigate websites, click buttons, and type text without explicit coordinates.
- **Local Wake-Word Detection**: Runs entirely in the background and activates instantly when it hears its name using the lightweight Vosk STT engine.

## Prerequisites

- Python 3.10+
- An [OpenAI API Key](https://platform.openai.com/api-keys) with access to the `gpt-live-1` and `gpt-4o` models.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AstraStasis/Jarvisaya.git
   cd Jarvisaya
   ```

2. **Create a virtual environment (Recommended):**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *Note: The required local voice-recognition model (Vosk) will be automatically downloaded and extracted the first time you run the script.*

## Configuration

1. Copy the `.env.example` file and rename it to `.env`:
   ```bash
   copy .env.example .env
   ```

2. Open `.env` in a text editor and add your OpenAI API key:
   ```env
   OPENAI_API_KEY=sk-your-openai-api-key-here
   ```

## Usage

Start the assistant by running:

```bash
python main.py
```

The system will start up, establish a secure WebSocket connection to the AI, and begin listening in the background. Simply speak out loud (e.g., "Jarvis, open Google Chrome and search for the weather") and the AI will take over your mouse and keyboard to complete the task!

> [!WARNING]
> This AI is granted full autonomous control over your mouse and keyboard. Please supervise it while it is operating to prevent unintended actions on sensitive files or applications.
