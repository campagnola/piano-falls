
class Song:
    """Encapsulates a sequence of events in a song (notes, bars, lyrics, etc.)
    """
    def __init__(self, notes):
        # *notes* is a list of dicts describing each note
        # keys are: start_time, pitch, duration, track, track_n, on_msg, off_msg
        self.notes = []
        for i, src_note in enumerate(notes):
            if isinstance(src_note, dict):
                self.notes.append(Note(index=i, **src_note))
            elif isinstance(src_note, Note):
                src_note.index = i
                self.notes.append(src_note)
            else:
                raise ValueError(f'Invalid note type: {type(src_note)}')

        self.notes.sort(key=lambda n: n.start_time)

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


class Note:
    def __init__(self, start_time, pitch, duration, index=None, track=None, track_n=None, staff=1, voice=1, on_msg=None, off_msg=None):
        self.start_time = start_time
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
