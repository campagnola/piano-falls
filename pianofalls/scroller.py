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

    def set_song(self, song):
        self.song = song
        self.scroll_mode.set_song(song)
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
        super().__init__(*args, **kwargs)
        self.next_note_index = 0
        self.early_key_time = 1.0  # seconds before a note is due to be played where a key press will count as a hit
        self.track_modes = {}  # Dictionary mapping track to mode
        
    def set_track_modes(self, track_modes):
        """Set the track modes for this scroll mode"""
        self.track_modes = track_modes
        self.update_note_state()

    def set_song(self, song):
        super().set_song(song)
        self.next_note_index = 0
        if song is None:
            return
        # mark all notes as unplayed
        self.set_time(0)

    def set_time(self, time):
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
    

