from .qt import QtWidgets, QtCore
import pyqtgraph as pg


class TrackList(QtWidgets.QWidget):
    """
    Tree widget displaying list of tracks in a song.

    For each row, we can set the color (ColorButton) and play mode (QComboBox) of the staff.

    Play modes are autoplay, follow, mute
    """

    colors_changed = QtCore.Signal(object)
    modes_changed = QtCore.Signal()

    def __init__(self):
        super().__init__()

        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        alpha = 255
        self.default_colors = [
            (100, 255, 100, alpha),
            (100, 100, 255, alpha),
            (255, 100, 100, alpha),
            (255, 255, 100, alpha),
            (255, 100, 255, alpha),
            (100, 255, 255, alpha),
        ]

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        # self.tree.setAlternatingRowColors(True)
        self.tree.setColumnCount(3)
        self.layout.addWidget(self.tree, 0, 0)
        self.track_items = {}

    def track_colors(self):
        colors = {}
        for item in self.track_items.values():
            qcolor = item.color_button.color()
            colors[item.track] = (qcolor.red(), qcolor.green(), qcolor.blue())
        return colors
    
    def track_modes(self):
        """Return a dictionary mapping each track to its selected play mode"""
        modes = {}
        for item in self.track_items.values():
            modes[item.track] = item.play_mode.currentText()
        return modes

    def set_track_modes(self, track_modes):
        """Set track modes from a dictionary mapping track keys to mode strings"""
        for track_key, mode in track_modes.items():
            item = self.track_items.get(track_key)
            if item and mode in ['player', 'autoplay', 'visual only', 'hidden']:
                # Block signals to prevent triggering modes_changed while loading
                item.play_mode.blockSignals(True)
                item.play_mode.setCurrentText(mode)
                item.play_mode.blockSignals(False)

    def serialize_modes(self):
        """
        Serialize track modes to a JSON-compatible format.

        Returns a list of [part_name, staff, mode] for each track.
        This format is used for saving to the configuration file.
        """
        modes = self.track_modes()
        return [[part.name, staff, mode] for (part, staff), mode in modes.items()]

    def restore_modes(self, song_info):
        """
        Restore track modes from a SongInfo instance.

        Args:
            song_info: The SongInfo object
        """
        serialized_modes = song_info.get_setting('track_modes')
        if not serialized_modes:
            return

        song = song_info.get_song()

        # Convert from list of [part_name, staff, mode] to {track: mode} dict
        track_modes = {}
        for part_name, staff, mode in serialized_modes:
            # Find the matching track by part name and staff
            for track in song.tracks:
                if track[0] and track[0].name == part_name and track[1] == staff:
                    track_modes[track] = mode
                    break

        self.set_track_modes(track_modes)
    
    def set_song(self, song_info):
        """Set the song from a SongInfo instance."""
        song = song_info.get_song()
        self.song_info = song_info

        self.tree.clear()
        self.track_items = {}
        i = 0
        for track in song.tracks:
            if track[0] is None:
                continue
            item = TrackItem(track, self.default_colors[i % len(self.default_colors)])
            self.tree.addTopLevelItem(item)
            item.setup_ui(self.tree)
            item.color_button.sigColorChanged.connect(self.colors_changed)
            item.play_mode.currentIndexChanged.connect(self.modes_changed)
            i += 1
            self.track_items[track] = item

        for i in range(3):
            self.tree.resizeColumnToContents(i)


class TrackItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, track, color):
        self.track = track
        self.color_button = pg.ColorButton(color=color)
        self.color_button.setMaximumWidth(40)
        self.play_mode = QtWidgets.QComboBox()
        self.play_mode.addItems(['player', 'autoplay', 'visual only', 'hidden'])
        super().__init__([self.track_name])

    @property
    def track_name(self):
        track_name = self.track[0].name
        if self.track[1] is not None:
            track_name += f' staff {self.track[1]}'
        return track_name

    def setup_ui(self, tree):
        tree.setItemWidget(self, 1, self.color_button)
        tree.setItemWidget(self, 2, self.play_mode)

    def set_color(self, color):
        self.color = color

    def set_play_mode(self, mode):
        self.play_mode = mode
