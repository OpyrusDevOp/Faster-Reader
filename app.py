import sys
import os
import shutil

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QStyle
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont

import tts_handler
import handle_text
from translation_worker import TranslationWorker
from ui import MainWindowUI


class TTSWorker(QThread):
    finished = Signal(str, list, str)  # path, subtitles, full_clean_text
    progress = Signal(int)
    error = Signal(str)

    def __init__(self, text, voice, speed, output_path=None, parent=None):
        super().__init__(parent)
        self.text = text
        self.voice = voice
        self.speed = speed
        self.output_path = output_path

    def run(self):
        temp_files = []
        all_subtitles = []
        current_time_offset = 0.0
        try:
            # 1. Clean Text
            clean_text = handle_text.prepare_tts_input_with_context(self.text)
            if not clean_text:
                self.error.emit("Text is empty after processing.")
                return

            # 2. Chunking
            chunks = handle_text.chunk_text(clean_text, max_chars=2000)
            total_chunks = len(chunks)

            # We reconstruct the full text for the lyrics view to ensure it matches chunks perfectly
            full_clean_text_reconstructed = ""

            # 3. Process Chunks
            for i, chunk in enumerate(chunks):
                if self.isInterruptionRequested():
                    self.cleanup_temps(temp_files)
                    return

                # Generate audio & subs for this chunk
                audio_path, subtitles = tts_handler.generate_speech(
                    text=chunk,
                    voice=self.voice,
                    response_format="mp3",
                    speed=self.speed,
                )
                temp_files.append(audio_path)

                # Adjust timestamps for this chunk based on previous chunks
                chunk_len = len(full_clean_text_reconstructed)
                for sub in subtitles:
                    sub["start"] += current_time_offset
                    # Adjust text offset to match the full concatenated string
                    sub["text_offset"] += chunk_len
                    all_subtitles.append(sub)
                
                # print(f"DEBUG: Chunk {i} processed. Audio duration: {tts_handler.get_audio_duration(audio_path):.2f}s. Subtitles count: {len(subtitles)}")

                full_clean_text_reconstructed += chunk + "\n\n"  # Add separation back

                # Calculate duration of this chunk to update offset for next chunk
                duration = tts_handler.get_audio_duration(audio_path)
                # Fallback if ffmpeg duration fails: estimate from last subtitle
                if duration == 0 and subtitles:
                    last_sub = subtitles[-1]
                    duration = (
                        (last_sub["start"] - current_time_offset)
                        + last_sub["duration"]
                        + 0.5
                    )

                current_time_offset += duration

                prog = int(10 + ((i + 1) / total_chunks * 80))
                self.progress.emit(prog)

            # 4. Merge
            self.progress.emit(95)
            if self.output_path:
                final_path = self.output_path
            else:
                import tempfile

                # Create a temp file that persists
                f = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                final_path = f.name
                f.close()

            tts_handler.merge_audio_files(temp_files, final_path)
            self.cleanup_temps(temp_files)

            self.progress.emit(100)
            self.finished.emit(final_path, all_subtitles, full_clean_text_reconstructed)

        except Exception as e:
            self.cleanup_temps(temp_files)
            self.error.emit(str(e))

    def cleanup_temps(self, files):
        for f in files:
            try:
                os.remove(f)
            except Exception:
                pass


