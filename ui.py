from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QComboBox, QDoubleSpinBox, QProgressBar, QStyle,
    QSlider, QSplitter, QTabWidget, QLineEdit, QGroupBox, QFormLayout,
    QMainWindow
)
from PySide6.QtCore import Qt

class ReadingTabUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Input
        input_container = QWidget()
        ic_layout = QVBoxLayout(input_container)
        ic_layout.addWidget(QLabel("<b>Input (Markdown):</b>"))
        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("Type markdown text here...")
        ic_layout.addWidget(self.text_editor)
        ic_layout.setContentsMargins(0,0,0,0)
        
        # Output
        output_container = QWidget()
        oc_layout = QVBoxLayout(output_container)
        oc_layout.addWidget(QLabel("<b>Now Playing (Synced):</b>"))
        self.lyrics_view = QTextEdit()
        self.lyrics_view.setReadOnly(True)
        self.lyrics_view.setStyleSheet("font-size: 14pt; color: #555;")
        oc_layout.addWidget(self.lyrics_view)
        oc_layout.setContentsMargins(0,0,0,0)
        
        splitter.addWidget(input_container)
        splitter.addWidget(output_container)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        # Button
        self.btn_send_to_trans = QPushButton("Send Input to Translation Tab")
        
        layout.addWidget(self.btn_send_to_trans)
        layout.addWidget(splitter)

class TranslationTabUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Input
        input_container = QWidget()
        ic_layout = QVBoxLayout(input_container)
        ic_layout.addWidget(QLabel("<b>Translation Input:</b>"))
        self.trans_input = QTextEdit()
        self.trans_input.setPlaceholderText("Type text to translate here...")
        ic_layout.addWidget(self.trans_input)
        ic_layout.setContentsMargins(0,0,0,0)
        
        splitter.addWidget(input_container)
        
        # Controls
        controls = QGroupBox("Settings")
        form = QFormLayout(controls)
        
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(["Google (Free)", "DeepL (API Key)"])
        
        self.input_apikey = QLineEdit()
        self.input_apikey.setPlaceholderText("Enter DeepL API Key")
        self.input_apikey.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_apikey.setEnabled(False)
        
        self.combo_lang = QComboBox()
        self.combo_lang.addItem("English", "en")
        self.combo_lang.addItem("French", "fr")
        self.combo_lang.addItem("Spanish", "es")
        self.combo_lang.addItem("German", "de")
        self.combo_lang.addItem("Italian", "it")
        self.combo_lang.addItem("Portuguese", "pt")
        self.combo_lang.addItem("Russian", "ru")
        self.combo_lang.addItem("Japanese", "ja")
        self.combo_lang.addItem("Chinese (Simplified)", "zh-CN")
        
        form.addRow("Provider:", self.combo_provider)
        form.addRow("API Key:", self.input_apikey)
        form.addRow("Target Lang:", self.combo_lang)
        
        self.btn_translate = QPushButton("Translate Input Text")
        self.btn_transfer = QPushButton("Use Translated Text & Switch to Reader")
        self.btn_send_input_to_read = QPushButton("Send Input to Reader")
        
        layout.addWidget(controls)
        layout.addWidget(self.btn_translate)
        layout.addWidget(self.btn_transfer)
        layout.addWidget(self.btn_send_input_to_read)
        
        # Output
        output_container = QWidget()
        oc_layout = QVBoxLayout(output_container)
        oc_layout.addWidget(QLabel("<b>Translation Output:</b>"))
        self.trans_output = QTextEdit()
        self.trans_output.setReadOnly(True)
        self.trans_output.setPlaceholderText("Translation will appear here...")
        oc_layout.addWidget(self.trans_output)
        oc_layout.setContentsMargins(0,0,0,0)
        
        splitter.addWidget(output_container)
        layout.addWidget(splitter)

class MainWindowUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Faster Reader")
        self.resize(1280, 720)
        self.setup_ui()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Top Bar
        top_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load Markdown")
        self.btn_load.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        
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
        
        # Tabs
        self.tabs = QTabWidget()
        self.reading_tab = ReadingTabUI()
        self.translation_tab = TranslationTabUI()
        
        self.tabs.addTab(self.reading_tab, "Reading")
        self.tabs.addTab(self.translation_tab, "Translation")
        
        main_layout.addWidget(self.tabs)
        
        # Player Controls
        controls_layout = QHBoxLayout()
        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play.setFixedSize(40, 40)
        self.btn_play.setEnabled(False)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setEnabled(False)
        
        self.lbl_current_time = QLabel("00:00")
        self.lbl_total_time = QLabel("00:00")
        
        self.btn_generate = QPushButton("Generate & Read")
        self.btn_generate.setStyleSheet("padding: 5px 15px; font-weight: bold;")
        
        self.btn_save = QPushButton("Save MP3")
        
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.lbl_current_time)
        controls_layout.addWidget(self.slider)
        controls_layout.addWidget(self.lbl_total_time)
        controls_layout.addSpacing(20)
        controls_layout.addWidget(self.btn_generate)
        controls_layout.addWidget(self.btn_save)
        
        main_layout.addLayout(controls_layout)
        
        # Status
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        self.status_label = QLabel("Ready")
        
        sb = self.statusBar()
        sb.addWidget(self.status_label)
        sb.addPermanentWidget(self.progress_bar)
