import sys
import re
import syncedlyrics

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QPlainTextEdit,
    QVBoxLayout, QHBoxLayout, QWidget, QSlider, QFileDialog, QScrollArea, QLineEdit, QDialog, QDialogButtonBox, QStyleFactory, QMessageBox
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl, Qt, QTime
from PyQt6.QtGui import QKeySequence, QShortcut

class LrcSyncApp(QMainWindow):
    song_filename: str
    lyric_verses: list[tuple[str,str]] # Timing and verse
    song_is_loaded: bool
    current_verse_index: int

    def __init__(self):
        super().__init__()
        self.song_is_loaded = False
        self.lyric_verses = []
        self.current_verse_index = 0

        # Set up the media player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        # Main layout
        main_layout = QVBoxLayout()

        # Pause/play Shortcut
        self.space_shortcut = QShortcut(QKeySequence("Space"), self)
        self.space_shortcut.activated.connect(self.toggle_play_pause)
        # Pause/play Shortcut
        self.sync_next_verse_shortcut= QShortcut(QKeySequence("n"), self)
        self.sync_next_verse_shortcut.activated.connect(self.sync_next_verse)


        # Top Section: File name, Play/Pause button, Seek Bar
        self.file_label = QLabel("No file loaded")
        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.clicked.connect(self.toggle_play_pause)

        # Seek Bar
        self.seek_bar = QSlider(Qt.Orientation.Horizontal)
        self.seek_bar.setRange(0, 0)
        self.seek_bar.sliderMoved.connect(self.set_position)

        # Top layout
        top_layout = QVBoxLayout()
        top_layout.addWidget(self.file_label)
        top_layout.addWidget(self.play_pause_button)
        top_layout.addWidget(self.seek_bar)

        # Add top layout to the main layout
        main_layout.addLayout(top_layout)

        # Main Section: Lyrics and Buttons (Sync, Load, Get Lyrics, Save)
        # Scroll area for lyrics
        self.scroll_area = QScrollArea()
        self.scroll_area.setStyleSheet("background-color: #33364a")
        self.scroll_area.setWidgetResizable(True)

        # Scroll area contents: layout to hold all the verses
        self.scroll_content = QWidget()
        self.lyrics_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)

        # Buttons
        self.open_file_button = QPushButton("Open MP3 File")
        self.open_file_button.clicked.connect(self.open_new_file)

        self.syncall_button = QPushButton("Resync All")
        self.syncall_button.clicked.connect(self.sync_all)

        self.load_button = QPushButton("Load LRC File")
        self.load_button.clicked.connect(self.load_lrc_file)

        self.get_lyrics_button = QPushButton("Get Lyrics")
        self.get_lyrics_button.clicked.connect(self.get_lyrics_online)

        self.save_button = QPushButton("Save LRC File")
        self.save_button.clicked.connect(self.save_lrc_file)

        self.clear_button = QPushButton("Clear Lyrics")
        self.clear_button.clicked.connect(self.clear_lyrics)

        # Button layout (Vertical on the right)
        button_layout = QVBoxLayout()
        button_layout.addWidget(self.open_file_button)
        button_layout.addWidget(self.syncall_button)
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.get_lyrics_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()

        # Main content layout (Lyrics on left, buttons on right)
        content_layout = QHBoxLayout()
        content_layout.addWidget(self.scroll_area)
        content_layout.addLayout(button_layout)

        # Add content layout to the main layout
        main_layout.addLayout(content_layout)

        # Set up the main widget and layout
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Window settings
        self.setWindowTitle("LRC Sync Tool")
        self.resize(600, 400)

        # Connect signals for media player
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)

        self.open_file()


    def open_file(self):
        audio_file, _ = QFileDialog.getOpenFileName(self, "Open Audio File", "/home/georgiou/Music", filter = "MP3 Files (*.mp3)")
        self.song_filename = audio_file.split(".")[0].split("/")[-1]
        print(self.song_filename)
        self.player.setSource(QUrl.fromLocalFile(audio_file))
        self.file_label.setText(f"Loaded: {self.song_filename}")
        self.song_is_loaded = True
        """
        if audio_file:
            self.player.setSource(QUrl.fromLocalFile(audio_file))
            self.player.play()
        """


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


    def duration_changed(self, duration):
        self.seek_bar.setRange(0, duration)


    def clear_lyrics(self):
        for i in reversed(range(self.lyrics_layout.count())):
            item = self.lyrics_layout.itemAt(i)
            if item is not None:
                self.delete_verse(item.widget())


    def sync_all(self):
        # Step 1: Get current time (shift reference) from media player position
        current_time = self.player.position() - 300  # Subtract 300 ms as before
        formatted_current_time = QTime(0, 0).addMSecs(current_time)

        # Step 2: Extract the timestamp of the first verse
        if self.lyrics_layout.count() == 0:
            return  # No verses to sync

        first_verse_widget = self.lyrics_layout.itemAt(0).widget()
        first_timestamp_label = first_verse_widget.layout().itemAt(0).widget().text()  # Get timestamp label text
        first_timestamp = QTime.fromString(first_timestamp_label.strip("[]"), "mm:ss.zz")  # Parse time from string

        # Step 3: Calculate time difference (in milliseconds)
        time_difference = first_timestamp.msecsTo(formatted_current_time)

        # Step 4: Iterate through all verses and shift timestamps
        for i in range(self.lyrics_layout.count()):
            verse_widget = self.lyrics_layout.itemAt(i).widget()
            timestamp_label = verse_widget.layout().itemAt(0).widget()  # Get timestamp label

            # Get the current verse's timestamp and shift it
            verse_timestamp = QTime.fromString(timestamp_label.text().strip("[]"), "mm:ss.zz")
            new_timestamp = verse_timestamp.addMSecs(time_difference)

            # Update the timestamp label with the new time
            timestamp_label.setText(f"[{new_timestamp.toString('mm:ss.zz')}]")


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


    def sync_verse(self, timestamp):
        current_time = self.player.position()-300  # Get current playback position in ms
        formatted_time = QTime(0, 0).addMSecs(current_time).toString("mm:ss.zzz")[:-1]  # Format time for LRC
        timestamp.setText(f"[{formatted_time}]")


    def find_verse_index(self, time_text):
        """
        Find the index of a verse by its text.
        Returns the index of the verse if found, otherwise -1.
        """
        for i in range(self.lyrics_layout.count()):
            verse_widget = self.lyrics_layout.itemAt(i).widget()
            if verse_widget is not None:
                verse_layout = verse_widget.layout()
                #verse_input = verse_layout.itemAt(1).widget()  # Get the QLineEdit
                verse_input = verse_layout.itemAt(0).widget()  # Get the QLabel
                if isinstance(verse_input, QLabel) and verse_input.text() == time_text:
                    return i

        return -1


    def add_verse(self, timestamp="", verse="", after_index=None):
        verse_widget = QWidget()
        verse_layout = QHBoxLayout()

        timestamp_label = QLabel(timestamp)
        timestamp_label.setStyleSheet("color: #ffffff")
        verse_layout.addWidget(timestamp_label)

        verse_text = QLineEdit(verse)
        verse_layout.addWidget(verse_text)

        sync_button = QPushButton("⏲")
        sync_button.setStyleSheet("background-color: #4a34aa; border: 1px solid #8a74ea")
        sync_button.clicked.connect(lambda: self.sync_verse(timestamp_label))
        verse_layout.addWidget(sync_button)

        delete_button = QPushButton("🗑")
        delete_button.setStyleSheet("background-color: #4a34aa; border: 1px solid #8a74ea")
        delete_button.clicked.connect(lambda: self.delete_verse(verse_widget))
        verse_layout.addWidget(delete_button)

        add_button = QPushButton("+")
        add_button.setStyleSheet("background-color: #4a34aa; border: 1px solid #8a74ea")
        add_button.clicked.connect(lambda: self.add_verse("[00:00.00]", "", after_index=self.find_verse_index(timestamp_label.text())))
        verse_layout.addWidget(add_button)

        verse_widget.setLayout(verse_layout)

        verse_widget.setObjectName("verse");
        verse_widget.setStyleSheet("QWidget#verse { background-color: #232340; border-radius: 16px; border: 2px solid #5a44aa; padding: 10px;}")

        verse_widget.parent_layout = self.lyrics_layout

        if after_index is not None and 0 <= after_index < self.lyrics_layout.count():
            self.lyrics_layout.insertWidget(after_index + 1, verse_widget)
        else:
            self.lyrics_layout.addWidget(verse_widget)


    def delete_verse(self, verse_widget):
        if verse_widget is not None:
            parent_layout = getattr(verse_widget, 'parent_layout', None)  # Retrieve stored parent layout if available
            if parent_layout:
                parent_layout.removeWidget(verse_widget)
                verse_widget.deleteLater()


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
                for i in range(self.lyrics_layout.count()):
                    verse_widget = self.lyrics_layout.itemAt(i).widget()
                    verse_layout = verse_widget.layout()
                    timestamp_label = verse_layout.itemAt(0).widget().text()
                    verse_text = verse_layout.itemAt(1).widget().text()
                    file.write(f"{timestamp_label} {verse_text}\n")


    def open_new_file(self):
        self.clear_lyrics()
        self.open_file()


    def sync_next_verse(self):
        total_verses = self.lyrics_layout.count()

        if total_verses == 0:
            return

        if self.current_verse_index >= total_verses:
            self.current_verse_index = 0

        current_verse_widget = self.lyrics_layout.itemAt(self.current_verse_index).widget()
        timestamp_label = current_verse_widget.layout().itemAt(0).widget()
        current_verse_widget.setStyleSheet("QWidget#verse { background-color: #232340; border-radius: 16px; border: 2px solid #5a44aa; padding: 10px;}")

        self.scroll_area.ensureWidgetVisible(current_verse_widget)

        self.sync_verse(timestamp_label)
        self.current_verse_index += 1

        if self.lyrics_layout.itemAt(self.current_verse_index) is not None:
            next_verse_widget = self.lyrics_layout.itemAt(self.current_verse_index).widget()
            next_verse_widget.setStyleSheet("background-color: #232340; border-radius: 16px; border: 2px solid #aa94fa; padding: 10px;")



app = QApplication(sys.argv)
app.setStyleSheet("""

     QPushButton {
        background-color: #4a34aa;
        color: white;
        font-size: 14px;
        border-radius: 15px;
        padding: 8px;
    }
    QPushButton:hover {
        background-color: #6555aa;
    }
    QLabel {
        font-size: 16px;
        border-radius: 10px;

    }
    QScrollBar:vertical {
        border: none;
        background-color: #c0c0c0;    /* Background of the scrollbar */
        width: 12px;                   /* Scrollbar width */
        margin: 0px 2px 0px 2px;       /* Margins around scrollbar */
    }

    QScrollBar::handle:vertical {
        background-color: #5e5e5e;     /* Scroll handle color */
        min-height: 30px;              /* Minimum height of the handle */
    }

    QScrollBar::handle:vertical:hover {
        background-color: #787878;     /* Color on hover */
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        border: none;
        background: none;
    }

    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: none;              /* No background for the page sections */
    }
""")


window = LrcSyncApp()
window.show()
sys.exit(app.exec())
