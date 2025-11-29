# tts_worker.py

from PySide6.QtCore import QObject, QRunnable, Signal, Slot
from tts_handler import generate_speech
from handle_text import prepare_tts_input_with_context


class TtsSignals(QObject):
    """Signals available from the running worker thread."""

    finished = Signal(str)  # Emits the path to the generated audio file
    error = Signal(str)  # Emits a detailed error message


class TtsWorker(QRunnable):
    """Worker thread for generating speech to keep the GUI responsive."""

    def __init__(self, text, voice, response_format, speed, remove_filter):
        super().__init__()
        self.text = text
        self.voice = voice
        self.response_format = response_format
        self.speed = speed
        self.remove_filter = remove_filter
        self.signals = TtsSignals()

    @Slot()
    def run(self):
        """Your heavy TTS generation function is executed here."""
        try:
            # Apply your existing Markdown cleanup logic before TTS
            if not self.remove_filter:
                processed_text = prepare_tts_input_with_context(self.text)
            else:
                processed_text = self.text

            # Call the core TTS function from tts_handler.py
            output_file_path = generate_speech(
                processed_text, self.voice, self.response_format, self.speed
            )

            # Emit the finished signal with the output file path
            self.signals.finished.emit(output_file_path)

        except Exception as e:
            error_message = f"TTS generation failed: {str(e)}"
            self.signals.error.emit(error_message)
