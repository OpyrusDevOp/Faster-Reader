import edge_tts
import asyncio
import tempfile
import subprocess
import os
import re
from pathlib import Path

# Language default (environment variable)
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en-US")

# OpenAI voice names mapped to edge-tts equivalents
voice_mapping = {
    "alloy": "en-US-JennyNeural",
    "ash": "en-US-AndrewNeural",
    "ballad": "en-GB-ThomasNeural",
    "coral": "en-AU-NatashaNeural",
    "echo": "en-US-GuyNeural",
    "fable": "en-GB-SoniaNeural",
    "nova": "en-US-AriaNeural",
    "onyx": "en-US-EricNeural",
    "sage": "en-US-JennyNeural",
    "shimmer": "en-US-EmmaNeural",
    "verse": "en-US-BrianNeural",
}

model_data = [
    {"id": "tts-1", "name": "Text-to-speech v1"},
    {"id": "tts-1-hd", "name": "Text-to-speech v1 HD"},
    {"id": "gpt-4o-mini-tts", "name": "GPT-4o mini TTS"},
]


def is_ffmpeg_installed():
    """Check if FFmpeg is installed and accessible."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_audio_duration(file_path):
    """
    Get the duration of an audio file in seconds using ffmpeg/ffprobe.
    Returns float duration in seconds, or 0.0 if failed.
    """
    try:
        # Use ffmpeg -i to get duration from stderr
        result = subprocess.run(
            ["ffmpeg", "-i", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Look for "Duration: 00:00:05.12,"
        match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d+)", result.stderr)
        if match:
            hours, minutes, seconds = map(float, match.groups())
            return hours * 3600 + minutes * 60 + seconds
    except Exception as e:
        print(f"Error getting duration: {e}")
    return 0.0


async def _generate_audio_with_subs(text, voice, speed):
    """
    Generate TTS audio and collect subtitles (WordBoundaries).
    Returns (audio_data_bytes, subtitle_list)
    """
    edge_tts_voice = voice_mapping.get(voice, voice)

    try:
        speed_rate = speed_to_rate(speed)
    except Exception:
        speed_rate = "+0%"

    communicator = edge_tts.Communicate(
        text=text, voice=edge_tts_voice, rate=speed_rate
    )

    audio_data = bytearray()
    subtitles = []

    # Process the stream
    async for chunk in communicator.stream():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            # chunk content: {'offset': 12345, 'duration': 123, 'text': 'word', ...}
            # offset is in 100ns units (ticks). 1ms = 10,000 ticks.
            subtitles.append(
                {
                    "start": chunk["offset"] / 10000000,  # Convert to seconds
                    "duration": chunk["duration"] / 10000000,
                    "text": chunk["text"],
                    "text_offset": chunk["text_offset"],  # char index in input text
                    "word_len": chunk["word_length"],
                }
            )

    return audio_data, subtitles


async def _generate_audio_file(text, voice, response_format, speed):
    """
    Generate TTS audio to a file and return path + subtitles.
    """
    audio_data, subtitles = await _generate_audio_with_subs(text, voice, speed)

    # 1. Save raw audio (mp3 usually)
    temp_mp3_obj = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_mp3_path = temp_mp3_obj.name
    temp_mp3_obj.write(audio_data)
    temp_mp3_obj.close()

    # If requested format is mp3, we are done
    if response_format == "mp3":
        return temp_mp3_path, subtitles

    # Conversion logic if ffmpeg is available
    if not is_ffmpeg_installed():
        return temp_mp3_path, subtitles

    converted_obj = tempfile.NamedTemporaryFile(
        delete=False, suffix=f".{response_format}"
    )
    converted_path = converted_obj.name
    converted_obj.close()

    cmd = ["ffmpeg", "-y", "-i", temp_mp3_path, converted_path]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        Path(temp_mp3_path).unlink(missing_ok=True)
        return converted_path, subtitles
    except Exception:
        Path(converted_path).unlink(missing_ok=True)
        return temp_mp3_path, subtitles  # Fallback to mp3


def generate_speech(text, voice, response_format, speed=1.0):
    """Wrapper to run async generator."""
    return asyncio.run(_generate_audio_file(text, voice, response_format, speed))


def merge_audio_files(file_paths, output_path=None):
    """
    Merges audio files using FFmpeg (concat demuxer).
    """
    if not file_paths:
        return None

    if not output_path:
        ext = Path(file_paths[0]).suffix
        out_obj = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        output_path = out_obj.name
        out_obj.close()

    if is_ffmpeg_installed():
        list_file = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".txt")
        try:
            for path in file_paths:
                safe_path = str(Path(path).absolute()).replace("\\", "/")
                list_file.write(f"file '{safe_path}'\n")
            list_file.close()

            cmd = [
                "ffmpeg",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file.name,
                "-c",
                "copy",
                "-y",
                output_path,
            ]
            subprocess.run(
                cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
        except Exception as e:
            print(f"Merge error: {e}")
            _binary_append(file_paths, output_path)
        finally:
            if os.path.exists(list_file.name):
                os.remove(list_file.name)
    else:
        _binary_append(file_paths, output_path)

    return output_path


def _binary_append(file_paths, output_path):
    with open(output_path, "wb") as outfile:
        for fpath in file_paths:
            with open(fpath, "rb") as infile:
                outfile.write(infile.read())


def get_voices(language=None):
    return asyncio.run(_get_voices(language))


async def _get_voices(languages=None):
    all_voices = await edge_tts.list_voices()
    
    if languages is None:
        languages = [DEFAULT_LANGUAGE]
    elif isinstance(languages, str):
        if languages == "all":
            languages = None
        else:
            languages = [languages]

    filtered_voices = [
        {"name": v["ShortName"], "gender": v["Gender"], "language": v["Locale"]}
        for v in all_voices
        if languages is None or any(v["Locale"].startswith(lang) for lang in languages)
    ]
    return filtered_voices


def speed_to_rate(speed: float) -> str:
    if speed < 0 or speed > 2:
        raise ValueError("Speed must be between 0 and 2 (inclusive).")
    percentage_change = (speed - 1) * 100
    return f"{percentage_change:+.0f}%"
