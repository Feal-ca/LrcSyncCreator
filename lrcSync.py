import sys
import re
import syncedlyrics
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QPlainTextEdit,
    QVBoxLayout, QHBoxLayout, QWidget, QSlider, QFileDialog, QScrollArea, QLineEdit, QDialog, QDialogButtonBox, QStyleFactory, QMessageBox
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl, Qt, QTime, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QKeySequence, QShortcut

class Verse(QWidget):
    def __init__(self, timestamp="", verse="", parent=None):
        super().__init__(parent)
        self.setObjectName("verse")
       
        self.setStyleSheet("background-color: #232340; border-radius: 16px; border: 2px solid #5a44aa; padding: 10px;")
        
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(5, 5, 5, 5)
        outer_layout.setSpacing(5)
        
        inner_widget = QWidget()
        inner_widget.setStyleSheet("background-color: #2a2a4a; border: 2px solid #5a44aa; border-radius: 10px; padding: 5px;")
        
        layout = QHBoxLayout(inner_widget)
        
        self.timestamp_label = QLabel(timestamp)
        self.timestamp_label.setStyleSheet("color: #ffffff")
        layout.addWidget(self.timestamp_label)
        
        self.verse_text = QLineEdit(verse)
        layout.addWidget(self.verse_text, stretch=1)
        
        button_size = 33
        button_style = "background-color: #4a34aa; border: 1px solid #8a74ea; font-size: 16px; font-weight: bold; padding: 2px; margin: 0px;"
        
        self.sync_button = QPushButton("⏲")
        self.sync_button.setFixedSize(button_size, button_size)
        self.sync_button.setStyleSheet(button_style)
        layout.addWidget(self.sync_button)
        
        self.delete_button = QPushButton("🗑")
        self.delete_button.setFixedSize(button_size, button_size)
        self.delete_button.setStyleSheet(button_style)
        layout.addWidget(self.delete_button)
        
        self.add_button = QPushButton("+")
        self.add_button.setFixedSize(button_size, button_size)
        self.add_button.setStyleSheet(button_style)
        layout.addWidget(self.add_button)
        
        outer_layout.addWidget(inner_widget)
        self.setLayout(outer_layout)

    def get_timestamp(self):
        return self.timestamp_label.text()
        
    def get_verse_text(self):
        return self.verse_text.text()
        
    def set_timestamp(self, timestamp):
        self.timestamp_label.setText(timestamp)
        
    def set_selected(self, selected):
        inner_widget = self.findChild(QWidget)  
        if selected:
            # self.setStyleSheet("background-color: #2a2a4a; border-radius: 16px; border: 2px solid #ffcc00; padding: 10px;")
            inner_widget.setStyleSheet("background-color: #3a3a5a; border: 2px solid #ccaaff; border-radius: 16px; padding: 5px; font-weight: bold;")
        else:
            # self.setStyleSheet("background-color: #232340; border-radius: 16px; border: 2px solid #bb55bb; padding: 10px;")
            inner_widget.setStyleSheet("background-color: #2a2a4a; border: 2px solid #5a44aa; border-radius: 16px; padding: 5px;")

