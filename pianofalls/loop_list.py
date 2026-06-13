from .qt import QtWidgets, QtCore


class LoopList(QtWidgets.QWidget):
    """
    Widget for managing practice loop regions in a song.

    Displays loops (start/end times in seconds) for the current song,
    sorted chronologically. Each loop has an active checkbox and editable
    start/end spin boxes. Active loops are enforced during playback (time
    jumps to start when end is reached) and shown in the waterfall.

    Loop data is persisted to and restored from song settings automatically.
    """
    loops_changed = QtCore.Signal(list)
    add_requested = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.song_info = None
        self._updating = False

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setLayout(layout)

        label = QtWidgets.QLabel('Practice Loops:')
        layout.addWidget(label)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnCount(3)
        self.tree.setMaximumHeight(120)
        layout.addWidget(self.tree)

        btn_layout = QtWidgets.QHBoxLayout()
        self.add_btn = QtWidgets.QPushButton('Add')
        self.remove_btn = QtWidgets.QPushButton('Remove')
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        layout.addLayout(btn_layout)

        self.tree.itemChanged.connect(self._on_item_changed)
        self.add_btn.clicked.connect(self.add_requested.emit)
        self.remove_btn.clicked.connect(self._on_remove)

    def set_song(self, song_info):
        """Load loops from song settings and populate the tree."""
        self.song_info = song_info
        loops = song_info.get_setting('loops') or []
        self._populate(loops)

    def _populate(self, loops):
        """Rebuild the tree from a list of loop dicts. Does not save to config."""
        self._updating = True
        self.tree.clear()
        for loop in sorted(loops, key=lambda l: l['start']):
            item = LoopItem(loop['start'], loop['end'], loop.get('active', True))
            self.tree.addTopLevelItem(item)
            item.setup_ui(self.tree)
            item.start_spin.valueChanged.connect(self._on_spin_changed)
            item.end_spin.valueChanged.connect(self._on_spin_changed)
        for col in range(3):
            self.tree.resizeColumnToContents(col)
        self._updating = False
        self.loops_changed.emit(self.get_loops())

    def get_loops(self):
        """Return list of loop dicts in chronological order."""
        return [
            self.tree.topLevelItem(i).to_dict()
            for i in range(self.tree.topLevelItemCount())
        ]

    def add_loop(self, current_time):
        """Add a new active loop starting at current_time with a 4-second duration."""
        start = max(0.0, current_time)
        loops = self.get_loops()
        loops.append({'start': start, 'end': start + 4.0, 'active': True})
        loops.sort(key=lambda l: l['start'])
        self._populate(loops)
        self._save()

    def _on_remove(self):
        for item in self.tree.selectedItems():
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(item))
        self._save()
        self.loops_changed.emit(self.get_loops())

    def _on_item_changed(self, item, column):
        if not self._updating:
            self._save()
            self.loops_changed.emit(self.get_loops())

    def _on_spin_changed(self):
        if not self._updating:
            self._save()
            self.loops_changed.emit(self.get_loops())

    def _save(self):
        if self.song_info is not None:
            self.song_info.update_settings(loops=self.get_loops())


class LoopItem(QtWidgets.QTreeWidgetItem):
    """A single loop region entry in the LoopList tree."""

    def __init__(self, start, end, active=True):
        super().__init__([''])
        self.setFlags(self.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        self.setCheckState(0, QtCore.Qt.CheckState.Checked if active else QtCore.Qt.CheckState.Unchecked)

        self.start_spin = QtWidgets.QDoubleSpinBox()
        self.start_spin.setRange(0, 99999)
        self.start_spin.setDecimals(1)
        self.start_spin.setSingleStep(0.1)
        self.start_spin.setSuffix('s')
        self.start_spin.setValue(start)

        self.end_spin = QtWidgets.QDoubleSpinBox()
        self.end_spin.setRange(0, 99999)
        self.end_spin.setDecimals(1)
        self.end_spin.setSingleStep(0.1)
        self.end_spin.setSuffix('s')
        self.end_spin.setValue(end)

    def setup_ui(self, tree):
        tree.setItemWidget(self, 1, self.start_spin)
        tree.setItemWidget(self, 2, self.end_spin)

    def to_dict(self):
        return {
            'start': self.start_spin.value(),
            'end': self.end_spin.value(),
            'active': self.checkState(0) == QtCore.Qt.CheckState.Checked,
        }
