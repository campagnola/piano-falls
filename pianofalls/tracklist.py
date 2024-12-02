from .qt import QtWidgets, QtCore
import pyqtgraph as pg


class TrackList(QtWidgets.QWidget):
    """
    Tree widget displaying list of tracks in a song.

    For each row, we can set the color (ColorButton) and play mode (QComboBox) of the staff.

    Play modes are autoplay, follow, mute
    """

    colors_changed = QtCore.Signal()
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
        return {item.track: item.color_button.color() for item in self.track_items.values()}

    def set_song(self, song):
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


class TrackItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, track, color):
        self.track = track
        self.color_button = pg.ColorButton(color=color)
        self.play_mode = QtWidgets.QComboBox()
        self.play_mode.addItems(['autoplay', 'follow', 'mute'])
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