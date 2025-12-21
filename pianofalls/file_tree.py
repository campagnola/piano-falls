import os
import pathlib
import shutil
from .qt import QtCore, QtWidgets, QtGui
from .file_registry import handle_delete, handle_move
from .file_stability_monitor import FileStabilityMonitor


class FileTree(QtWidgets.QTreeWidget):

    file_double_clicked = QtCore.Signal(str)

    def __init__(self):
        super().__init__()
        self.setHeaderLabels(['File', 'Rating', 'Difficulty', 'Tags'])
        self.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.itemExpanded.connect(self.on_item_expanded)
        self.itemClicked.connect(self.on_item_clicked)
        self.setEditTriggers(self.EditKeyPressed)
        # allow sorting
        self.setSortingEnabled(True)
        self.itemChanged.connect(self.on_item_changed)
        # enable multi-selection
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.rename_action = QtWidgets.QAction('Rename', self)
        self.delete_action = QtWidgets.QAction('Delete', self)
        self.move_to_action = QtWidgets.QAction('Move to...', self)
        self.rename_action.triggered.connect(self.trigger_rename)
        self.delete_action.triggered.connect(self.trigger_delete)

        self.file_watcher = QtCore.QFileSystemWatcher()
        self.stability_monitor = FileStabilityMonitor()
        self.file_watcher.directoryChanged.connect(self.stability_monitor.notify_directory_changed)
        self.stability_monitor.directory_stable.connect(self._on_directory_stable)

    def on_item_double_clicked(self, item, column):
        if item.path.is_file():
            self.file_double_clicked.emit(str(item.path))

    def on_item_clicked(self, item, column):
        """Show rating widget when clicking column 1."""
        if column == 1 and isinstance(item, FileTreeItem) and item.path.is_file():
            self._show_rating_widget(item)

    def _show_rating_widget(self, item):
        """Show rating popup for item."""
        from .rating_widget import RatingWidget
        from .song_info import SongInfo

        try:
            song_info = SongInfo.load(str(item.path), parent=self)
            current_rating = song_info.get_setting('rating')
        except Exception:
            return

        widget = RatingWidget(current_rating, parent=self)

        def on_rating_changed(new_rating):
            song_info.update_settings(rating=new_rating)
            item._update_rating_display()

        widget.rating_changed.connect(on_rating_changed)

        # Position near cursor
        cursor_pos = QtGui.QCursor.pos()
        widget.move(cursor_pos.x() + 10, cursor_pos.y() + 10)
        widget.show()

    def set_roots(self, roots):
        self.clear()
        for root in roots:
            self.add_root(root)

    def add_root(self, root):
        path = pathlib.Path(os.path.abspath(os.path.expanduser(root)))
        if not path.exists():
            return
        item = FileTreeItem(path, self.file_watcher)
        self.addTopLevelItem(item)
        item.setExpanded(True)
        self.resizeColumnToContents(0)

    def on_item_expanded(self, item):
        item.load_children()

    # if item is edited, rename the file
    def on_item_changed(self, item, column):
        if column == 0:
            new_name = item.text(0).strip()
            if not new_name or new_name == item.path.name:
                with QtCore.QSignalBlocker(self):
                    item.setText(0, item.path.name)
                return

            new_path = item.path.with_name(new_name)
            if new_path.exists():
                QtWidgets.QMessageBox.warning(
                    self,
                    'Rename Failed',
                    f"A file or directory named '{new_name}' already exists."
                )
                with QtCore.QSignalBlocker(self):
                    item.setText(0, item.path.name)
                return

            old_path = item.path
            old_was_directory = old_path.is_dir()
            try:
                old_path.rename(new_path)
            except OSError as exc:
                QtWidgets.QMessageBox.critical(
                    self,
                    'Rename Failed',
                    f"Could not rename '{old_path.name}' to '{new_name}'.\n{exc}"
                )
                with QtCore.QSignalBlocker(self):
                    item.setText(0, item.path.name)
                return

            self._update_paths_after_move(item, old_path, new_path, old_was_directory)

    def contextMenuEvent(self, event):
        item = self.itemAt(event.pos())
        if not isinstance(item, FileTreeItem):
            return

        # Get all selected items
        selected_items = [item for item in self.selectedItems() if isinstance(item, FileTreeItem)]
        if not selected_items:
            return

        menu = QtWidgets.QMenu(self)

        # Only show rename for single selection
        if len(selected_items) == 1:
            menu.addAction(self.rename_action)

        menu.addAction(self.delete_action)

        # Add "Move to..." submenu with folder hierarchy
        move_menu = self._build_move_to_menu(selected_items)
        if move_menu is not None:
            menu.addMenu(move_menu)

        menu.exec(event.globalPos())

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            # Check if any selected items are FileTreeItem
            if any(isinstance(item, FileTreeItem) for item in self.selectedItems()):
                self.trigger_delete()
                return
        elif event.key() == QtCore.Qt.Key_F2:
            # Check if any selected items are FileTreeItem
            if any(isinstance(item, FileTreeItem) for item in self.selectedItems()):
                self.trigger_rename()
                return
        super().keyPressEvent(event)

    def trigger_rename(self):
        # Only allow rename for single selection
        selected = [item for item in self.selectedItems() if isinstance(item, FileTreeItem)]
        if len(selected) != 1:
            return
        item = selected[0]
        self.scrollToItem(item)
        self.editItem(item, 0)

    def trigger_delete(self):
        items = [item for item in self.selectedItems() if isinstance(item, FileTreeItem)]
        if not items:
            return

        # Create confirmation message
        if len(items) == 1:
            message = f"Delete '{items[0].path.name}'?"
        else:
            message = f"Delete {len(items)} items?"

        response = QtWidgets.QMessageBox.question(
            self,
            'Confirm Delete',
            message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if response != QtWidgets.QMessageBox.Yes:
            return

        # Delete all selected items
        for item in items:
            deleted_path = pathlib.Path(item.path)
            was_directory = deleted_path.is_dir()

            try:
                if item.path.is_dir():
                    shutil.rmtree(item.path)
                else:
                    item.path.unlink()
            except OSError as exc:
                QtWidgets.QMessageBox.critical(
                    self,
                    'Delete Failed',
                    f"Could not delete '{item.path}'.\n{exc}"
                )
                continue

            handle_delete(deleted_path, was_directory=was_directory)
            self._remove_item(item)

    def _remove_item(self, item):
        # Remove item and all its descendants from the dictionary
        if isinstance(item, FileTreeItem):
            self._unregister_item_recursive(item)
        parent = item.parent()
        if parent is None:
            index = self.indexOfTopLevelItem(item)
            self.takeTopLevelItem(index)
        else:
            parent.removeChild(item)

    def _unregister_item_recursive(self, item):
        """Remove item and all its children from the class dictionary."""
        if isinstance(item, FileTreeItem):
            FileTreeItem._all_items.pop(item.path, None)
            for index in range(item.childCount()):
                child = item.child(index)
                self._unregister_item_recursive(child)

    def _update_paths_after_move(self, item, old_path, new_path, old_was_directory):
        """Refresh tree item text/paths and sync metadata for a move or rename."""
        if isinstance(item, FileTreeItem):
            item.update_paths(old_path, new_path)
            self._sync_metadata_after_move(
                pathlib.Path(old_path) if old_path is not None else None,
                pathlib.Path(item.path),
                old_was_directory
            )

    def _sync_metadata_after_move(self, old_base_path, new_base_path, old_was_directory):
        """Walk moved content and update the shared registry so hashes map to new paths."""
        new_base_path = pathlib.Path(new_base_path)
        paths_to_process = set()

        if new_base_path.exists():
            if new_base_path.is_dir():
                try:
                    for candidate in new_base_path.rglob('*'):
                        if candidate.is_file() and self._is_supported_file(candidate):
                            paths_to_process.add(candidate)
                except (OSError, PermissionError):
                    pass
            elif new_base_path.is_file() and self._is_supported_file(new_base_path):
                paths_to_process.add(new_base_path)

        if not paths_to_process and new_base_path.is_file() and self._is_supported_file(new_base_path):
            paths_to_process.add(new_base_path)

        if not paths_to_process and old_base_path is not None and not old_was_directory:
            handle_delete(old_base_path, was_directory=old_was_directory)
            return

        for candidate in paths_to_process:
            old_candidate = None
            if old_base_path is not None and new_base_path.is_dir():
                try:
                    relative = candidate.relative_to(new_base_path)
                    old_candidate = old_base_path / relative
                except ValueError:
                    old_candidate = None
            elif old_base_path is not None and not new_base_path.is_dir():
                old_candidate = old_base_path

            handle_move(old_candidate, candidate, parent=self)

    def _is_supported_file(self, path):
        """Return True when the file suffix is one we manage metadata for."""
        return path.suffix.lower() in {'.mid', '.midi', '.mxl', '.xml', '.musicxml'}

    def _on_directory_stable(self, dir_path):
        """Handle filesystem changes after files have stabilized (3 seconds of no size changes)."""
        print(f"Directory stable: {dir_path}")
        changed_path = pathlib.Path(dir_path)

        # Find the tree item corresponding to this directory
        for item in self._iter_items():
            if item.path == changed_path:
                # Reload just this item's children
                item.reload_children()
                break

    def _build_move_to_menu(self, source_items):
        """Build a hierarchical menu showing all valid destination folders."""
        move_menu = QtWidgets.QMenu('Move to...', self)

        def mk_move_callback(source_items, destination_path):
            def callback():
                self._perform_move(source_items, destination_path)
            return callback

        path_menus = {}
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if isinstance(item, FileTreeItem) and item.path.is_dir():
                for (dirpath, dirnames, filenames) in os.walk(item.path):
                    parent_path, name = os.path.split(dirpath)
                    parent_menu = path_menus.get(parent_path, move_menu)
                    callback = mk_move_callback(source_items, pathlib.Path(dirpath))
                    if len(dirnames) == 0:
                        # Add folder as action (immediately move here)
                        action = parent_menu.addAction(name)
                        action.triggered.connect(callback)
                    else:
                        # folder has subfolders; make a tree and add action inside
                        path_menus[dirpath] = submenu = parent_menu.addMenu(name)
                        action = submenu.addAction(f'← Move here')
                        action.triggered.connect(mk_move_callback(source_items, pathlib.Path(dirpath)))
                        submenu.addSeparator()

        return move_menu

    def _perform_move(self, source_items, destination_path):
        """Move source_items into destination_path folder."""
        # Ensure source_items is a list
        if not isinstance(source_items, list):
            source_items = [source_items]

        # Check for conflicts
        conflicts = []
        for item in source_items:
            final_destination = destination_path / item.path.name
            if final_destination.exists():
                conflicts.append(item.path.name)

        if conflicts:
            QtWidgets.QMessageBox.warning(
                self,
                'Move Not Allowed',
                f"The following items already exist in the destination:\n" + "\n".join(conflicts)
            )
            return

        # Create confirmation message
        if len(source_items) == 1:
            message = f"Move '{source_items[0].path.name}' to '{destination_path}'?"
        else:
            message = f"Move {len(source_items)} items to '{destination_path}'?"

        confirmation = QtWidgets.QMessageBox.question(
            self,
            'Confirm Move',
            message,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if confirmation != QtWidgets.QMessageBox.Yes:
            return

        # Move all items
        for item in source_items:
            source_path = item.path
            source_was_directory = source_path.is_dir()
            final_destination = destination_path / source_path.name

            try:
                shutil.move(str(source_path), str(final_destination))
            except OSError as exc:
                QtWidgets.QMessageBox.critical(
                    self,
                    'Move Failed',
                    f"Could not move '{source_path}' to '{destination_path}'.\n{exc}"
                )
                continue

            # Update metadata
            self._update_paths_after_move(item, source_path, final_destination, source_was_directory)

    def _iter_items(self):
        root = self.invisibleRootItem()
        stack = [root]
        while stack:
            current = stack.pop()
            for index in range(current.childCount()):
                child = current.child(index)
                stack.append(child)
                if isinstance(child, FileTreeItem):
                    yield child

    def _is_descendant(self, potential_parent, potential_child):
        """Check if potential_child is a descendant of potential_parent."""
        if not isinstance(potential_parent, FileTreeItem):
            return False
        current = potential_child
        while isinstance(current, FileTreeItem):
            if current is potential_parent:
                return True
            current = current.parent()
        return False

    def search(self, search_text):
        """
        Filter the tree to show only items matching the search text.

        Uses os.walk() to find all matching files across the entire search paths,
        then lazy-loads folders as needed and shows/hides items accordingly.
        """
        search_text = search_text.strip().lower()

        if not search_text:
            # Show all items
            for item in self._iter_items():
                item.setHidden(False)
            return

        # Step 1: Find all matching files using os.walk()
        matching_paths = set()
        for i in range(self.topLevelItemCount()):
            root_item = self.topLevelItem(i)
            if isinstance(root_item, FileTreeItem) and root_item.path.is_dir():
                for dirpath, dirnames, filenames in os.walk(root_item.path):
                    for filename in filenames:
                        if filename.lower().endswith(('.mid', '.midi', '.mxl', '.xml', '.musicxml')):
                            if search_text in filename.lower():
                                file_path = pathlib.Path(dirpath) / filename
                                matching_paths.add(file_path)
                                # Add all parent directories to matching paths
                                parent = file_path.parent
                                while parent != root_item.path.parent:
                                    matching_paths.add(parent)
                                    parent = parent.parent

        # Step 2: Lazy-load and show/hide items
        self._filter_tree(matching_paths)

    def _filter_tree(self, matching_paths):
        """Hide/show items based on matching_paths set."""
        for item in self._iter_items():
            if item.path in matching_paths:
                # This item should be visible
                item.setHidden(False)
                # Ensure parent folders are loaded
                if item.path.is_dir() and not item.children_loaded:
                    item.load_children()
            else:
                # Check if this is a directory that contains matching descendants
                is_ancestor = False
                if item.path.is_dir():
                    for matching_path in matching_paths:
                        try:
                            matching_path.relative_to(item.path)
                            is_ancestor = True
                            break
                        except ValueError:
                            continue

                if is_ancestor:
                    # This directory contains matches, show it and load children
                    item.setHidden(False)
                    if not item.children_loaded:
                        item.load_children()
                else:
                    # No matches, hide this item
                    item.setHidden(True)

class FileTreeItem(QtWidgets.QTreeWidgetItem):
    # Class-level dictionary mapping path -> FileTreeItem
    _all_items = {}

    def __init__(self, path, file_watcher):
        super().__init__()
        self.path = path
        self.file_watcher = file_watcher
        self.setText(0, path.parts[-1])
        flags = self.flags() | QtCore.Qt.ItemFlag.ItemIsEditable
        if self.path.is_dir():
            self._loading_item = QtWidgets.QTreeWidgetItem(['loading..'])
            self.addChild(self._loading_item)
            # Watch this directory for changes
            self.file_watcher.addPath(str(self.path))
        else:
            # Update rating display for files
            self._update_rating_display()
        self.setFlags(flags)
        self.children_loaded = False

        # Register this item in the class-level dictionary
        FileTreeItem._all_items[self.path] = self

    def __lt__(self, other):
        if isinstance(other, FileTreeItem):
            return self.path < other.path
        return super().__lt__(other)
    
    def load_children(self):
        if self.children_loaded:
            return        

        if not self.path.is_dir():
            return

        if getattr(self, '_loading_item', None) is not None:
            try:
                self.removeChild(self._loading_item)
            except RuntimeError:
                pass
            self._loading_item = None

        existing = {}
        for index in range(self.childCount()):
            child = self.child(index)
            if isinstance(child, FileTreeItem):
                existing[child.path] = child

        seen_paths = set()
        for child_path in sorted(self.path.iterdir()):
            if child_path.is_dir() or child_path.suffix in ['.mid', '.midi', '.mxl', '.xml', '.musicxml']:
                seen_paths.add(child_path)
                item = existing.get(child_path)
                if item is None:
                    item = FileTreeItem(child_path, self.file_watcher)
                    self.addChild(item)
                else:
                    item.path = child_path
                    item.setText(0, child_path.name)
                    # Update rating when reloading
                    if child_path.is_file():
                        item._update_rating_display()

        for index in reversed(range(self.childCount())):
            child = self.child(index)
            if isinstance(child, FileTreeItem) and child.path not in seen_paths:
                self.removeChild(child)

        self.children_loaded = True

    def reload_children(self):
        self.children_loaded = False
        self.load_children()

    def update_paths(self, old_path, new_path):
        # Update the dictionary: remove old path and add new path
        FileTreeItem._all_items.pop(old_path, None)
        self.path = new_path
        FileTreeItem._all_items[new_path] = self

        self.setText(0, new_path.name)
        if new_path.is_dir():
            for index in range(self.childCount()):
                child = self.child(index)
                if isinstance(child, FileTreeItem):
                    try:
                        relative = child.path.relative_to(old_path)
                    except ValueError:
                        relative = pathlib.Path(child.path.name)
                    child_new_path = new_path / relative
                    child.update_paths(child.path, child_new_path)

    def _update_rating_display(self):
        """Update the rating column display based on song rating in config."""
        if not self.path.is_file():
            return
        try:
            from .song_info import SongInfo
            from .rating_widget import rating_to_stars
            song_info = SongInfo.load(str(self.path), parent=None)
            rating = song_info.get_setting('rating')
            stars = rating_to_stars(rating)
            # Don't show stars for unrated files in the tree
            self.setText(1, stars if rating > 0 else '')
        except Exception:
            # If file can't be loaded or isn't a valid song, leave blank
            self.setText(1, '')
