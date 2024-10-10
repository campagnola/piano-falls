import zipfile
import xml.etree.ElementTree as ET
from .song import Song, Pitch, Note


def read_musicxml_file(filename):
    import zipfile
    import xml.etree.ElementTree as ET

    if filename.lower().endswith('.mxl'):
        # It's a compressed MusicXML file
        with zipfile.ZipFile(filename, 'r') as zf:
            # Try to read container.xml to find the rootfile
            try:
                container_data = zf.read('META-INF/container.xml')
                container_root = ET.fromstring(container_data)
                # Find the rootfile
                rootfile_elem = container_root.find('.//rootfile')
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
                if name.endswith('.xml') or name.endswith('.musicxml') and '/' not in name:
                    score_data = zf.read(name)
                    root = ET.fromstring(score_data)
                    return root
            raise Exception('No MusicXML file found in the MXL archive.')
    else:
        # It's an uncompressed MusicXML file
        tree = ET.parse(filename)
        return tree.getroot()


def parse_part(part_elem, initial_tempo=120.0):
    """
    Parse a <part> element and return a list of Note instances.
    """
    notes = []
    divisions = 1  # Default divisions per quarter note
    tempo = initial_tempo  # Use initial_tempo parameter
    key_signature = 0  # Default key signature (C major/a minor)
    time_signature = (4, 4)  # Default time signature
    voice_current_times = {}  # Keeps track of current_time for each voice
    ties = {}  # Keep track of ongoing ties per voice

    # Iterate through measures
    for measure_elem in part_elem.findall('measure'):
        # Handle attributes (divisions, key signature, time signature)
        attributes_elem = measure_elem.find('attributes')
        if attributes_elem is not None:
            # Divisions descrbe the number of divisions per quarter note.
            # Note durations are expressed in terms of these divisions.
            divisions_elem = attributes_elem.find('divisions')
            if divisions_elem is not None:
                divisions = int(divisions_elem.text)
            # Key signature
            key_elem = attributes_elem.find('key')
            if key_elem is not None:
                fifths_elem = key_elem.find('fifths')
                if fifths_elem is not None:
                    key_signature = int(fifths_elem.text)
            # Time signature
            time_elem = attributes_elem.find('time')
            if time_elem is not None:
                beats_elem = time_elem.find('beats')
                beat_type_elem = time_elem.find('beat-type')
                if beats_elem is not None and beat_type_elem is not None:
                    beats = int(beats_elem.text)
                    beat_type = int(beat_type_elem.text)
                    time_signature = (beats, beat_type)

        # Handle tempo changes within the measure
        direction_elems = measure_elem.findall('direction')
        for direction in direction_elems:
            sound_elem = direction.find('sound')
            if sound_elem is not None and 'tempo' in sound_elem.attrib:
                tempo = float(sound_elem.attrib['tempo'])

        # Parse the measure
        measure_notes = parse_measure(
            measure_elem, divisions, tempo, voice_current_times, key_signature, ties
        )
        notes.extend(measure_notes)
    return notes


def parse_measure(measure_elem, divisions, tempo, voice_current_times, key_signature, ties):
    """
    Parse a measure element and return a list of Note instances.
    """
    notes = []

    # Get all measure child elements in order
    measure_elements = list(measure_elem)
    i = 0
    while i < len(measure_elements):
        elem = measure_elements[i]
        tag = elem.tag

        if tag == "attributes":
            # Handle attributes within the measure (if any)
            i += 1

        elif tag == "direction":
            # Handle tempo changes
            sound_elem = elem.find('sound')
            if sound_elem is not None and 'tempo' in sound_elem.attrib:
                tempo = float(sound_elem.attrib['tempo'])
            i += 1

        elif tag == "note":
            note_elem = elem
            chord_notes = []
            # Get voice number
            voice_elem = note_elem.find('voice')
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
                if next_elem.tag == f"note":
                    # Check if this note has <chord/> element
                    chord_elem = next_elem.find('chord')
                    if chord_elem is not None:
                        chord_notes.append(next_elem)
                        i += 1
                    else:
                        break  # Not part of the chord
                else:
                    break  # Not a note element

            # Process the chord notes
            chord_note_objs = []
            max_duration_divisions = 0
            for chord_note_elem in chord_notes:
                note_obj, duration_divisions, voice_number, is_chord_note, is_rest, _ = parse_note_element(
                    chord_note_elem, divisions, tempo, voice_time, key_signature
                )
                if note_obj:
                    # Handle ties
                    tie_elems = chord_note_elem.findall('tie')
                    tie_types = [tie_elem.attrib.get('type') for tie_elem in tie_elems]

                    if 'start' in tie_types and 'stop' not in tie_types:
                        # Start of a tie
                        ties[voice_number] = note_obj
                        continue  # Do not add to notes yet
                    elif 'stop' in tie_types and 'start' not in tie_types:
                        # End of a tie
                        if voice_number in ties:
                            prev_note = ties.pop(voice_number)
                            # Combine durations
                            prev_note.duration += note_obj.duration
                            # Do not add the current note separately
                            note_obj = prev_note
                        else:
                            # No matching tie start, add as is
                            pass
                    elif 'start' in tie_types and 'stop' in tie_types:
                        # Both start and stop (middle of a tie)
                        if voice_number in ties:
                            prev_note = ties[voice_number]
                            # Combine durations
                            prev_note.duration += note_obj.duration
                            # Keep the tie ongoing
                            ties[voice_number] = prev_note
                            continue  # Do not add to notes yet
                        else:
                            ties[voice_number] = note_obj
                            continue  # Do not add to notes yet
                    else:
                        # No tie, but check if continuing a tie
                        if voice_number in ties:
                            prev_note = ties.pop(voice_number)
                            prev_note.duration += note_obj.duration
                            note_obj = prev_note

                    chord_note_objs.append(note_obj)
                if duration_divisions > max_duration_divisions:
                    max_duration_divisions = duration_divisions

            notes.extend(chord_note_objs)

            # Update current_time for the voice after processing the chord
            duration_seconds = (max_duration_divisions / divisions) * (60.0 / tempo)
            voice_current_times[voice_number] += duration_seconds

        else:
            # Other elements
            i += 1

    return notes


