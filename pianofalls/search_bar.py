from .qt import QtWidgets, QtCore


def parse_search_query(text):
    """
    Parse a comma-separated search string into structured filters.

    Supported token syntax:
      rating>=N   minimum rating (0-10 scale)
      rating<=N   maximum rating
      rating=N    exact rating
      tag:NAME    tag filter (matches full tag or leaf name, case-insensitive)
      plain text  filename substring match (case-insensitive)

    Returns a dict with keys:
      'text'       list of lowercase text terms
      'rating_min' int or None
      'rating_max' int or None
      'tags'       list of lowercase tag strings
    """
    filters = {'text': [], 'rating_min': None, 'rating_max': None, 'tags': []}
    for token in text.split(','):
        token = token.strip()
        if not token:
            continue
        lower = token.lower()
        if lower.startswith('rating>='):
            try:
                filters['rating_min'] = int(lower[8:])
            except ValueError:
                pass
        elif lower.startswith('rating<='):
            try:
                filters['rating_max'] = int(lower[8:])
            except ValueError:
                pass
        elif lower.startswith('rating='):
            try:
                val = int(lower[7:])
                filters['rating_min'] = val
                filters['rating_max'] = val
            except ValueError:
                pass
        elif lower.startswith('tag:'):
            tag = token[4:].strip()
            if tag:
                filters['tags'].append(tag.lower())
        else:
            filters['text'].append(lower)
    return filters


def build_search_string(text_terms, rating_min, tags):
    """Build a comma-separated search string from structured filter components."""
    parts = list(text_terms)
    if rating_min is not None and rating_min > 0:
        parts.append(f'rating>={rating_min}')
    for tag in tags:
        parts.append(f'tag:{tag}')
    return ','.join(parts)


class SearchFilterPanel(QtWidgets.QWidget):
    """
    Popup panel for constructing search filters via GUI controls.

    Contains a rating slider (sets a minimum-rating filter) and a tag checklist.
    Writes filter tokens directly into the parent SearchBar's line edit.
    """

    def __init__(self, search_bar, parent=None):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.search_bar = search_bar

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Rating slider
        self.rating_label = QtWidgets.QLabel('Rating: any')
        layout.addWidget(self.rating_label)

        self.rating_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.rating_slider.setMinimum(0)
        self.rating_slider.setMaximum(10)
        self.rating_slider.setValue(0)
        self.rating_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.rating_slider.setTickInterval(2)
        layout.addWidget(self.rating_slider)

        # Tags checklist
        layout.addWidget(QtWidgets.QLabel('Tags:'))
        self.tag_list = QtWidgets.QListWidget()
        layout.addWidget(self.tag_list)

        self.setStyleSheet("""
            SearchFilterPanel {
                background-color: white;
                border: 2px solid #555;
                border-radius: 4px;
            }
        """)
        self.setFixedSize(260, 240)

        # Connect signals before populating; populate uses QSignalBlocker internally
        self.rating_slider.valueChanged.connect(self._on_rating_changed)
        self.tag_list.itemChanged.connect(self._on_tags_changed)

        self._populate_from_search()

    def _populate_from_search(self):
        """Pre-populate controls to reflect the current search bar text."""
        from .config import config
        current_text = self.search_bar.line_edit.text()
        filters = parse_search_query(current_text)

        with QtCore.QSignalBlocker(self.rating_slider):
            self.rating_slider.setValue(filters['rating_min'] or 0)
        self._update_rating_label(self.rating_slider.value())

        all_tags = list(config.get_all_tags())
        with QtCore.QSignalBlocker(self.tag_list):
            self.tag_list.clear()
            for tag in all_tags:
                item = QtWidgets.QListWidgetItem(tag)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                leaf = tag.rsplit('/', 1)[-1].lower()
                checked = tag.lower() in filters['tags'] or leaf in filters['tags']
                item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
                self.tag_list.addItem(item)

    def _update_rating_label(self, value):
        if value == 0:
            self.rating_label.setText('Rating: any')
        else:
            from .rating_widget import rating_to_stars
            self.rating_label.setText(f'Rating ≥ {rating_to_stars(value)}')

    def _on_rating_changed(self, value):
        self._update_rating_label(value)
        self._update_search()

    def _on_tags_changed(self, item):
        self._update_search()

    def _update_search(self):
        """Reconstruct the search string from current controls and push it to the search bar."""
        current_text = self.search_bar.line_edit.text()
        filters = parse_search_query(current_text)

        rating_val = self.rating_slider.value()
        filters['rating_min'] = rating_val if rating_val > 0 else None

        tags = []
        for i in range(self.tag_list.count()):
            list_item = self.tag_list.item(i)
            if list_item.checkState() == QtCore.Qt.Checked:
                tags.append(list_item.text().lower())
        filters['tags'] = tags

        new_text = build_search_string(filters['text'], filters['rating_min'], filters['tags'])
        self.search_bar.line_edit.setText(new_text)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)


class SearchBar(QtWidgets.QWidget):
    """
    Search bar with a filter-panel button for the file tree.

    The text input accepts comma-separated search tokens:
      rating>=N        show files with rating at or above N (0-10 scale)
      tag:NAME         show files tagged with NAME (full name or leaf match)
      plain text       show files whose filename contains the text

    Multiple tokens are AND-combined. The hamburger (☰) button opens a panel
    for constructing rating and tag filters via GUI controls.

    Emits search_changed(str) whenever the search text changes.
    """

    search_changed = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.line_edit = QtWidgets.QLineEdit()
        self.line_edit.setPlaceholderText('Search... (e.g. rating>=4,tag:beginner)')
        self.line_edit.setClearButtonEnabled(True)
        self.line_edit.textChanged.connect(self.search_changed)
        layout.addWidget(self.line_edit)

        self.menu_button = QtWidgets.QPushButton('☰')  # ☰
        self.menu_button.setFixedSize(28, 28)
        self.menu_button.setToolTip('Filter options')
        self.menu_button.clicked.connect(self._show_filter_panel)
        layout.addWidget(self.menu_button)

    def _show_filter_panel(self):
        panel = SearchFilterPanel(self, parent=self)
        # Position panel below the button, right-aligned to button's right edge
        btn_global = self.menu_button.mapToGlobal(QtCore.QPoint(0, self.menu_button.height()))
        panel.move(btn_global.x() - panel.width() + self.menu_button.width(), btn_global.y())
        panel.show()
