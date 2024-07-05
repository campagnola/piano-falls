import queue
import threading, math, time
from .qt import QtCore


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
        self.midi_queue = queue.Queue()

        self.set_scroll_mode('wait')

        self.thread = threading.Thread(target=self.auto_scroll_loop, daemon=True)

    def set_scrolling(self, scrolling):
        self.scrolling = scrolling

    def toggle_scrolling(self):
        self.set_scrolling(not self.scrolling)

    def set_song(self, song):
        self.song = song
        self.scroll_mode.set_song(song)
        self.set_time(-3)
        self.set_scrolling(False)
        self.thread.start()

    def set_scroll_speed(self, speed):
        self.scroll_speed = speed

    def set_scroll_mode(self, mode):
        self.scroll_mode = {
            'tempo': TempoScrollMode,
            'wait': WaitScrollMode,
            'follow': FollowScrollMode,
        }[mode](self.song, self.midi_queue)

    def set_time(self, time):
        self.current_time = time
        self.target_time = time
        self.scroll_mode.set_time(time)

    def set_target_time(self, time):
        self.target_time = time

    def scroll_by(self, delta):
        self.set_target_time(self.target_time + delta)

    def connect_midi_input(self, midi_input):
        midi_input.message.connect(self.on_midi_message)

    def on_midi_message(self, midi_input, msg):
        if msg.type in ['note_on', 'note_off']:
            self.midi_queue.put(msg)

    def auto_scroll_loop(self):
        last_time = time.perf_counter()
        while True:
            now = time.perf_counter()
            dt = now - last_time
            last_time = now
            
            if self.scrolling:
                self.set_target_time(self.scroll_mode.update(self.current_time, dt, self.scroll_speed))

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


class ScrollMode:
    def __init__(self, song=None, midi_queue=None):
        self.set_song(song)
        self.midi_queue = midi_queue
        self.recent_midi = []

    def set_song(self, song):
        self.song = song

    def set_time(self, time):
        """Called when the scroller is set to a new time"""
        pass

    def check_midi(self):
        # collect latest midi messages from queue
        while not self.midi_queue.empty():
            msg = self.midi_queue.get()
            self.recent_midi.append(msg)

        # discard messages older than 5 seconds
        now = time.perf_counter()
        self.recent_midi = [msg for msg in self.recent_midi if msg.perf_counter > now - 5]

    def update(self, current_time, dt, scroll_speed):
        pass


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

    def set_song(self, song):
        super().set_song(song)
        self.next_note_index = 0

    def set_time(self, time):
        super().set_time(time)
        self.next_note_index = self.song.index_at_time(time)

    def update(self, current_time, dt, scroll_speed):        
        # find how far we have played into the song
        self.check_midi()
        recent_keys = {msg.note:msg for msg in self.recent_midi if msg.type == 'note_on'}
        while True:
            next_note = self.song.notes[self.next_note_index]
            if next_note.start_time > current_time + self.early_key_time:
                break
            if next_note.pitch.midi_note in recent_keys:
                self.next_note_index += 1
                self.recent_midi.remove(recent_keys[next_note.pitch.midi_note])
                recent_keys.pop(next_note.pitch.midi_note)
            else:
                break

        # next unplayed note
        next_note = self.song.notes[self.next_note_index]

        desired_time = current_time + dt * scroll_speed
        return min(desired_time, next_note.start_time)


class FollowScrollMode(ScrollMode):
    def update(self, current_time, dt, scroll_speed):
        self.check_midi()
        # use BLAST to predict where we are in the song, based on recent midi input events
        return current_time + dt * scroll_speed