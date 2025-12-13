import os
import pathlib
import shutil
from .qt import QtCore, QtWidgets
from .file_registry import handle_delete, handle_move


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
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)

        self.rename_action = QtWidgets.QAction('Rename', self)
        self.delete_action = QtWidgets.QAction('Delete', self)
        self.rename_action.triggered.connect(self.trigger_rename)
        self.delete_action.triggered.connect(self.trigger_delete)

        self._drag_item = None
        self._hidden_during_drag = []

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
        self.setCurrentItem(item)
        menu = QtWidgets.QMenu(self)
        menu.addAction(self.rename_action)
        menu.addAction(self.delete_action)
        menu.exec(event.globalPos())

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            if isinstance(self.currentItem(), FileTreeItem):
                self.trigger_delete()
                return
        elif event.key() == QtCore.Qt.Key_F2:
            if isinstance(self.currentItem(), FileTreeItem):
                self.trigger_rename()
                return
        super().keyPressEvent(event)

    def trigger_rename(self):
        item = self.currentItem()
        if isinstance(item, FileTreeItem):
            self.scrollToItem(item)
            self.editItem(item, 0)

    def trigger_delete(self):
        item = self.currentItem()
        if not isinstance(item, FileTreeItem):
            return
        deleted_path = pathlib.Path(item.path)
        was_directory = deleted_path.is_dir()

        response = QtWidgets.QMessageBox.question(
            self,
            'Confirm Delete',
            f"Delete '{item.path.name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if response != QtWidgets.QMessageBox.Yes:
            return

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
            return

        handle_delete(deleted_path, was_directory=was_directory)
        self._remove_item(item)

    def _remove_item(self, item):
        parent = item.parent()
        if parent is None:
            index = self.indexOfTopLevelItem(item)
            self.takeTopLevelItem(index)
        else:
            parent.removeChild(item)

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

    def dragEnterEvent(self, event):
        if self._drag_item is not None or event.source() is self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._drag_item is not None or event.source() is self:
            event.acceptProposedAction()
        else:
            event.ignore()

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not isinstance(item, FileTreeItem):
            return
        self._drag_item = item
        self._apply_drag_visibility(hide=True)
        try:
            super().startDrag(supportedActions)
        finally:
            self._apply_drag_visibility(hide=False)
            self._drag_item = None

    def dropEvent(self, event):
        if not isinstance(self._drag_item, FileTreeItem):
            event.ignore()
            return

        target_item = self._target_item_from_event(event)
        if target_item is None:
            event.ignore()
            return

        target_dir_item = self._resolve_drop_directory(target_item)
        if target_dir_item is None:
            event.ignore()
            return

        if self._is_descendant(self._drag_item, target_dir_item):
            QtWidgets.QMessageBox.warning(
                self,
                'Move Not Allowed',
                'Cannot move a folder into one of its subfolders.'
            )
            event.ignore()
            return

        source_path = self._drag_item.path
        source_was_directory = source_path.is_dir()
        destination_path = target_dir_item.path / source_path.name

        if destination_path == source_path:
            event.ignore()
            return

        if destination_path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                'Move Not Allowed',
                f"'{destination_path.name}' already exists in the destination."
            )
            event.ignore()
            return

        confirmation = QtWidgets.QMessageBox.question(
            self,
            'Confirm Move',
            f"Move '{source_path.name}' to '{target_dir_item.path}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if confirmation != QtWidgets.QMessageBox.Yes:
            event.ignore()
            return

        try:
            shutil.move(str(source_path), str(destination_path))
        except OSError as exc:
            QtWidgets.QMessageBox.critical(
                self,
                'Move Failed',
                f"Could not move '{source_path}' to '{target_dir_item.path}'.\n{exc}"
            )
            event.ignore()
            return

        moved_item = self._drag_item
        self._remove_item(moved_item)
        self._update_paths_after_move(moved_item, source_path, destination_path, source_was_directory)

        if isinstance(target_dir_item, FileTreeItem):
            target_dir_item.addChild(moved_item)
            if not target_dir_item._children_loaded:
                target_dir_item.load_children()
            self.setCurrentItem(moved_item)
        else:
            new_item = FileTreeItem(destination_path)
            self.addTopLevelItem(new_item)
            self.setCurrentItem(new_item)

        event.setDropAction(QtCore.Qt.MoveAction)
        event.accept()
        column = self.header().sortIndicatorSection()
        order = self.header().sortIndicatorOrder()
        self.sortItems(column, order)

    def _apply_drag_visibility(self, hide):
        if hide:
            self._hidden_during_drag = []
            if not isinstance(self._drag_item, FileTreeItem):
                return
            for item in self._iter_items():
                if item is self._drag_item:
                    continue
                if not item.path.is_dir() and not item.isHidden():
                    item.setHidden(True)
                    self._hidden_during_drag.append(item)
        else:
            for item in self._hidden_during_drag:
                item.setHidden(False)
            self._hidden_during_drag = []

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

    def _target_item_from_event(self, event):
        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        return self.itemAt(pos)

    def _resolve_drop_directory(self, item):
        if not isinstance(item, FileTreeItem):
            return None
        if item.path.is_dir():
            return item
        parent = item.parent()
        if isinstance(parent, FileTreeItem):
            return parent
        return None

    def _is_descendant(self, potential_parent, potential_child):
        if not isinstance(potential_parent, FileTreeItem):
            return False
        current = potential_child
        while isinstance(current, FileTreeItem):
            if current is potential_parent:
                return True
            current = current.parent()
        return False

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
                    item = FileTreeItem(child_path)
                    self.addChild(item)
                else:
                    item.path = child_path
                    item.setText(0, child_path.name)

        for index in reversed(range(self.childCount())):
            child = self.child(index)
            if isinstance(child, FileTreeItem) and child.path not in seen_paths:
                self.removeChild(child)

    def update_paths(self, old_path, new_path):
        self.path = new_path
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
