
class Song:
    """Encapsulates a sequence of events in a song (notes, bars, lyrics, etc.)
    """
    def __init__(self, notes):
        # *notes* is a list of dicts describing each note
        # keys are: start_time, pitch, duration, track, track_n, on_msg, off_msg
        self.notes = [Note(index=i, **n) for i,n in enumerate(notes)]

        # Lookup table for quickly finding the note at a given time
        self.time_lookup = {}
        for i,note in enumerate(self.notes):
            self.time_lookup[int(note.start_time)] = i

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
    def __init__(self, index, start_time, pitch, duration, track, track_n, on_msg=None, off_msg=None):
        self.index = index
        self.start_time = start_time
        self.pitch = pitch
        self.duration = duration
        self.track = track
        self.track_n = track_n
        self.on_msg = on_msg
        self.off_msg = off_msg


class Pitch:
    def __init__(self, midi_note):
        self.midi_note = midi_note
        self.key = midi_note - 21    
