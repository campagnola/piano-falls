import time
import mido
from .qt import QtCore
from .song import Pitch, Song


class MidiInput(QtCore.QObject):
    message = QtCore.Signal(object, object)

    @classmethod
    def get_available_ports(cls):
        import mido
        return mido.get_input_names()

    def __init__(self, port):
        self.port = mido.open_input(port)
        self.port.callback = self.callback
        super().__init__()

    def callback(self, msg):
        # warning: exceptions in this callback are silently ignored
        self.message.emit(self, MidiMessage(msg))


class MidiMessage:
    def __init__(self, msg):
        self.msg = msg
        self.perf_counter = time.perf_counter()

    def __getattr__(self, name):
        return getattr(self.msg, name)
    
    def __repr__(self):
        return f'<MidiMessage {self.perf_counter} {self.type} {self.note}>'


def load_midi(filename:str) -> Song:
    """Load a MIDI file and display it on the waterfall"""
    midi = mido.MidiFile(filename)
    assert midi.type in (0, 1)

    messages = []
    for i, track in enumerate(midi.tracks):
        # create a dict for each message that contains the absolute tick count
        # and the message itself
        ticks = 0
        prev_track_msg = None
        for msg in track:
            ticks += msg.time
            messages.append({'ticks': ticks, 'midi': msg, 'track': track, 'track_n': i, 'prev_track_msg': prev_track_msg})
            prev_track_msg = messages[-1]

    # sort messages by tick
    messages = sorted(messages, key=lambda m: m['ticks'])

    # calculate absolute time of each message, accounting for tempo changes that affect all tracks
    tempo = 500000
    ticks_per_beat = midi.ticks_per_beat
    abs_time = 0
    last_ticks = 0

    for msg in messages:
        ticks = msg['ticks']
        # Update absolute time based on the elapsed ticks and current tempo
        dt = mido.tick2second(ticks - last_ticks, ticks_per_beat, tempo)
        abs_time += dt
        msg['time'] = abs_time

        # If the message is a tempo change, update the tempo
        if msg['midi'].type == 'set_tempo':
            tempo = msg['midi'].tempo

        last_ticks = ticks

    # collapse note_on / note_off messages into a single event with duration
    current_notes = {}  # To store the notes currently being played
    notes = []  # Store the complete notes
    for message in messages:
        msg = message['midi']
        msg_time = message['time']
        if msg.type == 'note_on' and msg.velocity > 0:
            note_dict = {
                'start_time': msg_time, 'pitch': Pitch(midi_note=msg.note), 'duration': None, 
                'track': message['track'], 'track_n': message['track_n'],
                'on_msg': message, 'off_msg': None
            }
            notes.append(note_dict)
            if msg.note in current_notes:
                # end previous note here
                prev_note = current_notes[msg.note]
                prev_note['duration'] = msg_time - prev_note['start_time']
            current_notes[msg.note] = note_dict
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note not in current_notes:
                continue
            note_end = msg_time
            note_start = current_notes[msg.note]['start_time']
            current_notes[msg.note]['duration'] = note_end - note_start
            current_notes[msg.note]['off_msg'] = msg
            del current_notes[msg.note]

    # filter out empty notes
    notes = [n for n in notes if n['duration'] > 0]

    return Song(notes)