class LrcSyncApp(QMainWindow):
    song_filename: str
    lyric_verses: list[tuple[str,str]] # Timing and verse
    song_is_loaded: bool
    current_verse_index: int


    def __init__(self):
        super().__init__()
        self.init_state()
        self.init_media_player()
        self.init_shortcuts()
        self.init_ui()
        self.init_signals()
        self.open_file()


    def init_state(self):
        self.song_is_loaded = False
        self.lyric_verses = []
        self.current_verse_index = 0


    def init_media_player(self):
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)


    def init_shortcuts(self):
        self.space_shortcut = QShortcut(QKeySequence("Space"), self)
        self.space_shortcut.activated.connect(self.toggle_play_pause)
        self.sync_next_verse_shortcut = QShortcut(QKeySequence("s"), self)
        self.sync_next_verse_shortcut.activated.connect(self.sync_next_verse)
        self.up_shortcut = QShortcut(QKeySequence("Up"), self)
        self.up_shortcut.activated.connect(lambda: self.select_verse(self.current_verse_index - 1))
        self.down_shortcut = QShortcut(QKeySequence("Down"), self)
        self.down_shortcut.activated.connect(lambda: self.select_verse(self.current_verse_index + 1))


    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Initialize top section
        top_layout = self.init_top_section()
        main_layout.addLayout(top_layout)

        # Initialize main content
        content_layout = self.init_main_section()
        main_layout.addLayout(content_layout)

        # Set up the main widget and layout
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Window settings
        self.setWindowTitle("LRC Sync Tool")
        self.resize(600, 400)


    def init_top_section(self):
        # File label
        self.file_label = QLabel("No file loaded")
        
        # Play controls
        play_controls_layout = QHBoxLayout()
        
        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.setFixedSize(72, 33)
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        play_controls_layout.addWidget(self.play_pause_button)
        
        play_controls_layout.addStretch()
        
        self.time_label = QLabel("00:00.00")
        self.time_label.setStyleSheet("font-size: 18px")
        play_controls_layout.addWidget(self.time_label)
        
        play_controls_layout.addStretch()
        
        self.verse_index_label = QLabel("Verse: 0/0")
        play_controls_layout.addWidget(self.verse_index_label, alignment=Qt.AlignmentFlag.AlignRight)

        # Seek Bar
        self.seek_bar = QSlider(Qt.Orientation.Horizontal)
        self.seek_bar.setRange(0, 0)
        self.seek_bar.sliderMoved.connect(self.set_position)

        # Combine into top layout
        top_layout = QVBoxLayout()
        top_layout.addWidget(self.file_label)
        top_layout.addLayout(play_controls_layout)
        top_layout.addWidget(self.seek_bar)
        
        return top_layout


    def init_main_section(self):
        # Scroll area setup
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("background-color: #33364a")
        self.scroll_area.setWidgetResizable(True)

        self.scroll_animation = QPropertyAnimation(self.scroll_area.verticalScrollBar(), b"value")
        self.scroll_animation.setEasingCurve(QEasingCurve.Type.Linear)
        self.scroll_animation.setDuration(150)

        self.scroll_content = QWidget()
        self.lyrics_layout = QVBoxLayout(self.scroll_content)
        self.lyrics_layout.addStretch()
        self.scroll_area.setWidget(self.scroll_content)

        # Button setup
        button_layout = self.init_buttons()

        # Combine into content layout
        content_layout = QHBoxLayout()
        content_layout.addWidget(self.scroll_area, stretch=4)
        content_layout.addLayout(button_layout, stretch=1)
        
        return content_layout


    def init_buttons(self):
        button_width = 88
        button_height = int(0.75*button_width)

        self.open_file_button = QPushButton("Open\nMP3 File")
        self.open_file_button.setFixedSize(button_width, button_height)
        self.open_file_button.clicked.connect(self.open_new_file)

        self.syncall_button = QPushButton("Resync\nAll")
        self.syncall_button.setFixedSize(button_width, button_height)
        self.syncall_button.clicked.connect(self.sync_all)

        self.load_button = QPushButton("Load\nLRC File")
        self.load_button.setFixedSize(button_width, button_height)
        self.load_button.clicked.connect(self.load_lrc_file)

        self.get_lyrics_button = QPushButton("Get\nLyrics")
        self.get_lyrics_button.setFixedSize(button_width, button_height)
        self.get_lyrics_button.clicked.connect(self.get_lyrics_online)

        self.save_button = QPushButton("Save\nLRC File")
        self.save_button.setFixedSize(button_width, button_height)
        self.save_button.clicked.connect(self.save_lrc_file)

        self.clear_button = QPushButton("Clear\nLyrics")
        self.clear_button.setFixedSize(button_width, button_height)
        self.clear_button.clicked.connect(self.clear_lyrics)

        button_layout = QVBoxLayout()
        button_layout.addWidget(self.open_file_button)
        button_layout.addWidget(self.syncall_button)
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.get_lyrics_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch(1)
        button_layout.setSpacing(10)

        return button_layout


    def init_signals(self):
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)


    def open_file(self):
        audio_file, _ = QFileDialog.getOpenFileName(self, "Open Audio File", "/home/georgiou/Music", filter = "MP3 Files (*.mp3)")
        self.song_filename = audio_file.split(".")[0].split("/")[-1]
        print(self.song_filename)
        self.player.setSource(QUrl.fromLocalFile(audio_file))
        self.file_label.setText(f"Loaded: {self.song_filename}")
        self.song_is_loaded = True
        self.add_verse("[00:00.00]", "")


    def _show_error_message(self, error_text: str):
        error_box = QMessageBox()
        error_box.setIcon(QMessageBox.Icon.Critical)  # Use QMessageBox.Icon.Critical for PyQt6
        error_box.setWindowTitle("Error")
        error_box.setText(error_text)
        error_box.exec()


    def toggle_play_pause(self):
        if self.player.isPlaying():
            self.player.pause()
            self.play_pause_button.setText("Play")
        else:
            self.player.play()
            self.play_pause_button.setText("Pause")


    def set_position(self, position):
        self.player.setPosition(position)


    def position_changed(self, position):
        self.seek_bar.setValue(position)
        current_time = QTime(0, 0).addMSecs(position)
        self.time_label.setText(current_time.toString("mm:ss.zz"))


    def duration_changed(self, duration):
        self.seek_bar.setRange(0, duration)


    def clear_lyrics(self):
        for i in reversed(range(self.lyrics_layout.count())):
            item = self.lyrics_layout.itemAt(i)
            if item is not None and not item.isEmpty():
                widget = item.widget()
                if isinstance(widget, Verse):
                    self.delete_verse(widget)
        self.current_verse_index = 0
        self.update_verse_index_label()
        self.add_verse("[00:00.00]", "")

    def sync_all(self):
        # Step 1: Get current time (shift reference) from media player position
        current_time = self.player.position() - 300  # Subtract 300 ms as before
        formatted_current_time = QTime(0, 0).addMSecs(current_time)

        # Step 2: Extract the timestamp of the first verse
        if self.lyrics_layout.count() == 0:
            return  # No verses to sync

        first_verse = self.lyrics_layout.itemAt(0).widget()
        first_timestamp = QTime.fromString(first_verse.get_timestamp().strip("[]"), "mm:ss.zz")

        # Step 3: Calculate time difference (in milliseconds)
        time_difference = first_timestamp.msecsTo(formatted_current_time)

        # Step 4: Iterate through all verses and shift timestamps
        for i in range(self.lyrics_layout.count()):
            verse = self.lyrics_layout.itemAt(i).widget()
            if isinstance(verse, Verse):
                verse_timestamp = QTime.fromString(verse.get_timestamp().strip("[]"), "mm:ss.zz")
                new_timestamp = verse_timestamp.addMSecs(time_difference)
                verse.set_timestamp(f"[{new_timestamp.toString('mm:ss.zz')}]")


    def get_lyrics_online(self):
        search_box = QDialog(self)
        search_box.setWindowTitle("Search for lyrics online")

        layout = QVBoxLayout()
        query_input = QLineEdit(self.song_filename)
        layout.addWidget(query_input)

        # OK and Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)

        button_box.accepted.connect(search_box.accept)
        button_box.rejected.connect(search_box.reject)

        search_box.setLayout(layout)

        if search_box.exec() == QDialog.DialogCode.Accepted:
            search_query = query_input.text()
            text = syncedlyrics.search(f"{search_query}")
            self.add_all_verses(text)


    def find_verse_index(self, time_text):
        """
        Find the index of a verse by its text.
        Returns the index of the verse if found, otherwise -1.
        """
        for i in range(self.lyrics_layout.count()):
            verse = self.lyrics_layout.itemAt(i).widget()
            if isinstance(verse, Verse) and verse.get_timestamp() == time_text:
                return i
        return -1


    def add_verse(self, timestamp="", verse="", after_index=None):
        verse_widget = Verse(timestamp, verse)
        verse_widget.sync_button.clicked.connect(lambda: self.sync_verse(verse_widget))
        verse_widget.delete_button.clicked.connect(lambda: self.delete_verse(verse_widget))
        verse_widget.add_button.clicked.connect(lambda: self.add_verse("[00:00.00]", "", after_index=self.find_verse_index(verse_widget.get_timestamp())))

        if after_index is not None and 0 <= after_index < self.lyrics_layout.count():
            self.lyrics_layout.insertWidget(after_index + 1, verse_widget)
        else:
            # Insert before the stretch
            self.lyrics_layout.insertWidget(self.lyrics_layout.count() - 1, verse_widget)
        
        self.update_verse_index_label()


    def delete_verse(self, verse_widget):
        if verse_widget is not None:
            index = self.lyrics_layout.indexOf(verse_widget)
            if index >= 0:
                self.lyrics_layout.removeWidget(verse_widget)
                verse_widget.deleteLater()
                if self.current_verse_index >= self.lyrics_layout.count() - 1:  # -1 for stretch
                    self.current_verse_index = max(0, self.lyrics_layout.count() - 2)  # -2 for stretch
                self.update_verse_index_label()


    def add_all_verses(self, lyrics):
        self.clear_lyrics()
        lines = lyrics.split("\n")
        pattern = r'(\[\d{2}:\d{2}\.\d{2}\])\s?(.+)'
        for line in lines:
            match = re.match(pattern, line)
            if match:
                timestamp = match.group(1)
                lyric = match.group(2)
            else:
                timestamp = "[00:00.00]"
                lyric = line.strip()

            self.add_verse(timestamp, lyric)
            self.lyric_verses.append((timestamp, lyric))


    def load_lrc_file(self):
        if self.song_is_loaded:
            try:
                with open(f"/home/georgiou/Music/{self.song_filename}.lrc", 'r', encoding='utf-8') as file:
                    text = file.read()
                    self.add_all_verses(text)
            except FileNotFoundError:
                self._show_error_message("I couldn't find a .lrc with that name, maybe try *actually creating one*? ")
        else:
            self._show_error_message("You did not load a song; yet expect me to find Lrc? Outrageous!")


    def save_lrc_file(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save LRC File", f"/home/georgiou/Music/{self.song_filename}.lrc", "LRC Files (*.lrc);;All Files (*)")
        if file_name:
            with open(file_name, 'w', encoding='utf-8') as file:
                for i in range(self.lyrics_layout.count() - 1):  # -1 to skip the stretch
                    verse = self.lyrics_layout.itemAt(i).widget()
                    if isinstance(verse, Verse):
                        file.write(f"{verse.get_timestamp()} {verse.get_verse_text()}\n")


    def open_new_file(self):
        self.clear_lyrics()
        self.open_file()


    def update_verse_index_label(self):
        total_verses = self.lyrics_layout.count() - 1  # -1 for stretch
        self.verse_index_label.setText(f"Verse: {self.current_verse_index + 1}/{total_verses}")


    def select_verse(self, index):
        total_verses = self.lyrics_layout.count() - 1  # -1 for stretch
        if total_verses == 0:
            return

        # Reset current verse style
        if 0 <= self.current_verse_index < total_verses:
            current_verse = self.lyrics_layout.itemAt(self.current_verse_index).widget()
            current_verse.set_selected(False)

        # Update index with circular wrapping
        self.current_verse_index = index % total_verses if index >= 0 else total_verses - 1

        # Style new current verse
        new_verse = self.lyrics_layout.itemAt(self.current_verse_index).widget()
        new_verse.set_selected(True)
        
        # Center the selected verse in the scroll area with animation
        scroll_bar = self.scroll_area.verticalScrollBar()
        widget_pos = new_verse.pos().y()
        viewport_height = self.scroll_area.viewport().height()
        widget_height = new_verse.height()
        
        # Calculate position to center the widget
        center_position = widget_pos - (viewport_height - widget_height) // 2
        
        # Set up and start the scroll animation
        self.scroll_animation.setStartValue(scroll_bar.value())
        self.scroll_animation.setEndValue(center_position)
        self.scroll_animation.start()

        self.update_verse_index_label()


    def sync_next_verse(self):
        current_verse = self.lyrics_layout.itemAt(self.current_verse_index).widget()
        self.sync_verse(current_verse)
        self.select_verse(self.current_verse_index + 1)


    def sync_verse(self, verse):
        current_time = self.player.position()-300  # Get current playback position in ms
        formatted_time = QTime(0, 0).addMSecs(current_time).toString("mm:ss.zzz")[:-1]  # Format time for LRC
        verse.set_timestamp(f"[{formatted_time}]")


app = QApplication(sys.argv)

# Define stylesheet for the application
stylesheet = """
    QWidget#verse { 
        background-color: #232340; 
        border-radius: 16px; 
        border: 2px solid #5a44aa; 
        padding: 10px;
        margin-right: 10px;
    }
    /* Base colors */
    * {
        color: #ffffff;
        font-size: 14px;
    }

    QPushButton {
        background-color: #4a34aa;
        border-radius: 15px;
        padding: 8px 16px;
        border: 1px solid #5a44aa;
    }

    QPushButton:hover {
        background-color: #5a44aa;
        border: 1px solid #6a54ba;
    }

    QPushButton:pressed {
        background-color: #3a24aa;
    }

    QLabel {
        font-size: 16px;
        border-radius: 10px;
        padding: 4px;
    }

    /* Scrollbar styling */
    QScrollBar:vertical {
        border: none;
        background-color: #232340;
        width: 12px;
        margin: 0px;
        border-radius: 6px;
    }

    QScrollBar::handle:vertical {
        background-color: #4a34aa;
        min-height: 30px;
        border-radius: 6px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #5a44aa;
    }

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {
        border: none;
        background: none;
        height: 0px;
    }

    QScrollBar::add-page:vertical,
    QScrollBar::sub-page:vertical {
        background: none;
    }
"""

app.setStyleSheet(stylesheet)

window = LrcSyncApp()
window.show()
sys.exit(app.exec())
