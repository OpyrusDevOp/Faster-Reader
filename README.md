# Faster Reader

**Faster Reader** is a desktop application that converts Markdown text to speech using high-quality Edge TTS voices, with a karaoke-style synchronized text display.

## Features

-   **Text-to-Speech**: High-quality neural voices from Microsoft Edge TTS.
-   **Markdown Support**: Intelligently handles Markdown formatting (headers, lists, etc.) for better reading flow.
-   **Karaoke Sync**: Highlights the text word-by-word as it is being read.
-   **MP3 Export**: Save the generated audio to an MP3 file.
-   **Customization**: Adjustable reading speed and voice selection.

## Installation

1.  **Clone the repository** (if applicable) or download the source code.
2.  **Install Python 3.10+**.
3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Install FFmpeg**:
    -   **Linux**: `sudo apt install ffmpeg`
    -   **Windows/Mac**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and ensure it's in your system PATH.

## Usage

1.  Run the application:
    ```bash
    python app.py
    ```
2.  **Load Markdown**: Click "Load Markdown" to open a `.md` or `.txt` file, or paste text directly into the left editor.
3.  **Select Voice**: Choose a voice from the dropdown menu.
4.  **Generate**: Click "Generate & Read". The application will process the text and start playing the audio.
5.  **Playback**: Use the play/pause button and slider to control playback. The text on the right will highlight in sync with the audio.
6.  **Save**: Click "Save MP3" to export the generated audio.

## Building from Source

To create a standalone executable:

1.  Ensure `pyinstaller` is installed (included in `requirements.txt`).
2.  Run the build script:
    ```bash
    python build.py
    ```
3.  The executable will be created in the `dist/` directory.
