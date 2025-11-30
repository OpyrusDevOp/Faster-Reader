from PySide6.QtCore import QThread, Signal
from deep_translator import GoogleTranslator, DeeplTranslator
import handle_text

class TranslationWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, text, target_lang, provider="google", api_key=None):
        super().__init__()
        self.text = text
        self.target_lang = target_lang
        self.provider = provider
        self.api_key = api_key

    def run(self):
        try:
            if not self.text:
                self.finished.emit("")
                return

            # Chunking to support long text and avoid API limits
            # Google Translate (free) often has limits around 5000 chars.
            # We use 2000 to be safe and responsive.
            chunks = handle_text.chunk_text(self.text, max_chars=2000)
            translated_chunks = []

            # Initialize translator once if possible
            if self.provider == "deepl":
                if not self.api_key:
                    raise ValueError("DeepL API key is required.")
                translator = DeeplTranslator(api_key=self.api_key, target=self.target_lang, use_free_api=True)
            else:
                # Google
                translator = GoogleTranslator(source='auto', target=self.target_lang)

            for chunk in chunks:
                if not chunk.strip():
                    translated_chunks.append("")
                    continue
                
                # Translate chunk
                res = translator.translate(chunk)
                translated_chunks.append(res)
            
            # Reassemble
            full_translation = "\n\n".join(translated_chunks)
            self.finished.emit(full_translation)

        except Exception as e:
            self.error.emit(str(e))
