import tts_handler
import asyncio

def verify():
    print("Fetching voices for ['en', 'fr']...")
    voices = tts_handler.get_voices(language=["en", "fr"])
    
    en_count = 0
    fr_count = 0
    other_count = 0
    
    for v in voices:
        lang = v['language']
        if lang.startswith('en'):
            en_count += 1
        elif lang.startswith('fr'):
            fr_count += 1
        else:
            other_count += 1
            print(f"Unexpected language: {lang}")

    print(f"English voices: {en_count}")
    print(f"French voices: {fr_count}")
    print(f"Other voices: {other_count}")

    if en_count > 0 and fr_count > 0 and other_count == 0:
        print("SUCCESS: Found both English and French voices, and no others.")
    else:
        print("FAILURE: Voice filtering incorrect.")

if __name__ == "__main__":
    verify()