class MainWindow(MainWindowUI):
    def __init__(self):
        super().__init__()
        
        # -- Media Player --
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.playbackStateChanged.connect(self.on_state_changed)

        # -- UI Data --
        self.subtitles = []
        self.current_audio_path = None
        self.is_slider_dragged = False
        self.available_voices = []

        self.connect_signals()
        self.populate_voices()

    def connect_signals(self):
        # Top Bar
        self.btn_load.clicked.connect(self.load_file)
        
        # Reading Tab
        self.reading_tab.btn_send_to_trans.clicked.connect(self.send_reading_to_translation)
        
        # Translation Tab
        self.translation_tab.combo_provider.currentIndexChanged.connect(self.on_provider_changed)
        self.translation_tab.btn_translate.clicked.connect(self.start_translation)
        self.translation_tab.btn_transfer.clicked.connect(self.transfer_translation)
        self.translation_tab.btn_send_input_to_read.clicked.connect(self.send_trans_input_to_reading)
        
        # Player Controls
        self.btn_play.clicked.connect(self.toggle_playback)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderReleased.connect(self.on_slider_released)
        self.slider.valueChanged.connect(self.on_slider_moved)
        self.btn_generate.clicked.connect(self.start_generation)
        self.btn_save.clicked.connect(self.save_audio)

    # -- Logic --

    def populate_voices(self):
        # We assume tts_handler has a synchronous wrapper or we run in thread.
        # For simplicity in this snippet, let's use a thread like before.

        # Re-defining simple loader here for completeness
        class VLoader(QThread):
            loaded = Signal(list)

            def run(self):
                self.loaded.emit(tts_handler.get_voices(language="all"))

        self.vloader = VLoader()
        self.vloader.loaded.connect(self.on_voices_loaded)
        self.vloader.start()

    def on_voices_loaded(self, voices):
        self.available_voices = voices
        self.combo_voice.clear()
        mapped = tts_handler.voice_mapping.keys()
        for m in mapped:
            self.combo_voice.addItem(f"OpenAI: {m}", m)
        self.combo_voice.insertSeparator(self.combo_voice.count())
        for v in voices:
            self.combo_voice.addItem(f"{v['name']} ({v['language']})", v["name"])

    def start_generation(self):
        text = self.reading_tab.text_editor.toPlainText().strip()
        if not text:
            return

        # Stop existing
        self.player.stop()
        self.subtitles = []

        # UI Prep
        self.set_ui_generating(True)
        self.status_label.setText("Generating audio...")
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        voice = self.combo_voice.currentData()
        speed = self.spin_speed.value()

        self.worker = TTSWorker(text, voice, speed)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_generation_finished(self, path, subs, clean_text):
        self.set_ui_generating(False)
        self.progress_bar.hide()
        self.status_label.setText("Ready to play.")

        self.current_audio_path = path
        self.subtitles = subs

        # Setup Lyrics View
        self.reading_tab.lyrics_view.setPlainText(clean_text)

        # Setup Player
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def save_audio(self):
        if not self.current_audio_path or not os.path.exists(self.current_audio_path):
            QMessageBox.warning(self, "No Audio", "Please generate audio first.")
            return

        dest, _ = QFileDialog.getSaveFileName(
            self, "Save Audio", "output.mp3", "MP3 Files (*.mp3)"
        )
        if dest:
            shutil.copy2(self.current_audio_path, dest)
            QMessageBox.information(self, "Saved", f"File saved to {dest}")

    # -- Player Controls & Sync --

    def toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
            )
        else:
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )

    def on_duration_changed(self, duration):
        self.slider.setRange(0, duration)
        self.lbl_total_time.setText(self.format_time(duration))

    def on_position_changed(self, position):
        if not self.is_slider_dragged:
            self.slider.setValue(position)

        self.lbl_current_time.setText(self.format_time(position))
        self.sync_lyrics(position)

    def on_slider_pressed(self):
        self.is_slider_dragged = True

    def on_slider_released(self):
        self.is_slider_dragged = False
        self.player.setPosition(self.slider.value())

    def on_slider_moved(self, value):
        if self.is_slider_dragged:
            self.lbl_current_time.setText(self.format_time(value))

    def format_time(self, ms):
        seconds = (ms // 1000) % 60
        minutes = ms // 60000
        return f"{minutes:02}:{seconds:02}"

    def sync_lyrics(self, position_ms):
        if not self.subtitles:
            return

        # Convert ms to seconds
        pos_sec = position_ms / 1000.0

        # Find the active subtitle
        # Optimization: Could store last index to avoid searching from 0
        current_sub = None
        for i, sub in enumerate(self.subtitles):
            if sub["start"] <= pos_sec <= (sub["start"] + sub["duration"]):
                current_sub = sub
                # Verify if the text at this offset matches
                doc_text = self.reading_tab.lyrics_view.toPlainText()
                expected_word = sub['text']
                actual_text = doc_text[sub['text_offset'] : sub['text_offset'] + sub['word_len']]
                
                print(f"DEBUG: Match at {pos_sec:.2f}s. Sub: '{expected_word}' (Offset {sub['text_offset']}). Doc: '{actual_text}'")
                break
        
        if not current_sub:
             print(f"DEBUG: No match for time {pos_sec:.2f}. Range: {self.subtitles[0]['start']:.2f} to {self.subtitles[-1]['start'] + self.subtitles[-1]['duration']:.2f}")

        if current_sub:
            self.highlight_word(current_sub["text_offset"], current_sub["word_len"])

    def highlight_word(self, start_index, length):
        cursor = self.reading_tab.lyrics_view.textCursor()
        cursor.setPosition(start_index)
        cursor.setPosition(start_index + length, QTextCursor.MoveMode.KeepAnchor)

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#ffff00"))  # Yellow highlight
        fmt.setForeground(QColor("#000000"))
        fmt.setFontWeight(QFont.Weight.Bold)

        # Reset entire doc format
        select_all = QTextCursor(self.reading_tab.lyrics_view.document())
        select_all.select(QTextCursor.SelectionType.Document)
        default_fmt = QTextCharFormat()
        default_fmt.setBackground(Qt.GlobalColor.transparent)
        default_fmt.setForeground(QColor("#555"))
        select_all.setCharFormat(default_fmt)

        # Apply new highlight
        cursor.setCharFormat(fmt)

        # Scroll to ensure visible
        self.reading_tab.lyrics_view.setTextCursor(cursor)
        self.reading_tab.lyrics_view.ensureCursorVisible()

    def on_provider_changed(self, index):
        is_deepl = (index == 1)
        self.translation_tab.input_apikey.setEnabled(is_deepl)
        if is_deepl:
            self.translation_tab.input_apikey.setFocus()

    def start_translation(self):
        text = self.translation_tab.trans_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty", "Please enter some text to translate.")
            return

        provider = "google" if self.translation_tab.combo_provider.currentIndex() == 0 else "deepl"
        api_key = self.translation_tab.input_apikey.text().strip()
        target_lang = self.translation_tab.combo_lang.currentData()

        if provider == "deepl" and not api_key:
            QMessageBox.warning(self, "Missing Key", "DeepL requires an API Key.")
            return

        self.translation_tab.btn_translate.setEnabled(False)
        self.translation_tab.trans_output.setPlainText("Translating...")
        
        self.trans_worker = TranslationWorker(text, target_lang, provider, api_key)
        self.trans_worker.finished.connect(self.on_trans_finished)
        self.trans_worker.error.connect(self.on_trans_error)
        self.trans_worker.start()

    def on_trans_finished(self, result):
        self.translation_tab.btn_translate.setEnabled(True)
        self.translation_tab.trans_output.setPlainText(result)

    def on_trans_error(self, err):
        self.translation_tab.btn_translate.setEnabled(True)
        self.translation_tab.trans_output.setPlainText(f"Error: {err}")
        QMessageBox.critical(self, "Translation Error", err)

    def transfer_translation(self):
        text = self.translation_tab.trans_output.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty", "No translated text to transfer.")
            return

        # 1. Transfer text
        self.reading_tab.text_editor.setText(text)
        
        # 2. Switch tab
        self.tabs.setCurrentIndex(0) # Reading tab

        # 3. Auto-select voice
        target_lang = self.translation_tab.combo_lang.currentData() # e.g. "fr"
        
        # Find a voice that starts with this language code
        best_voice_name = None
        for v in self.available_voices:
            if v['language'].startswith(target_lang):
                best_voice_name = v['name']
                break
        
        if best_voice_name:
            # Find index in combo
            index = self.combo_voice.findData(best_voice_name)
            if index >= 0:
                self.combo_voice.setCurrentIndex(index)
                self.status_label.setText(f"Switched to voice: {best_voice_name}")
            else:
                self.status_label.setText(f"Voice {best_voice_name} not found in combo.")
        else:
            self.status_label.setText(f"No voice found for language {target_lang}")

    def send_reading_to_translation(self):
        text = self.reading_tab.text_editor.toPlainText()
        self.translation_tab.trans_input.setText(text)
        self.tabs.setCurrentIndex(1) # Switch to Translation
        
    def send_trans_input_to_reading(self):
        text = self.translation_tab.trans_input.toPlainText()
        self.reading_tab.text_editor.setText(text)
        self.tabs.setCurrentIndex(0) # Switch to Reading

    # -- Utilities --

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open MD", "", "Markdown (*.md);;Txt (*.txt)"
        )
        if path:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Load into the active tab's input
            current_index = self.tabs.currentIndex()
            if current_index == 1: # Translation Tab
                self.translation_tab.trans_input.setText(content)
            else: # Reading Tab (default)
                self.reading_tab.text_editor.setText(content)

    def set_ui_generating(self, generating):
        self.btn_generate.setEnabled(not generating)
        self.btn_play.setEnabled(not generating)
        self.slider.setEnabled(not generating)
        self.reading_tab.text_editor.setReadOnly(generating)

    def on_error(self, msg):
        self.set_ui_generating(False)
        self.progress_bar.hide()
        QMessageBox.critical(self, "Error", msg)

    def closeEvent(self, event):
        if self.current_audio_path and os.path.exists(self.current_audio_path):
            try:
                os.remove(self.current_audio_path)
            except Exception:
                pass
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
