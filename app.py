import sys
import os
import shutil


from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QComboBox,
    QLabel,
    QFileDialog,
    QDoubleSpinBox,
    QMessageBox,
    QProgressBar,
    QStyle,
    QSlider,
    QSplitter,
    QTabWidget,
    QLineEdit,
    QGroupBox,
    QFormLayout,
)
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont

import tts_handler
import handle_text
from translation_worker import TranslationWorker


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Faster Reader")
        self.resize(1280, 720)

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

        self.setup_ui()
        self.populate_voices()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 1. Top Bar
        top_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load Markdown")
        self.btn_load.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        self.btn_load.clicked.connect(self.load_file)

        self.combo_voice = QComboBox()
        self.combo_voice.setMinimumWidth(200)

        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.5, 2.0)
        self.spin_speed.setSingleStep(0.1)
        self.spin_speed.setValue(1.0)
        self.spin_speed.setPrefix("Speed: x")

        top_layout.addWidget(self.btn_load)
        top_layout.addStretch()
        top_layout.addWidget(QLabel("Voice:"))
        top_layout.addWidget(self.combo_voice)
        top_layout.addWidget(self.spin_speed)
        main_layout.addLayout(top_layout)

        # 2. Main Content (Splitter)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Editor
        self.editor_container = QWidget()
        editor_layout = QVBoxLayout(self.editor_container)
        editor_layout.addWidget(QLabel("<b>Input (Markdown):</b>"))
        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("Type markdown text here...")
        editor_layout.addWidget(self.text_editor)

        editor_layout.setContentsMargins(0, 0, 0, 0)

        # Tabs (Reading / Translation)
        self.tabs = QTabWidget()

        # Tab 1: Reading (Synced)
        self.tab_reading = QWidget()
        reading_layout = QVBoxLayout(self.tab_reading)
        reading_layout.addWidget(QLabel("<b>Now Playing (Synced):</b>"))
        self.lyrics_view = QTextEdit()
        self.lyrics_view.setReadOnly(True)
        self.lyrics_view.setStyleSheet("font-size: 14pt; color: #555;")
        reading_layout.addWidget(self.lyrics_view)
        self.tabs.addTab(self.tab_reading, "Reading")

        # Tab 2: Translation
        self.tab_translation = QWidget()
        trans_layout = QVBoxLayout(self.tab_translation)
        
        # Controls
        trans_controls = QGroupBox("Settings")
        trans_form = QFormLayout(trans_controls)
        
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(["Google (Free)", "DeepL (API Key)"])
        self.combo_provider.currentIndexChanged.connect(self.on_provider_changed)
        
        self.input_apikey = QLineEdit()
        self.input_apikey.setPlaceholderText("Enter DeepL API Key")
        self.input_apikey.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_apikey.setEnabled(False) # Default is Google

        self.combo_lang = QComboBox()
        # Common languages
        self.combo_lang.addItem("English", "en")
        self.combo_lang.addItem("French", "fr")
        self.combo_lang.addItem("Spanish", "es")
        self.combo_lang.addItem("German", "de")
        self.combo_lang.addItem("Italian", "it")
        self.combo_lang.addItem("Portuguese", "pt")
        self.combo_lang.addItem("Russian", "ru")
        self.combo_lang.addItem("Japanese", "ja")
        self.combo_lang.addItem("Chinese (Simplified)", "zh-CN")
        
        trans_form.addRow("Provider:", self.combo_provider)
        trans_form.addRow("API Key:", self.input_apikey)
        trans_form.addRow("Target Lang:", self.combo_lang)
        
        self.btn_translate = QPushButton("Translate Input Text")
        self.btn_translate.clicked.connect(self.start_translation)
        
        trans_layout.addWidget(trans_controls)
        trans_layout.addWidget(self.btn_translate)
        
        self.trans_output = QTextEdit()
        self.trans_output.setReadOnly(True)
        self.trans_output.setPlaceholderText("Translation will appear here...")
        trans_layout.addWidget(self.trans_output)
        
        self.tabs.addTab(self.tab_translation, "Translation")

        splitter.addWidget(self.editor_container)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

        # 3. Player Controls
        controls_layout = QHBoxLayout()

        # Play/Pause
        self.btn_play = QPushButton()
        self.btn_play.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.btn_play.setFixedSize(40, 40)
        self.btn_play.clicked.connect(self.toggle_playback)
        self.btn_play.setEnabled(False)  # Disabled until generated

        # Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderReleased.connect(self.on_slider_released)
        self.slider.valueChanged.connect(self.on_slider_moved)
        self.slider.setEnabled(False)

        # Time Labels
        self.lbl_current_time = QLabel("00:00")
        self.lbl_total_time = QLabel("00:00")

        # Generate Button (The main action)
        self.btn_generate = QPushButton("Generate & Read")
        self.btn_generate.setStyleSheet("padding: 5px 15px; font-weight: bold;")
        self.btn_generate.clicked.connect(self.start_generation)

        # Save Button
        self.btn_save = QPushButton("Save MP3")
        self.btn_save.clicked.connect(self.save_audio)

        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.lbl_current_time)
        controls_layout.addWidget(self.slider)
        controls_layout.addWidget(self.lbl_total_time)
        controls_layout.addSpacing(20)
        controls_layout.addWidget(self.btn_generate)
        controls_layout.addWidget(self.btn_save)

        main_layout.addLayout(controls_layout)

        # 4. Status
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        self.status_label = QLabel("Ready")

        sb = self.statusBar()
        sb.addWidget(self.status_label)
        sb.addPermanentWidget(self.progress_bar)

    # -- Logic --

    def populate_voices(self):
        # We assume tts_handler has a synchronous wrapper or we run in thread.
        # For simplicity in this snippet, let's use a thread like before.

        # Re-defining simple loader here for completeness
        class VLoader(QThread):
            loaded = Signal(list)

            def run(self):
                self.loaded.emit(tts_handler.get_voices(language=["en", "fr"]))

        self.vloader = VLoader()
        self.vloader.loaded.connect(self.on_voices_loaded)
        self.vloader.start()

    def on_voices_loaded(self, voices):
        self.combo_voice.clear()
        mapped = tts_handler.voice_mapping.keys()
        for m in mapped:
            self.combo_voice.addItem(f"OpenAI: {m}", m)
        self.combo_voice.insertSeparator(self.combo_voice.count())
        for v in voices:
            self.combo_voice.addItem(f"{v['name']} ({v['language']})", v["name"])

    def start_generation(self):
        text = self.text_editor.toPlainText().strip()
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
        self.lyrics_view.setPlainText(clean_text)

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
        for sub in self.subtitles:
            if sub["start"] <= pos_sec <= (sub["start"] + sub["duration"]):
                current_sub = sub
                break

        if current_sub:
            self.highlight_word(current_sub["text_offset"], current_sub["word_len"])

    def highlight_word(self, start_index, length):
        cursor = self.lyrics_view.textCursor()
        cursor.setPosition(start_index)
        cursor.setPosition(start_index + length, QTextCursor.MoveMode.KeepAnchor)

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#ffff00"))  # Yellow highlight
        fmt.setForeground(QColor("#000000"))
        fmt.setFontWeight(QFont.Weight.Bold)

        # Clear previous highlights?
        # For simplicity, we just reload text if we want to clear,
        # or we rely on the fact that we move fast.
        # Ideally: Reset format for whole doc, then apply.
        # To avoid flicker, we might just un-highlight the *previous* word if we tracked it.
        # Heavy Reset Approach (Simplest logic, maybe slight flicker on huge texts):

        # Better approach:
        # We need a way to clear the previous highlight without resetting the whole text.
        # But for now, let's just highlight. If user wants "Karaoke" style where past text stays colored, that's different.
        # Let's assume "Teleprompter" style: Highlighting current word ONLY.

        # Reset entire doc format
        select_all = QTextCursor(self.lyrics_view.document())
        select_all.select(QTextCursor.SelectionType.Document)
        default_fmt = QTextCharFormat()
        default_fmt.setBackground(Qt.GlobalColor.transparent)
        default_fmt.setForeground(QColor("#555"))
        select_all.setCharFormat(default_fmt)

        # Apply new highlight
        cursor.setCharFormat(fmt)

        # Scroll to ensure visible
        self.lyrics_view.setTextCursor(cursor)
        self.lyrics_view.ensureCursorVisible()

    def on_provider_changed(self, index):
        is_deepl = (index == 1)
        self.input_apikey.setEnabled(is_deepl)
        if is_deepl:
            self.input_apikey.setFocus()

    def start_translation(self):
        text = self.text_editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty", "Please enter some text to translate.")
            return

        provider = "google" if self.combo_provider.currentIndex() == 0 else "deepl"
        api_key = self.input_apikey.text().strip()
        target_lang = self.combo_lang.currentData()

        if provider == "deepl" and not api_key:
            QMessageBox.warning(self, "Missing Key", "DeepL requires an API Key.")
            return

        self.btn_translate.setEnabled(False)
        self.trans_output.setPlainText("Translating...")
        
        self.trans_worker = TranslationWorker(text, target_lang, provider, api_key)
        self.trans_worker.finished.connect(self.on_trans_finished)
        self.trans_worker.error.connect(self.on_trans_error)
        self.trans_worker.start()

    def on_trans_finished(self, result):
        self.btn_translate.setEnabled(True)
        self.trans_output.setPlainText(result)

    def on_trans_error(self, err):
        self.btn_translate.setEnabled(True)
        self.trans_output.setPlainText(f"Error: {err}")
        QMessageBox.critical(self, "Translation Error", err)

    # -- Utilities --

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open MD", "", "Markdown (*.md);;Txt (*.txt)"
        )
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.text_editor.setText(f.read())

    def set_ui_generating(self, generating):
        self.btn_generate.setEnabled(not generating)
        self.btn_play.setEnabled(not generating)
        self.slider.setEnabled(not generating)
        self.text_editor.setReadOnly(generating)

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