def parse_note(note_elem, divisions, tempo, current_time, part_index):
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
    chord_elem = note_elem.find('chord')
    if chord_elem is not None:
        is_chord = True

    # Parse the note
    note_data, duration_divisions, voice_number, is_chord_note, is_rest, updated_current_time = parse_note_element(
        note_elem, divisions, tempo, current_time, part_index
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


def parse_note_element(elem, divisions, tempo, current_time, key_signature):
    """
    Parse a MusicXML <note> element and return:
    - note_obj: The Note instance or None if it's a rest.
    - duration_divisions: The duration of the note in divisions.
    - voice_number: The voice number of the note.
    - is_chord: Boolean indicating if the note is part of a chord.
    - is_rest: Boolean indicating if the note is a rest.
    - updated_current_time: The updated current_time after the note.
    """
    # Get voice number (default to 1 if not specified)
    voice_elem = elem.find('voice')
    voice_number = int(voice_elem.text) if voice_elem is not None else 1

    # Get duration in divisions
    duration_elem = elem.find('duration')
    duration_divisions = int(duration_elem.text) if duration_elem is not None else 0

    # Handle time-modification (e.g., tuplets)
    time_mod_elem = elem.find('time-modification')
    if time_mod_elem is not None:
        actual_notes_elem = time_mod_elem.find('actual-notes')
        normal_notes_elem = time_mod_elem.find('normal-notes')
        if actual_notes_elem is not None and normal_notes_elem is not None:
            actual_notes = int(actual_notes_elem.text)
            normal_notes = int(normal_notes_elem.text)
            # Adjust duration_divisions
            duration_divisions *= (normal_notes / actual_notes)

    # Check for 'chord' element
    is_chord = elem.find('chord') is not None

    # Check if it's a rest
    is_rest = elem.find('rest') is not None

    # Get staff number (default to 1 if not specified)
    staff_elem = elem.find('staff')
    staff_number = int(staff_elem.text) if staff_elem is not None else 1

    # For rests, advance current_time by the duration
    if is_rest:
        duration = (duration_divisions / divisions) * (60.0 / tempo)
        updated_current_time = current_time + duration
        return None, duration_divisions, voice_number, is_chord, is_rest, updated_current_time

    # For chords, the start_time remains the same
    start_time = current_time

    # Process note
    pitch_elem = elem.find('pitch')
    if pitch_elem is not None:
        step = pitch_elem.find('step').text
        octave = int(pitch_elem.find('octave').text)
        alter_elem = pitch_elem.find('alter')
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

        # Create the note dict
        note_obj = Note(
            start_time=start_time,
            pitch=Pitch(midi_note=midi_note),
            duration=duration,
            staff=staff_number,
            voice=voice_number
        )

        # For chords, do not update current_time here
        updated_current_time = current_time + (duration if not is_chord else 0)

        return note_obj, duration_divisions, voice_number, is_chord, is_rest, updated_current_time

    return None, duration_divisions, voice_number, is_chord, is_rest, current_time


def load_musicxml(filename):
    """
    Load a MusicXML file and return a Song instance.
    """
    import xml.etree.ElementTree as ET

    # Read the MusicXML file using read_musicxml_file
    root = read_musicxml_file(filename)
    
    # read the part list
    part_info = {}
    part_list_elem = root.find('part-list')
    if part_list_elem is not None:
        for score_part_elem in part_list_elem.findall('score-part'):
            part_id = score_part_elem.attrib['id']
            part_info[part_id] = {}
            part_name_elem = score_part_elem.find('part-name')
            if part_name_elem is not None:
                part_info[part_id]['name'] = part_name_elem.text
            # instrument
            instrument_elem = score_part_elem.find('score-instrument')
            if instrument_elem is not None:
                instrument_name_elem = instrument_elem.find('instrument-name')
                if instrument_name_elem is not None:
                    part_info[part_id]['instrument'] = instrument_name_elem.text

    # Process each part
    notes = []
    parts = root.findall('part')
    assert parts, 'No parts found in the MusicXML file'
    for part_index, part_elem in enumerate(parts):
        # read notes for this part
        part_notes = parse_part(part_elem)
        # annotate notes with part information
        for note in part_notes:
            note.track_n = part_index
            part_id = part_elem.attrib['id']
            note.track = part_info.get(part_id, {}).get('name', f'Part {part_index}')
        notes.extend(part_notes)
    
    assert notes, 'No notes found in the MusicXML file'

    # Create a Song instance with the notes
    song = Song(notes=notes)
    return song
