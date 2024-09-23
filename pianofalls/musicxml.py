import zipfile
import xml.etree.ElementTree as ET
from .song import Song, Pitch


def read_musicxml_file(filename: str) -> str:
    """Read the contents of a MusicXML file."""
    if filename.endswith('.mxl'):
        with zipfile.ZipFile(filename) as z:
            with z.open('META-INF/container.xml') as f:
                container = ET.parse(f)
                rootfile = container.find('.//rootfile')
                musicxml_path = rootfile.attrib['full-path']
            with z.open(musicxml_path) as f:
                return f.read()
    else:
        with open(filename, 'rb') as f:
            return f.read()


def parse_musicxml_content(xml_content: bytes):
    """Parse the XML content and return root and namespace."""
    root = ET.fromstring(xml_content)

    # Get the namespace
    if root.tag.startswith('{'):
        namespace = root.tag.split('}')[0].strip('{')
    else:
        namespace = ''

    def ns_tag(tag):
        return f'{{{namespace}}}{tag}' if namespace else tag

    return root, ns_tag


def extract_parts(root, ns_tag):
    """Extract parts from the MusicXML root."""
    parts = root.findall(ns_tag('part'))
    return parts


def parse_part(part, ns_tag, divisions, tempo, part_index):
    """Parse a part and extract notes."""
    notes = []
    voice_positions = {}  # Key: voice_number, Value: current division position

    measures = part.findall(ns_tag('measure'))
    for measure in measures:
        measure_notes = parse_measure(measure, ns_tag, divisions, tempo, voice_positions, part_index)
        notes.extend(measure_notes)

    return notes


def parse_measure(measure_elem, ns_tag, divisions, initial_tempo, part_index):
    notes = []
    voice_current_times = {}  # Keeps track of current_time for each voice
    tempo = initial_tempo     # Use a mutable tempo variable

    # Get all measure child elements in order
    measure_elements = list(measure_elem)
    i = 0
    while i < len(measure_elements):
        elem = measure_elements[i]
        tag = elem.tag

        if tag == ns_tag('attributes'):
            # Handle attributes (e.g., divisions, time signature changes)
            divisions_elem = elem.find(ns_tag('divisions'))
            if divisions_elem is not None:
                divisions = int(divisions_elem.text)
            # Handle other attributes as needed
            i += 1

        elif tag == ns_tag('direction'):
            # Handle tempo changes
            sound_elem = elem.find(ns_tag('sound'))
            if sound_elem is not None and 'tempo' in sound_elem.attrib:
                tempo = float(sound_elem.attrib['tempo'])
            i += 1

        elif tag == ns_tag('note'):
            note_elem = elem
            chord_notes = []
            # Get voice number
            voice_elem = note_elem.find(ns_tag('voice'))
            voice_number = int(voice_elem.text) if voice_elem is not None else 1

            # Initialize current_time for the voice if not already set
            if voice_number not in voice_current_times:
                voice_current_times[voice_number] = 0.0  # Start at 0.0

            # Get the current_time for this voice
            voice_time = voice_current_times[voice_number]

            # Collect chord notes
            chord_notes.append(note_elem)
            i += 1
            while i < len(measure_elements):
                next_elem = measure_elements[i]
                if next_elem.tag == ns_tag('note'):
                    # Check if this note has <chord/> element
                    chord_elem = next_elem.find(ns_tag('chord'))
                    if chord_elem is not None:
                        chord_notes.append(next_elem)
                        i += 1
                    else:
                        break  # Not part of the chord
                else:
                    break  # Not a note element

            # Process the chord notes
            chord_note_dicts = []
            max_duration_divisions = 0
            for chord_note_elem in chord_notes:
                note_data, duration_divisions, voice_number, is_chord_note, is_rest, _ = parse_note_element(
                    chord_note_elem, ns_tag, divisions, tempo, voice_time, part_index
                )
                if note_data:
                    chord_note_dicts.append(note_data)
                if duration_divisions > max_duration_divisions:
                    max_duration_divisions = duration_divisions

            notes.extend(chord_note_dicts)

            # Update current_time for the voice after processing the chord
            duration_seconds = (max_duration_divisions / divisions) * (60.0 / tempo)
            voice_current_times[voice_number] += duration_seconds

        else:
            # Other elements (e.g., backup, forward)
            i += 1

    return notes


