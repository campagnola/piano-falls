from .qt import QtWidgets, QtCore


class TagPickerWidget(QtWidgets.QWidget):
    """
    Popup widget for selecting and managing tags for a song.

    Displays all available tags as checkboxes in a hierarchical tree, grouping
    tags that contain "/" under a category node named by the prefix before "/".
    Includes a text field at the bottom to type and add new tags to the global list.

    Emits tags_changed with the updated sorted tag list on every checkbox toggle
    or new-tag addition.
    """

    tags_changed = QtCore.Signal(list)

    def __init__(self, all_tags, current_tags, parent=None):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.current_tags = set(current_tags)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        layout.addWidget(self.tree)

        self.new_tag_input = QtWidgets.QLineEdit()
        self.new_tag_input.setPlaceholderText('Add new tag...')
        self.new_tag_input.returnPressed.connect(self._on_new_tag_submitted)
        layout.addWidget(self.new_tag_input)

        self._populate(all_tags)
        self.tree.expandAll()
        self.tree.itemChanged.connect(self._on_item_changed)

        self.setStyleSheet("""
            TagPickerWidget {
                background-color: white;
                border: 2px solid #555;
                border-radius: 4px;
            }
        """)
        self.setFixedSize(240, 300)

    def _populate(self, all_tags):
        """Rebuild the tag tree from the given list of tag names."""
        categories = {}  # category prefix -> [full_tag_name, ...]
        top_level_tags = []

        for tag in sorted(all_tags):
            if '/' in tag:
                category = tag.split('/', 1)[0]
                categories.setdefault(category, []).append(tag)
            else:
                top_level_tags.append(tag)

        with QtCore.QSignalBlocker(self.tree):
            self.tree.clear()

            for tag in top_level_tags:
                self.tree.addTopLevelItem(self._make_tag_item(tag, tag))

            for category in sorted(categories):
                cat_item = QtWidgets.QTreeWidgetItem([category])
                cat_item.setData(0, QtCore.Qt.UserRole, None)  # not a tag itself
                self.tree.addTopLevelItem(cat_item)
                for tag in categories[category]:
                    leaf = tag.split('/', 1)[1]
                    cat_item.addChild(self._make_tag_item(leaf, tag))

    def _make_tag_item(self, label, full_tag):
        """Create a checkable tree item for a tag."""
        item = QtWidgets.QTreeWidgetItem([label])
        item.setData(0, QtCore.Qt.UserRole, full_tag)
        state = QtCore.Qt.Checked if full_tag in self.current_tags else QtCore.Qt.Unchecked
        item.setCheckState(0, state)
        return item

    def _on_item_changed(self, item, column):
        """Update current_tags when a checkbox is toggled and emit the change."""
        full_tag = item.data(0, QtCore.Qt.UserRole)
        if full_tag is None:
            return
        if item.checkState(0) == QtCore.Qt.Checked:
            self.current_tags.add(full_tag)
        else:
            self.current_tags.discard(full_tag)
        self.tags_changed.emit(sorted(self.current_tags))

    def _on_new_tag_submitted(self):
        """Add the typed tag to the global list, select it, and refresh the tree."""
        from .config import config
        tag = self.new_tag_input.text().strip()
        if not tag:
            return
        self.new_tag_input.clear()
        config.add_tag(tag)
        self.current_tags.add(tag)
        self._populate(config.get_all_tags())
        self.tree.expandAll()
        self.tags_changed.emit(sorted(self.current_tags))

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)
