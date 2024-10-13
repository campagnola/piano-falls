
class Song:
    """Encapsulates a sequence of events in a song (notes, bars, lyrics, etc.)
    """
    def __init__(self, events):
        self.events = []
        for i, src_event in enumerate(events):
            if isinstance(src_event, Event):
                src_event.index = i
                self.events.append(src_event)
            else:
                raise ValueError(f'Invalid note type: {type(src_event)}')

        self.events.sort(key=lambda n: n.time)

        # Lookup table for quickly finding the note at a given time
        self.time_lookup = {}
        last = -1
        for i,note in enumerate(self.events):
            t = int(note.time)
            if t not in self.time_lookup:
                for j in range(last+1, t+1):
                    self.time_lookup[j] = i
                last = t

    def __len__(self):
        return len(self.events)
    
    def index_at_time(self, time):
        """Return the index of the first event at or after the given time"""
        time = max(0, time)
        closest_index = self.time_lookup.get(int(time), None)
        if closest_index is None:
            return None
        while True:
            if self.events[closest_index].time >= time:
                return closest_index
            closest_index += 1


class Event:
    def __init__(self, time, type):
        self.time = time
        self.type = type


class Note(Event):
    def __init__(self, start_time, pitch, duration, index=None, track=None, track_n=None, staff=1, voice=1, on_msg=None, off_msg=None):
        Event.__init__(self, start_time, 'note')
        self.pitch = pitch
        self.duration = duration
        self.index = index
        self.track = track
        self.track_n = track_n
        self.staff = staff
        self.voice = voice
        self.on_msg = on_msg
        self.off_msg = off_msg

    def __repr__(self):
        return f'<Note track={self.track} staff={self.staff} voice={self.voice} start_time={self.start_time} pitch={self.pitch.midi_note} duration={self.duration}>'


class Pitch:
    def __init__(self, midi_note):
        self.midi_note = midi_note
        self.key = midi_note - 21    
