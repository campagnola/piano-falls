import threading, math, time
from .qt import QtCore


class TimeScroller(QtCore.QObject):
    current_time_changed = QtCore.Signal(float)

    def __init__(self):
        super().__init__()
        self.current_time = 0.0
        self.time_lock = threading.Lock()

        self.song = None

        self.target_time = 0.0  # time to scroll to
        self.scroll_tau = 0.0  # how quickly to scroll to the target time
        self.scroll_speed = 1.0 # how quickly to scroll in song seconds per real second
        self.scrolling = False
        self.scroll_mode = 'tempo'  # 'wait' or 'tempo'

        self.midi_queue = None

        self.thread = threading.Thread(target=self.auto_scroll_loop, daemon=True)

    def set_scrolling(self, scrolling):
        self.scrolling = scrolling

    def toggle_scrolling(self):
        self.set_scrolling(not self.scrolling)

    def set_song(self, song):
        self.song = song
        self.set_time(-3)
        self.set_scrolling(False)
        self.thread.start()

    def set_scroll_speed(self, speed):
        self.scroll_speed = speed

    def set_time(self, time):
        with self.time_lock:
            self.current_time = time
            self.target_time = time

    def set_target_time(self, time):
        self.target_time = time

    def scroll_by(self, delta):
        with self.time_lock:
            self.set_target_time(self.target_time + delta)

    def connect_midi_input(self, midi_input):
        self.midi_queue = midi_input.add_queue()

    def auto_scroll_loop(self):
        last_time = time.perf_counter()
        midi_messages = []
        while True:
            now = time.perf_counter()
            dt = now - last_time
            last_time = now

            # collect latest midi messages from queue
            midi_queue = self.midi_queue
            if midi_queue is not None:
                while not midi_queue.empty():
                    msg = midi_queue.get()
                    if msg.type == 'note_on':
                        midi_messages.append(msg)

            # discard messages older than 5 seconds
            midi_messages = [msg for msg in midi_messages if msg.time > now - 5]
            
            with self.time_lock:
                if self.scrolling:
                    if self.scroll_mode == 'tempo':
                        self.set_target_time(self.current_time + dt * self.scroll_speed)
                    elif self.scroll_mode == 'wait':
                        next_note_index = self.waterfall.song.index_at_time(self.current_time)
                        if next_note_index is not None:
                            next_note = self.waterfall.song.notes[next_note_index]
                            for msg in midi_messages:
                                if msg.note == next_note.pitch.midi_note:
                                    self.set_target_time(next_note.start_time)
                                    break
                    elif self.scroll_mode == 'follow':
                        # use BLAST to predict where we are in the song, based on recent midi input events
                        pass

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
