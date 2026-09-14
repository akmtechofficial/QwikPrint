import sys

class AudioService:
    def __init__(self):
        pass

    def play_cash_chime(self):
        """Plays cash approval sound notification."""
        try:
            if sys.platform == "win32":
                import winsound
                # Play notification sound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
                winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
            else:
                print('\a') # Terminal bell fallback
        except Exception as e:
            print(f"[Audio Error] {e}")

audio_service = AudioService()
