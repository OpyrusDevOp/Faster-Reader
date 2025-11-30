from PySide6.QtCore import QThread, Signal
from deep_translator import GoogleTranslator, DeeplTranslator

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

            if self.provider == "deepl":
                if not self.api_key:
                    raise ValueError("DeepL API key is required.")
                translator = DeeplTranslator(api_key=self.api_key, target=self.target_lang, use_free_api=True)
                # DeepL might require 'en-US' instead of 'en', etc.
                # deep-translator handles some of this, but we should be careful.
                # For now, we trust the user/library.
                translated = translator.translate(self.text)
            else:
                # Google
                translator = GoogleTranslator(source='auto', target=self.target_lang)
                translated = translator.translate(self.text)

            self.finished.emit(translated)

        except Exception as e:
            self.error.emit(str(e))
