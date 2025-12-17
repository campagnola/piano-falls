import os
import pathlib
import shutil

from .config import config, default_song_config
from .qt import QtWidgets


def _normalize_path(path):
    """Return a fully expanded absolute pathlib.Path for the provided path-like value.

    Parameters
    ----------
    path : str or pathlib.Path
        Path-like object to normalize.

    Returns
    -------
    pathlib.Path
        Expanded absolute path.
    """
    if isinstance(path, pathlib.Path):
        result = path
    else:
        result = pathlib.Path(str(path))
    return pathlib.Path(os.path.abspath(os.path.expanduser(str(result))))


def _is_within(path, directory):
    """Return True when path is inside directory (respecting symlinks / real paths).

    Parameters
    ----------
    path : pathlib.Path
        Path to evaluate.
    directory : pathlib.Path
        Potential parent directory.

    Returns
    -------
    bool
        True when ``path`` is within ``directory``.
    """
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _delete_path(path, parent):
    """Delete the given file/directory and raise a UI error message if it fails.

    Parameters
    ----------
    path : pathlib.Path
        Target to delete.
    parent : QtWidgets.QWidget or None
        Parent widget for the message box.

    Returns
    -------
    bool
        True when deletion succeeded.
    """
    try:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        return True
    except OSError as exc:
        QtWidgets.QMessageBox.critical(
            parent,
            'Delete Failed',
            f"Could not delete '{path}'.\n{exc}"
        )
        return False


def _prompt_duplicate(parent, new_path, existing_path):
    """Inform the user about duplicate song hashes and ask which copy to keep.

    Parameters
    ----------
    parent : QtWidgets.QWidget or None
        Parent widget for the prompt.
    new_path : pathlib.Path
        File that triggered the duplicate detection.
    existing_path : pathlib.Path
        File already tracked with the same hash.

    Returns
    -------
    str
        Either ``'delete_existing'`` or ``'keep_both'`` depending on the user's choice.
    """
    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Warning)
    box.setWindowTitle('Duplicate Song Detected')
    box.setText(
        f"A song with the same contents is already tracked at:\n"
        f"{existing_path}\n\n"
        f"New file:\n{new_path}\n\n"
        "Which version should be kept?"
    )
    delete_existing = box.addButton('Delete Tracked File', QtWidgets.QMessageBox.AcceptRole)
    keep_both = box.addButton('Keep Both', QtWidgets.QMessageBox.RejectRole)
    box.setDefaultButton(keep_both)
    box.exec()

    clicked = box.clickedButton()
    if clicked is delete_existing:
        return 'delete_existing'
    return 'keep_both'


def register_file(path, parent=None):
    """Ensure the registry knows about path, handling duplicates and stale entries.

    Parameters
    ----------
    path : str or pathlib.Path
        File to register.
    parent : QtWidgets.QWidget or None, optional
        Parent widget for dialogs.
    """
    path = _normalize_path(path)
    if not path.exists() or not path.is_file():
        return

    try:
        sha = config.get_sha(str(path))
    except OSError:
        return

    entry = config.songs_by_sha.get(sha)
    if entry is None:
        new_entry = default_song_config.copy()
        new_entry.update({
            'sha': sha,
            'filename': str(path),
            'name': path.stem,
        })
        config.data.setdefault('songs', []).append(new_entry)
        config.songs_by_sha[sha] = new_entry
        config.save()
        return

    existing_filename = entry.get('filename')
    normalized_existing = _normalize_path(existing_filename) if existing_filename else None

    if normalized_existing == path:
        if existing_filename != str(path):
            entry['filename'] = str(path)
            config.save()
        return

    if normalized_existing and normalized_existing.exists():
        decision = _prompt_duplicate(parent, path, normalized_existing)
        if decision == 'delete_existing':
            if _delete_path(normalized_existing, parent):
                entry['filename'] = str(path)
                config.save()
        return

    entry['filename'] = str(path)
    config.save()


def handle_move(old_path, new_path, parent=None):
    """Refresh registry metadata after a filesystem move/rename.

    Parameters
    ----------
    old_path : str or pathlib.Path or None
        Previous location of the file, if known.
    new_path : str or pathlib.Path
        New location of the file.
    parent : QtWidgets.QWidget or None, optional
        Parent widget for dialogs.
    """
    new_path = _normalize_path(new_path)
    if new_path.exists() and new_path.is_file():
        register_file(new_path, parent)


def handle_delete(path, was_directory=False):
    """Remove any registry entries that reference a deleted file or directory tree.

    Parameters
    ----------
    path : str or pathlib.Path
        Deleted file or directory.
    was_directory : bool, optional
        True when ``path`` represented a directory (so descendants must be removed).
    """
    path = _normalize_path(path)
    songs = config.data.get('songs', [])
    if not songs:
        return

    remaining = []
    removed = False
    for song in songs:
        filename = song.get('filename')
        if not filename:
            remaining.append(song)
            continue
        song_path = _normalize_path(filename)
        should_remove = song_path == path
        if not should_remove and was_directory:
            should_remove = _is_within(song_path, path)
        if should_remove:
            removed = True
            sha = song.get('sha')
            if sha:
                config.songs_by_sha.pop(sha, None)
            continue
        remaining.append(song)

    if removed:
        config.data['songs'] = remaining
        config.save()
