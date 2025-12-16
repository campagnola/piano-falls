import queue
import threading, math, time
from .qt import QtCore
import atexit


class TimeScroller(QtCore.QObject):
    current_time_changed = QtCore.Signal(float)

    def __init__(self):
        super().__init__()
        self.current_time = 0.0

        self.song = None

        self.target_time = 0.0  # time to scroll to
        self.scroll_tau = 0.0  # how quickly to scroll to the target time
        self.scroll_speed = 1.0 # how quickly to scroll in song seconds per real second
        self.scrolling = False
        self.scroll_mode = None

        self.set_scroll_mode('wait')

        self.stop_thread = False
        self.thread = threading.Thread(target=self.auto_scroll_loop, daemon=True)
        self.thread.start()
        atexit.register(self.stop)

    def set_scrolling(self, scrolling):
        self.scrolling = scrolling

    def toggle_scrolling(self):
        self.set_scrolling(not self.scrolling)

    def set_song(self, song_info):
        """Set the song from a SongInfo instance."""
        self.song = song_info.get_song()
        self.song_info = song_info
        self.scroll_mode.set_song(self.song)
        self.set_time(-2)
        self.set_scrolling(True)

    def set_scroll_speed(self, speed):
        self.scroll_speed = speed

    def set_scroll_mode(self, mode):
        # Preserve current settings before creating new scroll mode
        old_volume = None
        old_midi_output = None
        if self.scroll_mode is not None:
            old_volume = self.scroll_mode.autoplay_volume
            old_midi_output = self.scroll_mode.midi_output

        # Create new scroll mode
        self.scroll_mode = {
            'tempo': TempoScrollMode,
            'wait': WaitScrollMode,
            'follow': FollowScrollMode,
        }[mode](self)

        # Restore settings to new scroll mode
        if old_volume is not None:
            self.scroll_mode.autoplay_volume = old_volume
        if old_midi_output is not None:
            self.scroll_mode.midi_output = old_midi_output

    def set_track_modes(self, track_modes):
        """Set the track modes for the current scroll mode"""
        if hasattr(self.scroll_mode, 'set_track_modes'):
            self.scroll_mode.set_track_modes(track_modes)

    def set_time(self, time):
        self.current_time = time
        self.target_time = time
        self.scroll_mode.set_time(time)

    def set_target_time(self, time):
        self.target_time = time
        self.scroll_mode.set_time(time)

    def scroll_by(self, delta):
        self.set_time(self.target_time + delta)

    def connect_midi_input(self, midi_input):
        midi_input.message.connect(self.on_midi_message)

    def connect_midi_output(self, midi_output):
        """Connect MIDI output to scroll mode"""
        if hasattr(self.scroll_mode, 'set_midi_output'):
            self.scroll_mode.set_midi_output(midi_output)

    def set_autoplay_volume(self, volume):
        """Set autoplay volume (0.0-1.0)"""
        if hasattr(self.scroll_mode, 'set_autoplay_volume'):
            self.scroll_mode.set_autoplay_volume(volume)

    def on_midi_message(self, midi_input, msg):
        self.scroll_mode.on_midi_message(msg)

    def auto_scroll_loop(self):
        last_time = time.perf_counter()
        while not self.stop_thread:
            now = time.perf_counter()
            dt = now - last_time
            last_time = now

            if self.song is None:
                time.sleep(0.1)
                continue
            
            if self.scrolling:
                self.target_time = self.scroll_mode.update(self.current_time, dt, self.scroll_speed)

            # Exponentially approach target
            if self.scroll_tau > 0:
                self.current_time += (self.target_time - self.current_time) * math.exp(-dt / self.scroll_tau)
            else:
                self.current_time = self.target_time
            self.current_time_changed.emit(self.current_time)

            last_note = self.song.notes[-1]
            if self.current_time > last_note.start_time + last_note.duration:
                self.set_scrolling(False)

            time.sleep(0.003)

    def stop(self):
        self.stop_thread = True
        self.thread.join()


