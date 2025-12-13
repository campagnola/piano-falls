import numpy as np


class Song:
    """Encapsulates a sequence of events in a song (notes, bars, lyrics, etc.)
    """
    def __init__(self, events):
        self._tracks = None

        # *events* can be a list of dicts describing each note
        # keys are: start_time, pitch, duration, track, track_n, on_msg, off_msg
        self.notes = []
        self.events = []
        self._end_time = None
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

        # Lookup table for quickly finding notes starting or playing at a given time
        song_duration = max(e.start_time + e.duration for e in self.events)
        self.start_time_lookup = [[] for _ in range(int(song_duration)+1)]
        self.playing_time_lookup = [[] for _ in range(int(song_duration)+1)]
        for i,event in enumerate(self.events):
            self.start_time_lookup[int(event.start_time)].append(i)
            for j in range(int(event.start_time), int(np.ceil(event.start_time + event.duration))):
                self.playing_time_lookup[j].append(i)

        self.note_start_times = np.array([n.start_time for n in self.notes])

    def __len__(self):
        return len(self.notes)
    
    def index_of_event_starting_at(self, time):
        """Return the index of the first event that starts at or after the given time
        """
        inds = self._event_indices_at_time(time, self.start_time_lookup)
        for i in range(inds[0], len(self.events)):
            if self.events[i].start_time >= time:
                return i
        return None
        
    def index_of_note_starting_at(self, time):
        """Return the index of the first note that starts at or after the given time
        """
        ind = np.searchsorted(self.note_start_times, time)
        if ind >= len(self.notes):
            return None
        return ind
        
    def _event_indices_at_time(self, time, lookup):
        """Return the first 1-second bin of event indices that appear at or after the given time
        """
        time = max(0, time)
        lookup_index = int(time)
        while lookup_index < len(lookup):
            if lookup[lookup_index]:
                return lookup[lookup_index]
            lookup_index += 1
        return []

    def indices_of_events_active_at(self, time):
        """Return indices of events that are active in the first 1-second bin at or after the given time
        """
        inds = self._event_indices_at_time(time, self.playing_time_lookup)
        return inds

    def get_events_active_in_range(self, time_range, filter=None):
        # Collect all event indices from bins that overlap with the time range
        all_inds = []
        for t in range(int(time_range[0]), int(time_range[1]) + 1):
            all_inds.extend(self.indices_of_events_active_at(t))

        if len(all_inds) == 0:
            return []

        events = self.events[min(all_inds):max(all_inds)+1]

        if isinstance(filter, str):
            events = [e for e in events if type(e).__name__ == filter]
        elif filter is not None:
            events = [e for e in events if isinstance(e, filter)]

        return events

    @property
    def tracks(self):
        """For musicxml, a track is the combination of part and staff. For midi,
        tracks and parts are the same thing.
        """
        if self._tracks is None:
            self._tracks = set([(getattr(e, 'part', None), getattr(e, 'staff', None)) for e in self.events])
            
        return self._tracks

    @property
    def end_time(self):
        if self._end_time is None:
            self._end_time = max(e.start_time + e.duration for e in self.events)
        return self._end_time


class Event:
    repr_keys = ['start_time', 'duration', 'part']
    def __init__(self, start_time, duration=0, part=None, line_number=None, **kwds):
        self.start_time = start_time
        self.duration = duration
        self.part = part
        self.line_number = line_number
        for k,v in kwds.items():
            setattr(self, k, v)

    def __repr__(self):
        vals = {k:getattr(self, k) for k in self.repr_keys}
        val_str = " ".join(f"{k}={v}" for k,v in vals.items())
        if self.line_number is not None:
            val_str += f' line={self.line_number}'
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
    repr_keys = Event.repr_keys + ['staff', 'voice', 'is_chord']
    def __init__(self, duration=None, start_time=None, 
                 staff=1, voice=1, is_chord=False, **kwds):
        self.voice = voice
        self.is_chord = is_chord
        self.staff = staff
        super().__init__(start_time=start_time, duration=duration, **kwds)

    @property
    def track(self):
        return (self.part, self.staff)


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
