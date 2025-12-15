import time
import mido
from .qt import QtCore
from .song import Pitch, Song, Note, Part


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
        try:
            self.message.emit(self, MidiMessage(msg))
        except Exception as e:
            print(f"Exception in MidiInput.callback: {e}")


class MidiOutput:
    """Handles MIDI output to external devices/synths"""

    @classmethod
    def get_available_ports(cls):
        """List available MIDI output ports"""
        import mido
        return mido.get_output_names()

    def __init__(self, port):
        """Initialize MIDI output on specified port"""
        self.port = mido.open_output(port)
        self.active_notes = {}  # Map from note object to midi_note number

    def note_on(self, note, volume):
        """Emit MIDI note-on with volume scaling.

        Args:
            note: Note object with pitch and on_msg attributes
            volume: Volume scale factor (0.0-1.0)
        """
        # Get velocity from note.on_msg, default to 64
        base_velocity = 64
        if hasattr(note, 'on_msg') and note.on_msg:
            midi_msg = note.on_msg.get('midi')
            if midi_msg and hasattr(midi_msg, 'velocity'):
                base_velocity = midi_msg.velocity

        # Scale by volume control
        scaled_velocity = int(base_velocity * volume)
        scaled_velocity = max(1, min(127, scaled_velocity))  # Clamp to MIDI range

        # Send note-on
        midi_note = note.pitch.midi_note
        msg = mido.Message('note_on', note=midi_note, velocity=scaled_velocity)
        self.port.send(msg)

        # Track active note
        self.active_notes[id(note)] = midi_note

    def note_off(self, note):
        """Emit MIDI note-off and remove from tracking"""
        midi_note = note.pitch.midi_note
        msg = mido.Message('note_off', note=midi_note, velocity=0)
        self.port.send(msg)

        # Remove from active tracking
        self.active_notes.pop(id(note), None)

    def stop_all(self):
        """Stop all active MIDI notes and clear tracking.

        This is the central method for ensuring no orphaned MIDI notes.
        """
        # Send note-off for all active notes
        for midi_note in self.active_notes.values():
            msg = mido.Message('note_off', note=midi_note, velocity=0)
            self.port.send(msg)

        # Clear tracking
        self.active_notes.clear()

    def close(self):
        """Close MIDI port"""
        if self.port:
            self.stop_all()  # Clean up any active notes
            self.port.close()


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
    parts = []
    for i, track in enumerate(midi.tracks):
        parts.append(MidiPart(track, i))
        # create a dict for each message that contains the absolute tick count
        # and the message itself
        ticks = 0
        prev_track_msg = None
        for msg in track:
            ticks += msg.time
            messages.append({'ticks': ticks, 'midi': msg, 'part': parts[-1], 'prev_track_msg': prev_track_msg})
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
            note_key = (msg.note, msg.channel)
            note = Note(
                start_time=msg_time, 
                pitch=Pitch(midi_note=msg.note), 
                duration=None, 
                part=message['part'],
                on_msg=message, off_msg=None
            )
            notes.append(note)
            if note_key in current_notes:
                # end previous note here
                prev_note = current_notes[note_key]
                prev_note.duration = msg_time - prev_note.start_time
            current_notes[note_key] = note
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            note_key = (msg.note, msg.channel)
            if note_key not in current_notes:
                continue
            note_end = msg_time
            note_start = current_notes[note_key].start_time
            current_notes[note_key].duration = note_end - note_start
            del current_notes[note_key]

    # force start at 0
    start_time = min([note.start_time for note in notes])
    for note in notes:
        note.start_time -= start_time

    return Song(notes)


class MidiPart(Part):
    def __init__(self, midi_track, track_n):
        track_name = midi_track.name
        if track_name == '':
            track_name = f'MIDI track {track_n}'
        Part.__init__(self, name=track_name)
        self.midi_track = midi_track
