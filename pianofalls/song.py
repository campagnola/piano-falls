
class Song:
    """Encapsulates a sequence of events in a song (notes, bars, lyrics, etc.)
    """
    def __init__(self, events):
        self._tracks = None

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

        self.notes.sort(key=lambda n: (n.start_time, n.pitch.midi_note))
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

    @property
    def tracks(self):
        """For musicxml, a track is the combination of part and staff. For midi,
        tracks and parts are the same thing.
        """
        if self._tracks is None:
            self._tracks = set([(getattr(e, 'part', None), getattr(e, 'staff', None)) for e in self.events])
            
        return self._tracks


class Event:
    repr_keys = ['start_time', 'duration', 'part']
    def __init__(self, start_time, duration=0, part=None, **kwds):
        self.start_time = start_time
        self.duration = duration
        self.part = part
        for k,v in kwds.items():
            setattr(self, k, v)

    def __repr__(self):
        vals = {k:getattr(self, k) for k in self.repr_keys}
        val_str = " ".join(f"{k}={v}" for k,v in vals.items())
        return f'<{self.__class__.__name__} {val_str}>'


class TempoChange(Event):
    repr_keys = Event.repr_keys + ['tempo']
    def __init__(self, tempo, start_time=None, **kwds):
        self.tempo = tempo
        super().__init__(start_time=start_time, **kwds)

class KeySignatureChange(Event):
    repr_keys = Event.repr_keys + ['fifths']
    def __init__(self, fifths, start_time=None, **kwds):
        self.fifths = fifths
        super().__init__(start_time=start_time, **kwds)

class TimeSignatureChange(Event):
    repr_keys = Event.repr_keys + ['numerator', 'denominator']
    def __init__(self, numerator, denominator, start_time=None, **kwds):
        self.numerator = numerator
        self.denominator = denominator
        super().__init__(start_time=start_time, **kwds)

class Barline(Event):
    pass


class VoiceEvent(Event):
    repr_keys = Event.repr_keys + ['track', 'staff', 'voice', 'is_chord']
    def __init__(self, duration=None, start_time=None, 
                 staff=1, voice=1, is_chord=False, **kwds):
        self.voice = voice
        self.is_chord = is_chord
        self.staff = staff
        super().__init__(start_time=start_time, duration=duration, **kwds)


class Note(VoiceEvent):
    repr_keys = ['pitch'] + VoiceEvent.repr_keys
    def __init__(self, pitch, **kwds):
        self.pitch = pitch
        super().__init__(**kwds)


class Rest(VoiceEvent):
    pass


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


class Part:
    """Represents a part in a song. 

    In MusicXML, a part is a single line of music (usually one instrument; may have multiple staves). 
    In MIDI, a part is a track.
    """
    def __init__(self, name):
        self.name = name