class ScrollMode:
    def __init__(self, scroller):
        self.scroller = scroller
        self.incoming_midi = []

        # Track modes and note tracking
        self.next_note_index = 0
        self.next_autoplay_check_index = 0
        self.early_key_time = 1.0  # seconds before a note is due to be played where a key press will count as a hit
        self.track_modes = {}  # Dictionary mapping track to mode

        # Autoplay settings
        self.midi_output = None
        self.autoplay_volume = 1.0  # 0.0-1.0 scale factor
        self.active_autoplay_notes = {}  # Map note_id -> note object for fast lookup

        self.set_song(self.scroller.song)

    def on_midi_message(self, msg):
        if msg.type in ['note_on', 'note_off']:
            self.incoming_midi.append(msg)

    def set_song(self, song):
        # Stop notes from previous song
        self.stop_all_midi()
        self.song = song
        self.next_note_index = 0
        self.next_autoplay_check_index = 0
        if song is None:
            return
        # mark all notes as unplayed
        self.set_time(0)

    def set_time(self, new_time):
        """Called when the scroller is set to a new time"""
        # Stop active notes before time jump
        self.stop_all_midi()
        self.reset_future_notes_played()

    def check_midi(self):
        """Return all midi messages received since the last call"""
        messages = self.incoming_midi
        self.incoming_midi = []
        return messages

    def set_track_modes(self, track_modes):
        """Set the track modes for this scroll mode"""
        # Stop notes that might be from tracks changing away from autoplay
        self.stop_all_midi()
        self.track_modes = track_modes
        self.reset_future_notes_played()

    def stop_all_midi(self):
        """Stop all active MIDI notes"""
        if self.midi_output is not None:
            self.midi_output.stop_all()
        self.active_autoplay_notes = {}

    def set_midi_output(self, midi_output):
        """Set MIDI output instance"""
        self.midi_output = midi_output

    def set_autoplay_volume(self, volume):
        """Set autoplay volume scale (0.0-1.0)"""
        self.autoplay_volume = volume

    def reset_future_notes_played(self):
        """Reset played state of future notes based on current time and track modes
        Also sets next_note_index to the first note after current time.
        """
        self.next_note_index = self.song.index_of_note_starting_at(self.scroller.target_time)
        self.next_autoplay_check_index = self.next_note_index

        # mark next event + all following events as unplayed, but only for 'player' tracks
        for i, note in enumerate(self.song.notes):
            track_key = (note.part, note.staff)
            track_mode = self.track_modes.get(track_key, 'player')  # default to 'player' mode; saved modes may not have been loaded yet

            # mark note as unplayed if it's in a 'player' track and starts at or after the current time
            note.played = (i < self.next_note_index) or (track_mode != 'player')

    def check_and_mark_played_notes(self, current_time):
        """Check MIDI input and mark matching notes as played.
        Returns list of recent note_on messages.
        """
        recent_messages = self.check_midi()
        recent_presses = [msg for msg in recent_messages if msg.type == 'note_on']

        # check if any recent key presses match upcoming notes
        for msg in recent_presses:
            matched_time = None
            for note in self.song.notes[self.next_note_index:]:
                if note.start_time > current_time + self.early_key_time:
                    # too early to count any key presses toward the next note
                    break
                if note.played:
                    continue
                if note.pitch.midi_note == msg.note:
                    # a key press matches an upcoming note. It only counts if it's the first key press for this note
                    # or if the note is being played at the same time as another that already accepted this key press
                    if matched_time is None or matched_time == note.start_time:
                        note.played = True
                        matched_time = note.start_time

        return recent_presses

    def handle_autoplay(self, new_time):
        """Handle autoplay notes - play and stop notes based on time.
        Should be called after new_time is determined.
        """
        if self.midi_output is None:
            return

        # Play autoplay notes whose start_time has been passed
        while (self.next_autoplay_check_index < len(self.song.notes) and
               self.song.notes[self.next_autoplay_check_index].start_time < new_time):
            note = self.song.notes[self.next_autoplay_check_index]
            track_key = (note.part, note.staff)
            track_mode = self.track_modes.get(track_key, 'player')

            if track_mode == 'autoplay':
                self.midi_output.note_on(note, self.autoplay_volume)
                self.active_autoplay_notes[id(note)] = note

            self.next_autoplay_check_index += 1

        # Stop autoplay notes whose end_time has been reached
        for note_id, note in list(self.active_autoplay_notes.items()):
            end_time = note.start_time + note.duration
            if end_time <= new_time:
                self.midi_output.note_off(note)
                self.active_autoplay_notes.pop(id(note), None)

    def update(self, current_time, dt, scroll_speed):
        """Called periodically to update the current time

        Returns the new current time"""
        raise NotImplementedError()


class TempoScrollMode(ScrollMode):
    """Scroll at constant speed"""
    def update(self, current_time, dt, scroll_speed):
        # Check for recent midi input and mark notes as played
        self.check_and_mark_played_notes(current_time)

        # Calculate new time at constant tempo (no waiting)
        new_time = current_time + dt * scroll_speed

        # Mark notes as played once they've passed (for player tracks only)
        # This ensures missed notes are marked as played in tempo mode
        while self.next_note_index < len(self.song.notes):
            note = self.song.notes[self.next_note_index]
            if note.start_time < new_time:
                track_key = (note.part, note.staff)
                track_mode = self.track_modes.get(track_key, 'player')
                # Mark as played if it's a player track (autoplay tracks are already marked)
                if track_mode == 'player':
                    note.played = True
                self.next_note_index += 1
            else:
                break

        # Handle autoplay notes
        self.handle_autoplay(new_time)

        return new_time
    

class WaitScrollMode(ScrollMode):
    """Wait for the next note to be played before scrolling"""

    def update(self, current_time, dt, scroll_speed):
        # Check for recent midi input and mark notes as played
        self.check_and_mark_played_notes(current_time)

        if self.next_note_index is None:
            return current_time

        # Advance next_note_index to the first unplayed note
        for i in range(self.next_note_index, len(self.song)):
            if self.song.notes[i].played:
                self.next_note_index = i + 1
            else:
                break

        # Calculate max_time based on next unplayed note
        if self.next_note_index >= len(self.song):
            max_time = self.song.end_time
        else:
            max_time = self.song.notes[self.next_note_index].start_time

        # Calculate new time, but don't advance past next unplayed note
        desired_time = current_time + dt * scroll_speed
        new_time = min(desired_time, max_time)

        # Handle autoplay notes
        self.handle_autoplay(new_time)

        return new_time


class FollowScrollMode(ScrollMode):
    def update(self, current_time, dt, scroll_speed):
        self.check_midi()

        recent_keys = {msg.note:msg for msg in self.recent_midi if msg.type == 'note_on'}
        # use BLAST to predict where we are in the song, based on recent midi input events
        return current_time + dt * scroll_speed
    

