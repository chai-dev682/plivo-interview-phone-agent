import json

# Load the configuration from a JSON file (API keys, settings, etc.)
def load_config(file_path='../plivo-ai-voice-agents/Deepgram-openai-elevenlabs/config.json'):
    global CONFIG
    with open(file_path, 'r') as f:
        CONFIG = json.load(f)
    return CONFIG

# Entry point for running the script
if __name__ == '__main__':
    load_config()
    print(CONFIG)
