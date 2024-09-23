import zipfile
import xml.etree.ElementTree as ET
from .song import Song, Pitch


def read_musicxml_file(filename):
    import zipfile
    import xml.etree.ElementTree as ET

    if filename.endswith('.mxl'):
        # It's a compressed MusicXML file
        with zipfile.ZipFile(filename, 'r') as zf:
            # Try to read container.xml to find the rootfile
            try:
                container_data = zf.read('META-INF/container.xml')
                container_root = ET.fromstring(container_data)
                # Find the rootfile
                rootfile_elem = container_root.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
                if rootfile_elem is not None:
                    full_path = rootfile_elem.attrib['full-path']
                    # Read the main score file
                    score_data = zf.read(full_path)
                    root = ET.fromstring(score_data)
                    return root
            except (KeyError, ET.ParseError):
                # No container.xml or unable to parse it
                pass

            # Fallback: search for the first .xml or .musicxml file in the zip archive
            for name in zf.namelist():
                if name.endswith('.xml') or name.endswith('.musicxml'):
                    score_data = zf.read(name)
                    root = ET.fromstring(score_data)
                    return root
            raise Exception('No MusicXML file found in the MXL archive.')
    else:
        # It's an uncompressed MusicXML file
        tree = ET.parse(filename)
        return tree.getroot()


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


def parse_part(part_elem, ns_tag, part_index, initial_tempo=120.0):
    """
    Parse a <part> element and return a list of note dictionaries.

    Parameters:
    - part_elem: The XML element representing the <part>.
    - ns_tag: A function to handle namespaces.
    - part_index: Index of the part (track).
    - initial_tempo: Initial tempo in BPM.

    Returns:
    - notes: List of note dictionaries parsed from the part.
    """
    notes = []
    divisions = 1  # Default divisions per quarter note
    tempo = initial_tempo  # Use initial_tempo parameter
    key_signature = 0  # Default key signature (C major/a minor)
    time_signature = (4, 4)  # Default time signature
    voice_current_times = {}  # Keeps track of current_time for each voice
    ties = {}  # Keep track of ongoing ties per voice

    # Iterate through measures
    for measure_elem in part_elem.findall(ns_tag('measure')):
        # Handle attributes (divisions, key signature, time signature)
        attributes_elem = measure_elem.find(ns_tag('attributes'))
        if attributes_elem is not None:
            # Divisions
            divisions_elem = attributes_elem.find(ns_tag('divisions'))
            if divisions_elem is not None:
                divisions = int(divisions_elem.text)
            # Key signature
            key_elem = attributes_elem.find(ns_tag('key'))
            if key_elem is not None:
                fifths_elem = key_elem.find(ns_tag('fifths'))
                if fifths_elem is not None:
                    key_signature = int(fifths_elem.text)
            # Time signature
            time_elem = attributes_elem.find(ns_tag('time'))
            if time_elem is not None:
                beats_elem = time_elem.find(ns_tag('beats'))
                beat_type_elem = time_elem.find(ns_tag('beat-type'))
                if beats_elem is not None and beat_type_elem is not None:
                    beats = int(beats_elem.text)
                    beat_type = int(beat_type_elem.text)
                    time_signature = (beats, beat_type)

        # Handle tempo changes within the measure
        direction_elems = measure_elem.findall(ns_tag('direction'))
        for direction in direction_elems:
            sound_elem = direction.find(ns_tag('sound'))
            if sound_elem is not None and 'tempo' in sound_elem.attrib:
                tempo = float(sound_elem.attrib['tempo'])

        # Parse the measure
        measure_notes = parse_measure(
            measure_elem, ns_tag, divisions, tempo, part_index, voice_current_times, key_signature, ties
        )
        notes.extend(measure_notes)

    return notes


