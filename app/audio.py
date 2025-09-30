from pathlib import Path
import playsound

SOUND_PATH = "/Users/yashshahani/Desktop/VSCode/job-tracker/app/assets/success.mp3"

def play_success():
    try:
        playsound.playsound(SOUND_PATH)
    except Exception as e:
        print(f"Audio error: {e}")
