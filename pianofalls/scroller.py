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
        self.scroll_mode = {
            'tempo': TempoScrollMode,
            'wait': WaitScrollMode,
            'follow': FollowScrollMode,
        }[mode](self.song)

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
    def __init__(self, song=None):
        self.set_song(song)
        self.incoming_midi = []

    def on_midi_message(self, msg):
        if msg.type in ['note_on', 'note_off']:
            self.incoming_midi.append(msg)

    def set_song(self, song):
        self.song = song

    def set_time(self, time):
        """Called when the scroller is set to a new time"""
        pass

    def check_midi(self):
        """Return all midi messages received since the last call"""
        messages = self.incoming_midi
        self.incoming_midi = []
        return messages

    def update(self, current_time, dt, scroll_speed):
        """Called periodically to update the current time
        
        Returns the new current time"""
        raise NotImplementedError()


class TempoScrollMode(ScrollMode):
    """Scroll at constant speed"""
    def update(self, current_time, dt, scroll_speed):
        return current_time + dt * scroll_speed
    

class WaitScrollMode(ScrollMode):
    """Wait for the next note to be played before scrolling"""
    def __init__(self, *args, **kwargs):
        self.next_note_index = 0
        self.early_key_time = 1.0  # seconds before a note is due to be played where a key press will count as a hit
        self.track_modes = {}  # Dictionary mapping track to mode

        # Autoplay settings
        self.midi_output = None
        self.autoplay_volume = 1.0  # 0.0-1.0 scale factor
        
        super().__init__(*args, **kwargs)
        
    def set_track_modes(self, track_modes):
        """Set the track modes for this scroll mode"""
        # Stop notes that might be from tracks changing away from autoplay
        if self.midi_output is not None:
            self.midi_output.stop_all()
        self.track_modes = track_modes
        self.update_note_state()

    def set_midi_output(self, midi_output):
        """Set MIDI output instance"""
        self.midi_output = midi_output

    def set_autoplay_volume(self, volume):
        """Set autoplay volume scale (0.0-1.0)"""
        self.autoplay_volume = volume

    def set_song(self, song):
        # Stop notes from previous song
        if self.midi_output is not None:
            self.midi_output.stop_all()
        super().set_song(song)
        self.next_note_index = 0
        if song is None:
            return
        # mark all notes as unplayed
        self.set_time(0)

    def set_time(self, time):
        # Stop active notes before time jump
        if self.midi_output is not None:
            self.midi_output.stop_all()
        super().set_time(time)
        self.next_note_index = self.song.index_of_note_starting_at(time)
        self.update_note_state()
                
    def update_note_state(self):
        # mark next event + all following events as unplayed, but only for 'player' tracks
        for i, note in enumerate(self.song.notes):
            track_key = (note.part, note.staff)
            track_mode = self.track_modes.get(track_key, 'player')  # Default to 'player' if not set

            if i < self.next_note_index:
                # Past notes are always marked as played
                note.played = True
            elif track_mode == 'player':
                # Future notes in 'player' tracks are marked as unplayed
                note.played = False
            else:
                # Future notes in non-player tracks (autoplay, visual only, hidden) are marked as played
                note.played = True

    def _can_emit_autoplay_note(self, autoplay_note, current_time):
        """Check if autoplay note can be emitted.

        Returns False if there are unplayed player notes at the same time.
        """
        # Find all notes at same start time (within 10ms tolerance)
        same_time_notes = [
            n for n in self.song.notes
            if abs(n.start_time - autoplay_note.start_time) < 0.01
        ]

        # Check if any player notes are unplayed
        for note in same_time_notes:
            track_key = (note.part, note.staff)
            track_mode = self.track_modes.get(track_key, 'player')

            if track_mode == 'player' and not note.played:
                # Player note not played yet - don't emit autoplay
                return False

        return True

    def _check_autoplay_note_ons(self, current_time):
        """Check for autoplay notes that should start at current_time"""
        if self.midi_output is None or self.song is None:
            return

        # Scan notes starting near current_time (within 3ms window)
        for note in self.song.notes:
            # Skip if already active
            if id(note) in self.midi_output.active_notes:
                continue

            # Skip if not at start time yet (notes are sorted)
            if note.start_time > current_time + 0.003:
                break

            # Skip if already past (more than 3ms ago)
            if note.start_time < current_time - 0.003:
                continue

            # Check if autoplay track
            track_key = (note.part, note.staff)
            track_mode = self.track_modes.get(track_key, 'player')

            if track_mode == 'autoplay':
                # Check if player notes at same time are all played
                if self._can_emit_autoplay_note(note, current_time):
                    self.midi_output.note_on(note, self.autoplay_volume)

    def _check_autoplay_note_offs(self, current_time):
        """Check for autoplay notes that should end at current_time"""
        if self.midi_output is None or self.song is None:
            return

        # Check active notes for those that should end
        to_stop = []
        for note_id in list(self.midi_output.active_notes.keys()):
            # Find the note object in the song
            note = None
            for n in self.song.notes:
                if id(n) == note_id:
                    note = n
                    break

            if note is None:
                continue

            end_time = note.start_time + note.duration
            if end_time <= current_time:
                to_stop.append(note)

        # Stop notes that have ended
        for note in to_stop:
            self.midi_output.note_off(note)

    def update(self, current_time, dt, scroll_speed):        
        # check for recent midi input
        recent_messages = self.check_midi()
        recent_presses = [msg for msg in recent_messages if msg.type == 'note_on']

        if self.next_note_index is None:
            return current_time

        # check if any recent key presses match the next note
        for msg in recent_presses:
            matched_time = None
            for note in self.song.notes[self.next_note_index:]:
                if note.start_time > current_time + self.early_key_time:
                    # too early to count any key presses toward the next note
                    break
                if note.played:
                    continue
                if note.pitch.midi_note == msg.note:
                    # a key press matches an upcoming next note. It only counts if it's the first key press for this note
                    # or if the note is being played at the same time as another that already accepted this key press
                    if matched_time is None or matched_time == note.start_time:
                        note.played = True
                        matched_time = note.start_time
                        print(f"DEBUG: Note played - start_time={note.start_time}, pitch={note.pitch}, duration={note.duration}")

        # Check for autoplay events
        self._check_autoplay_note_ons(current_time)
        self._check_autoplay_note_offs(current_time)

        # check if we can advance to the next note
        old_next_note_index = self.next_note_index
        for i in range(self.next_note_index, len(self.song)):
            if self.song.notes[i].played:
                self.next_note_index = i + 1
            else:
                break
        
        # Debug print when we advance to a new note
        if self.next_note_index != old_next_note_index and self.next_note_index < len(self.song):
            next_note = self.song.notes[self.next_note_index]
            print(f"DEBUG: Waiting for next note - start_time={next_note.start_time}, pitch={next_note.pitch}, duration={next_note.duration}")

        if self.next_note_index >= len(self.song):
            max_time = self.song.end_time
        else:
            max_time = self.song.notes[self.next_note_index].start_time
        
        desired_time = current_time + dt * scroll_speed
        return min(desired_time, max_time)


class FollowScrollMode(ScrollMode):
    def update(self, current_time, dt, scroll_speed):
        self.check_midi()

        recent_keys = {msg.note:msg for msg in self.recent_midi if msg.type == 'note_on'}
        # use BLAST to predict where we are in the song, based on recent midi input events
        return current_time + dt * scroll_speed
    

