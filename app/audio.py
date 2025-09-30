from pathlib import Path

try:
    import playsound as _playsound
except Exception:
    _playsound = None

SOUND_PATH = Path(__file__).parent / "assets" / "success.mp3"

def play_success():
    if _playsound is None:
        return
    try:
        _playsound.playsound(str(SOUND_PATH))
    except Exception as e:
        print(f"Audio error: {e}")