def parse_note(note_elem, ns_tag, divisions, tempo, current_time, part_index):
    """
    Parse a note element, handling chords and returns a list of note dictionaries.

    Parameters:
    - note_elem: The XML element representing the <note>.
    - ns_tag: A function to handle namespaces.
    - divisions: Number of divisions per quarter note.
    - tempo: Tempo in BPM.
    - current_time: The current time position in seconds.
    - part_index: Index of the part (track).

    Returns:
    - note_dicts: List of note dictionaries (could be multiple for chords).
    - updated_current_time: The updated current_time after the note.
    """
    note_dicts = []
    chord_notes = []
    is_chord = False

    # Check if this note is part of a chord
    chord_elem = note_elem.find(ns_tag('chord'))
    if chord_elem is not None:
        is_chord = True

    # Parse the note
    note_data, duration_divisions, voice_number, is_chord_note, is_rest, updated_current_time = parse_note_element(
        note_elem, ns_tag, divisions, tempo, current_time, part_index
    )

    if note_data:
        note_dicts.append(note_data)

    # For chords, collect all chord notes
    if is_chord:
        # For testing purposes, assume chords are represented by consecutive <note> elements with <chord/>
        # Since we are in parse_measure, we need to handle the collection of chord notes here.
        pass  # Chord handling is simplified for this example

    # For rests or non-chord notes, update current_time
    if not is_chord:
        current_time = updated_current_time

    return note_dicts, current_time


def parse_note_element(elem, ns_tag, divisions, tempo, current_time, part_index):
    """
    Parse a MusicXML <note> element and return:
    - note_dict: The note dictionary or None if it's a rest.
    - duration_divisions: The duration of the note in divisions.
    - voice_number: The voice number of the note.
    - is_chord: Boolean indicating if the note is part of a chord.
    - is_rest: Boolean indicating if the note is a rest.
    - updated_current_time: The updated current_time after the note.
    """
    # Get voice number (default to 1 if not specified)
    voice_elem = elem.find(ns_tag('voice'))
    voice_number = int(voice_elem.text) if voice_elem is not None else 1

    # Get duration in divisions
    duration_elem = elem.find(ns_tag('duration'))
    duration_divisions = int(duration_elem.text) if duration_elem is not None else 0

    # Handle time-modification (e.g., tuplets)
    time_mod_elem = elem.find(ns_tag('time-modification'))
    if time_mod_elem is not None:
        actual_notes_elem = time_mod_elem.find(ns_tag('actual-notes'))
        normal_notes_elem = time_mod_elem.find(ns_tag('normal-notes'))
        if actual_notes_elem is not None and normal_notes_elem is not None:
            actual_notes = int(actual_notes_elem.text)
            normal_notes = int(normal_notes_elem.text)
            # Adjust duration_divisions
            duration_divisions *= (normal_notes / actual_notes)

    # Check for 'chord' element
    is_chord = elem.find(ns_tag('chord')) is not None

    # Check if it's a rest
    is_rest = elem.find(ns_tag('rest')) is not None

    # Get staff number (default to 1 if not specified)
    staff_elem = elem.find(ns_tag('staff'))
    staff_number = int(staff_elem.text) if staff_elem is not None else 1

    # For rests, advance current_time by the duration
    if is_rest:
        duration = (duration_divisions / divisions) * (60.0 / tempo)
        updated_current_time = current_time + duration
        return None, duration_divisions, voice_number, is_chord, is_rest, updated_current_time

    # For chords, the start_time remains the same
    if is_chord:
        start_time = current_time
    else:
        start_time = current_time

    # Process note
    pitch_elem = elem.find(ns_tag('pitch'))
    if pitch_elem is not None:
        step = pitch_elem.find(ns_tag('step')).text
        octave = int(pitch_elem.find(ns_tag('octave')).text)
        alter_elem = pitch_elem.find(ns_tag('alter'))
        alter = int(alter_elem.text) if alter_elem is not None else 0

        # Map step to semitone
        step_to_semitone = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        midi_note = (octave + 1) * 12 + step_to_semitone[step] + alter

        # Calculate duration in seconds
        duration = (duration_divisions / divisions) * (60.0 / tempo)

        # Create the note dictionary
        note_dict = {
            'start_time': start_time,
            'pitch': Pitch(midi_note=midi_note),
            'duration': duration,
            'track': part_index,
            'track_n': part_index,
            'on_msg': None,
            'off_msg': None,
            'staff': staff_number,
            'voice': voice_number
        }

        # Update current_time if not a chord
        if not is_chord:
            updated_current_time = current_time + duration
        else:
            updated_current_time = current_time  # For chords, don't advance time here

        return note_dict, duration_divisions, voice_number, is_chord, is_rest, updated_current_time

    return None, duration_divisions, voice_number, is_chord, is_rest, current_time


def load_musicxml(filename: str) -> Song:
    """Load a MusicXML file and parse it into a Song object."""
    # Read the MusicXML file
    xml_content = read_musicxml_file(filename)
    # Parse the XML content
    root, ns_tag = parse_musicxml_content(xml_content)
    # Extract parts
    parts = extract_parts(root, ns_tag)
    # Initialize variables
    all_notes = []
    # Default divisions and tempo
    divisions = 1
    tempo = 120.0
    # Process each part
    for i, part in enumerate(parts):
        part_notes = parse_part(part, ns_tag, divisions, tempo, i)
        all_notes.extend(part_notes)
    # Create and return the Song object
    return Song(all_notes)
