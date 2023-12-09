
class Song:
    """Encapsulates a sequence of events in a song (notes, bars, lyrics, etc.)
    """
    def __init__(self, events):
        self.events = events







class Pitch:
    def __init__(self, midi_note):
        self.midi_note = midi_note
        self.key = midi_note - 21    


