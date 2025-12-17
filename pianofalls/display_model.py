"""
DisplayModel - Central source of truth for what to display.

This module provides a unified interface for both Qt and RPi renderers to determine
which events should be displayed and how they should appear, eliminating duplication
of track filtering, color lookup, and visibility logic.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from qtpy import QtCore
from .song import Event, Note, Barline
from .keyboard import Keyboard


@dataclass
class DisplayEvent:
    """
    Immutable rendering metadata for a single event.
    All renderers consume this - no further filtering/lookup needed.
    """
    # Source data
    event: Event  # Reference to original Note/Barline/etc

    # Display metadata
    color: Tuple[int, int, int]  # RGB color (pre-looked-up from track_colors)
    visible: bool  # False if track_mode == 'hidden'
    played: bool  # Cached from event.played (for RPi white line)

    # Geometry (scene coordinates, renderer-agnostic)
    x_pos: float  # Horizontal position (from Keyboard.key_spec)
    y_start: float  # Vertical start (event.start_time)
    width: float  # Note width (from key_spec)
    height: float  # Note duration

    # Track info (for debugging/future use)
    track_key: Optional[Tuple]  # (part, staff)
    track_mode: Optional[str]  # 'player', 'autoplay', 'visual only', 'hidden'


class DisplayModel(QtCore.QObject):
    """
    Single source of truth for what to display.
    Transforms Song + track settings into DisplayEvent objects.

    This eliminates duplication between Qt and RPi renderers by centralizing:
    - Track mode filtering (hidden tracks)
    - Color lookup
    - Geometry calculation
    - Visibility decisions
    """

    # Signals
    display_events_changed = QtCore.Signal()  # Emitted when any data changes

    def __init__(self):
        super().__init__()

        # Input state
        self._song = None
        self._track_modes = {}  # {(part, staff): 'player'/'autoplay'/etc}
        self._track_colors = {}  # {(part, staff): (r, g, b)}

        # Output cache
        self._display_events = []  # List of DisplayEvent
        self._display_events_by_id = {}  # Map event.index -> DisplayEvent for fast lookup
        self._keyboard_spec = Keyboard.key_spec()  # Cache key geometry

    # === Setters (invalidate cache, emit signal) ===

    def set_song(self, song):
        """Set the song to display."""
        self._song = song
        self._rebuild_display_events()

    def set_track_modes(self, track_modes):
        """
        Set track modes for all tracks.

        Args:
            track_modes: dict mapping (part, staff) -> mode string
                         where mode is one of: 'player', 'autoplay', 'visual only', 'hidden'
        """
        self._track_modes = track_modes
        self._rebuild_display_events()

    def set_track_colors(self, track_colors):
        """
        Set colors for all tracks.

        Args:
            track_colors: dict mapping (part, staff) -> (r, g, b) tuple
        """
        self._track_colors = track_colors
        self._rebuild_display_events()

    # === Getters ===

    def get_display_events(self, time_range=None):
        """
        Get all display events, optionally filtered by time range.

        Uses the Song's optimized bin-based lookup for performance.

        Args:
            time_range: Optional tuple (start_time, end_time) to filter events.
                        If None, returns all events.

        Returns:
            List of DisplayEvent objects (includes hidden events)
        """
        if time_range is None:
            return self._display_events

        if self._song is None:
            return []

        # Use Song's efficient bin-based lookup to get events in time range
        song_events = self._song.get_events_active_in_range(time_range)

        # Map to DisplayEvents using our lookup table
        display_events = []
        for event in song_events:
            if hasattr(event, 'index') and event.index in self._display_events_by_id:
                display_events.append(self._display_events_by_id[event.index])

        return display_events

    def get_visible_events(self, time_range=None):
        """
        Get only visible events (track_mode != 'hidden').

        Args:
            time_range: Optional tuple (start_time, end_time) to filter events.

        Returns:
            List of DisplayEvent objects with visible=True
        """
        events = self.get_display_events(time_range)
        return [evt for evt in events if evt.visible]

    # === Internal ===

    def _rebuild_display_events(self):
        """Rebuild entire display event cache and emit signal."""
        if self._song is None:
            self._display_events = []
            self._display_events_by_id = {}
            self.display_events_changed.emit()
            return

        events = []
        events_by_id = {}
        for song_event in self._song.events:
            # Handle different event types
            if isinstance(song_event, Note):
                display_evt = self._create_note_display_event(song_event)
                if display_evt is not None:
                    events.append(display_evt)
                    if hasattr(song_event, 'index'):
                        events_by_id[song_event.index] = display_evt
            elif isinstance(song_event, Barline):
                display_evt = self._create_barline_display_event(song_event)
                if display_evt is not None:
                    events.append(display_evt)
                    if hasattr(song_event, 'index'):
                        events_by_id[song_event.index] = display_evt
            # Other event types (TempoChange, etc.) are not displayed

        self._display_events = events
        self._display_events_by_id = events_by_id
        self.display_events_changed.emit()

    def _create_note_display_event(self, note):
        """Create a DisplayEvent for a Note."""
        # Check pitch is valid
        if note.pitch is None:
            return None
        if note.pitch.key < 0 or note.pitch.key >= len(self._keyboard_spec):
            return None  # Out of 88-key range

        # Get track metadata
        track_key = note.track  # Uses Note.track property: (part, staff)
        track_mode = self._track_modes.get(track_key, 'player')
        color = self._track_colors.get(track_key, (100, 100, 100))

        # Determine visibility
        visible = (track_mode != 'hidden')

        # Get geometry from keyboard spec
        keyspec = self._keyboard_spec[note.pitch.key]

        # Get played state
        played = getattr(note, 'played', False)

        # Create DisplayEvent
        return DisplayEvent(
            event=note,
            color=color,
            visible=visible,
            played=played,
            x_pos=keyspec['x_pos'],
            y_start=note.start_time,
            width=keyspec['width'],
            height=max(note.duration, 0.1),  # Min duration for visibility
            track_key=track_key,
            track_mode=track_mode,
        )

    def _create_barline_display_event(self, barline):
        """Create a DisplayEvent for a Barline."""
        # Barlines are always visible and span the full keyboard width
        return DisplayEvent(
            event=barline,
            color=(100, 100, 100),  # Gray
            visible=True,  # Always visible
            played=False,  # N/A for barlines
            x_pos=0,
            y_start=barline.start_time,
            width=88,  # Full keyboard width
            height=0,  # Line (no height)
            track_key=None,
            track_mode=None,
        )