def parse_measure(measure_elem, ns_tag, divisions, tempo, part_index, voice_current_times, key_signature, ties):
    """
    Parse a measure element and return a list of note dictionaries.

    Parameters:
    - measure_elem: The XML element representing the <measure>.
    - ns_tag: A function to handle namespaces.
    - divisions: Number of divisions per quarter note.
    - tempo: Tempo in BPM.
    - part_index: Index of the part (track).
    - voice_current_times: Dictionary of current times for each voice.
    - key_signature: Current key signature (number of sharps or flats).
    - ties: Dictionary to track ongoing ties per voice.

    Returns:
    - notes: List of note dictionaries parsed from the measure.
    """
    notes = []

    # Get all measure child elements in order
    measure_elements = list(measure_elem)
    i = 0
    while i < len(measure_elements):
        elem = measure_elements[i]
        tag = elem.tag

        if tag == ns_tag('attributes'):
            # Handle attributes within the measure (if any)
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
                    chord_note_elem, ns_tag, divisions, tempo, voice_time, part_index, key_signature
                )
                if note_data:
                    # Handle ties
                    tie_elems = chord_note_elem.findall(ns_tag('tie'))
                    tie_types = [tie_elem.attrib.get('type') for tie_elem in tie_elems]

                    if 'start' in tie_types and 'stop' not in tie_types:
                        # Start of a tie
                        ties[voice_number] = note_data
                        continue  # Do not add to notes yet
                    elif 'stop' in tie_types and 'start' not in tie_types:
                        # End of a tie
                        if voice_number in ties:
                            prev_note = ties.pop(voice_number)
                            # Combine durations
                            prev_note['duration'] += note_data['duration']
                            # Do not add the current note separately
                            note_data = prev_note
                        else:
                            # No matching tie start, add as is
                            pass
                    elif 'start' in tie_types and 'stop' in tie_types:
                        # Both start and stop (middle of a tie)
                        if voice_number in ties:
                            prev_note = ties[voice_number]
                            # Combine durations
                            prev_note['duration'] += note_data['duration']
                            # Keep the tie ongoing
                            ties[voice_number] = prev_note
                            continue  # Do not add to notes yet
                        else:
                            ties[voice_number] = note_data
                            continue  # Do not add to notes yet
                    else:
                        # No tie, but check if continuing a tie
                        if voice_number in ties:
                            prev_note = ties.pop(voice_number)
                            prev_note['duration'] += note_data['duration']
                            note_data = prev_note

                    chord_note_dicts.append(note_data)
                if duration_divisions > max_duration_divisions:
                    max_duration_divisions = duration_divisions

            notes.extend(chord_note_dicts)

            # Update current_time for the voice after processing the chord
            duration_seconds = (max_duration_divisions / divisions) * (60.0 / tempo)
            voice_current_times[voice_number] += duration_seconds

        else:
            # Other elements
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


def parse_note_element(elem, ns_tag, divisions, tempo, current_time, part_index, key_signature):
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
    start_time = current_time

    # Process note
    pitch_elem = elem.find(ns_tag('pitch'))
    if pitch_elem is not None:
        step = pitch_elem.find(ns_tag('step')).text
        octave = int(pitch_elem.find(ns_tag('octave')).text)
        alter_elem = pitch_elem.find(ns_tag('alter'))
        alter = int(alter_elem.text) if alter_elem is not None else 0

        # Adjust alter based on key signature
        key_signature_accidentals = {
            -7: ['B', 'E', 'A', 'D', 'G', 'C', 'F'],
            -6: ['B', 'E', 'A', 'D', 'G', 'C'],
            -5: ['B', 'E', 'A', 'D', 'G'],
            -4: ['B', 'E', 'A', 'D'],
            -3: ['B', 'E', 'A'],
            -2: ['B', 'E'],
            -1: ['B'],
            0: [],
            1: ['F'],
            2: ['F', 'C'],
            3: ['F', 'C', 'G'],
            4: ['F', 'C', 'G', 'D'],
            5: ['F', 'C', 'G', 'D', 'A'],
            6: ['F', 'C', 'G', 'D', 'A', 'E'],
            7: ['F', 'C', 'G', 'D', 'A', 'E', 'B'],
        }
        accidentals = key_signature_accidentals.get(key_signature, [])
        if step in accidentals and alter_elem is None:
            alter += 1  # Apply sharp

        # Map step to semitone
        step_to_semitone = {'C': 0, 'D': 2, 'E': 4, 'F':5, 'G':7, 'A':9, 'B':11}
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

        # For chords, do not update current_time here
        updated_current_time = current_time + (duration if not is_chord else 0)

        return note_dict, duration_divisions, voice_number, is_chord, is_rest, updated_current_time

    return None, duration_divisions, voice_number, is_chord, is_rest, current_time


def ns_tag(ns_map):
    def tag(name):
        return f"{{{ns_map['']} if '' in ns_map else ''}}{name}"
    return tag


def load_musicxml(filename):
    """
    Load a MusicXML file and return a Song instance.
    """
    import xml.etree.ElementTree as ET

    # Read the MusicXML file using read_musicxml_file
    root = read_musicxml_file(filename)
    
    # Namespace handling
    if root.tag.startswith('{'):
        ns_uri = root.tag[root.tag.find('{')+1:root.tag.find('}')]
        def ns_tag(tag):
            return f'{{{ns_uri}}}{tag}'
    else:
        def ns_tag(tag):
            return tag  # No namespace
    
    # Get initial tempo from the first direction element, default to 120
    initial_tempo = 120.0
    first_direction = root.find('.//' + ns_tag('direction'))
    if first_direction is not None:
        sound_elem = first_direction.find(ns_tag('sound'))
        if sound_elem is not None and 'tempo' in sound_elem.attrib:
            initial_tempo = float(sound_elem.attrib['tempo'])
    
    # Process each part
    notes = []
    for part_index, part_elem in enumerate(root.findall(ns_tag('part'))):
        part_notes = parse_part(
            part_elem,
            ns_tag=ns_tag,
            part_index=part_index,
            initial_tempo=initial_tempo
        )
        notes.extend(part_notes)
    
    # Create a Song instance with the notes
    song = Song(notes=notes)
    return song


