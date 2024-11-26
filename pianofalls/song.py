
class Song:
    """Encapsulates a sequence of events in a song (notes, bars, lyrics, etc.)
    """
    def __init__(self, events):
        # *events* can be a list of dicts describing each note
        # keys are: start_time, pitch, duration, track, track_n, on_msg, off_msg
        self.notes = []
        self.events = []
        for i, src_event in enumerate(events):
            if isinstance(src_event, dict):
                src_event = Note(**src_event)
            
            if not isinstance(src_event, Event):
                raise ValueError(f'Invalid note type: {type(src_event)}')
            
            src_event.index = i
            self.events.append(src_event)
            if isinstance(src_event, Note) and src_event.pitch is not None:
                self.notes.append(src_event)

        self.notes.sort(key=lambda n: n.start_time)
        self.events.sort(key=lambda e: e.start_time)

        # Lookup table for quickly finding the note at a given time
        self.time_lookup = {}
        last = -1
        for i,note in enumerate(self.notes):
            t = int(note.start_time)
            if t not in self.time_lookup:
                for j in range(last+1, t+1):
                    self.time_lookup[j] = i
                last = t

    def __len__(self):
        return len(self.notes)
    
    def index_at_time(self, time):
        """Return the index of the first note at or after the given time"""
        time = max(0, time)
        closest_index = self.time_lookup.get(int(time), None)
        if closest_index is None:
            return None
        while True:
            if self.notes[closest_index].start_time >= time:
                return closest_index
            closest_index += 1




class Event:
    def __init__(self, start_time, duration=0, **kwds):
        self.start_time = start_time
        self.duration = duration
        for k,v in kwds.items():
            setattr(self, k, v)

    def __repr__(self):
        return f'<{self.__class__.__name__} start_time={self.start_time}>'


class TempoChange(Event):
    def __init__(self, tempo, start_time=None, **kwds):
        self.tempo = tempo
        super().__init__(start_time=start_time, **kwds)

class KeySignatureChange(Event):
    def __init__(self, fifths, start_time=None, **kwds):
        self.fifths = fifths
        super().__init__(start_time=start_time, **kwds)

class TimeSignatureChange(Event):
    def __init__(self, numerator, denominator, start_time=None, **kwds):
        self.numerator = numerator
        self.denominator = denominator
        super().__init__(start_time=start_time, **kwds)


class Note(Event):
    def __init__(self, pitch, duration=None, start_time=None, index=None, track=None, 
                 track_n=None, staff=1, voice=1, is_chord=False, **kwds):
        self.pitch = pitch
        self.index = index
        self.track = track
        self.track_n = track_n
        self.staff = staff
        self.voice = voice
        self.is_chord = is_chord
        super().__init__(start_time=start_time, duration=duration, **kwds)

    def __repr__(self):
        return f'<{self.__class__.__name__} staff={self.staff} voice={self.voice} start_time={self.start_time} pitch={self.pitch.name} duration={self.duration}>'


class Rest(Note):
    def __init__(self, duration=None, start_time=None, **kwds):
        super().__init__(start_time=start_time, pitch=None, duration=duration, **kwds)

    def __repr__(self):
        return f'<{self.__class__.__name__} start_time={self.start_time} duration={self.duration}>'


class Pitch:
    def __init__(self, midi_note):
        self.midi_note = midi_note
        self.key = midi_note - 21

        # midi note 24 is C1  (23 is B0, because of course)
        self.note_name = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'][(midi_note - 24) % 12]
        self.octave = 1 + (midi_note - 24) // 12

    @property
    def name(self):
        return self.note_name + str(self.octave)

    def __eq__(self, other):
        return self.midi_note == other.midi_note

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.name} ({self.midi_note})>'
