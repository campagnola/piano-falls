import os
import pathlib
from .qt import QtCore, QtWidgets


class FileTree(QtWidgets.QTreeWidget):

    file_double_clicked = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self.setHeaderLabels(['File', 'Rating', 'Difficulty', 'Tags'])
        self.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.itemExpanded.connect(self.on_item_expanded)
        self.setEditTriggers(self.SelectedClicked)
        # allow sorting
        self.setSortingEnabled(True)
        self.itemChanged.connect(self.on_item_changed)

    def on_item_double_clicked(self, item, column):
        if item.path.is_file():
            self.file_double_clicked.emit(str(item.path))

    def set_roots(self, roots):
        self.clear()
        for root in roots:
            self.add_root(root)

    def add_root(self, root):
        path = pathlib.Path(os.path.abspath(os.path.expanduser(root)))
        if not path.exists():
            return
        item = FileTreeItem(path)
        self.addTopLevelItem(item)
        item.setExpanded(True)

    def on_item_expanded(self, item):
        item.load_children()

    # if item is edited, rename the file
    def on_item_changed(self, item, column):
        if column == 0:
            new_name = item.text(0)
            new_path = item.path.with_name(new_name)
            item.path.rename(new_path)
            item.path = new_path

class FileTreeItem(QtWidgets.QTreeWidgetItem):
    def __init__(self, path):
        super().__init__()
        self.path = path
        self.setText(0, path.parts[-1])
        flags = self.flags() | QtCore.Qt.ItemFlag.ItemIsEditable
        if self.path.is_dir():
            self._loading_item = QtWidgets.QTreeWidgetItem(['loading..'])
            self.addChild(self._loading_item)
        self.setFlags(flags)
        self._children_loaded = False

    def __lt__(self, other):
        if isinstance(other, FileTreeItem):
            return self.path < other.path
        return super().__lt__(other)
    
    def load_children(self):
        if self._children_loaded:
            return
        self._children_loaded = True
        if not self.path.is_dir():
            return
        
        self.removeChild(self._loading_item)
        for child in sorted(self.path.iterdir()):
            if child.is_dir() or child.suffix in ['.mid', '.midi', '.mxl', '.xml', '.musicxml']:
                item = FileTreeItem(child)
                self.addChild(item)
