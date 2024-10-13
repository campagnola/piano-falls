import zipfile
import xml.etree.ElementTree as ET
from .song import Song, Pitch, Note


def load_musicxml(filename):
    parser = MusicXMLParser()
    return parser.parse(filename)


import zipfile
import xml.etree.ElementTree as ET
from .song import Song, Pitch, Note

class MusicXMLParser:
    def __init__(self):
        # Initialize parser state
        self.divisions = 1  # Default divisions per quarter note
        self.tempo = 120.0  # Default tempo in BPM
        self.key_signature = 0  # Default key signature (C major/a minor)
        self.time_signature = (4, 4)  # Default time signature
        self.voice_current_times = {}  # Keeps track of current_time for each voice
        self.ties = {}  # Keep track of ongoing ties per voice
        self.notes = []
        self.cumulative_time = 0.0  # Cumulative time up to the current measure
        self.part_info = {}
        self.ns_map = {}
        self.ns_tag = lambda tag: tag  # Default namespace handler

    def get_local_tag(self, tag):
        """Extract the local tag name without namespace."""
        if '}' in tag:
            return tag.split('}', 1)[1]
        else:
            return tag

    def read_musicxml_file(self, filename):
        if filename.lower().endswith('.mxl'):
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
                    if (name.endswith('.xml') or name.endswith('.musicxml')) and '/' not in name:
                        score_data = zf.read(name)
                        root = ET.fromstring(score_data)
                        return root
                raise Exception('No MusicXML file found in the MXL archive.')
        else:
            # It's an uncompressed MusicXML file
            tree = ET.parse(filename)
            return tree.getroot()

    def parse(self, filename):
        # Read the MusicXML file
        root = self.read_musicxml_file(filename)
        
        # Namespace handling
        if root.tag.startswith('{'):
            ns_uri = root.tag[root.tag.find('{')+1:root.tag.find('}')]
            self.ns_map[''] = ns_uri
            def ns_tag(tag):
                return f'{{{ns_uri}}}{tag}'
        else:
            def ns_tag(tag):
                return tag
        
        self.ns_tag = ns_tag  # Save ns_tag function for later use
        
        # Read the part list
        self.part_info = {}
        part_list_elem = root.find(ns_tag('part-list'))
        if part_list_elem is not None:
            for score_part_elem in part_list_elem.findall(ns_tag('score-part')):
                part_id = score_part_elem.attrib['id']
                self.part_info[part_id] = {}
                part_name_elem = score_part_elem.find(ns_tag('part-name'))
                if part_name_elem is not None:
                    self.part_info[part_id]['name'] = part_name_elem.text
                # Instrument
                instrument_elem = score_part_elem.find(ns_tag('score-instrument'))
                if instrument_elem is not None:
                    instrument_name_elem = instrument_elem.find(ns_tag('instrument-name'))
                    if instrument_name_elem is not None:
                        self.part_info[part_id]['instrument'] = instrument_name_elem.text
        
        # Process each part
        parts = root.findall(ns_tag('part'))
        assert parts, 'No parts found in the MusicXML file'
        for part_index, part_elem in enumerate(parts):
            self.parse_part(part_elem, part_index)
        
        assert self.notes, 'No notes found in the MusicXML file'
        
        # Create a Song instance with the notes
        song = Song(notes=self.notes)
        return song

    def parse_part(self, part_elem, part_index):
        # Reset parser state for the new part
        self.voice_current_times = {}
        self.ties = {}
        self.divisions = 1
        self.tempo = 120.0
        self.key_signature = 0
        self.time_signature = (4, 4)
        self.cumulative_time = 0.0  # Reset cumulative time for the part

        # Iterate through measures
        for measure_elem in part_elem.findall(self.ns_tag('measure')):
            measure_notes, measure_duration = self.parse_measure(measure_elem)

            # Adjust note start times by adding cumulative_time
            for note in measure_notes:
                note.start_time += self.cumulative_time
                # Annotate notes with part information
                part_id = part_elem.attrib['id']
                note.track_n = part_index
                note.track = self.part_info.get(part_id, {}).get('name', f'Part {part_index}')

            # Update cumulative_time
            self.cumulative_time += measure_duration

            self.notes.extend(measure_notes)

    def parse_measure(self, measure_elem):
        """
        Parse a measure element and return a list of Note instances with start times relative to the measure.

        Returns:
        - notes: List of Note instances.
        - measure_duration: Duration of the measure in seconds.
        """
        notes = []

        # Check if the measure is implicit (e.g., pickup measure)
        implicit = measure_elem.attrib.get('implicit', 'no') == 'yes'

        # Initialize measure start time
        measure_start_time = 0.0  # Start at 0.0 within the measure

        # Process measure elements
        measure_elements = list(measure_elem)
        i = 0
        while i < len(measure_elements):
            elem = measure_elements[i]
            tag = self.get_local_tag(elem.tag)

            if tag == "attributes":
                self.parse_attributes(elem)
                i += 1

            elif tag == "direction":
                self.parse_direction(elem)
                i += 1

            elif tag == "note":
                note_elems, i = self.collect_chord_notes(measure_elements, i)
                new_notes = self.process_notes(note_elems)
                notes.extend(new_notes)

            elif tag in ("backup", "forward"):
                self.handle_backup_forward(elem, tag)
                i += 1

            else:
                i += 1

        # Calculate measure duration
        measure_duration = self.calculate_measure_duration(measure_start_time, implicit)

        return notes, measure_duration

    def process_notes(self, note_elems):
        """
        Processes a list of note elements and returns Note objects with start times relative to the measure.

        Returns:
        - notes: List of Note instances.
        """
        notes = []
        first_note_elem = note_elems[0]
        voice_number = self.get_voice_and_staff(first_note_elem)[0]

        # Initialize current_time for this voice if not already set
        if voice_number not in self.voice_current_times:
            self.voice_current_times[voice_number] = 0.0  # Start at 0.0 within the measure
        current_time = self.voice_current_times[voice_number]

        # Process all chord notes
        duration_seconds = None
        for note_elem in note_elems:
            note_obj, note_duration_seconds, note_voice_number = self.parse_note_element(
                note_elem, current_time_override=current_time)
            if note_obj:
                # Do not adjust note.start_time here
                notes.append(note_obj)
            duration_seconds = note_duration_seconds  # All chord notes share the same duration

        # Advance current_time for the voice after processing
        self.voice_current_times[voice_number] = current_time + duration_seconds

        return notes

    def collect_chord_notes(self, measure_elements, index):
        """
        Collects notes that are part of the same chord starting from the given index.

        Returns:
        - chord_notes: List of note elements that form the chord.
        - next_index: The index to continue parsing from.
        """
        note_elem = measure_elements[index]
        chord_notes = [note_elem]
        index += 1
        while index < len(measure_elements):
            next_elem = measure_elements[index]
            next_tag = self.get_local_tag(next_elem.tag)
            if next_tag == "note":
                chord_elem = next_elem.find(self.ns_tag('chord'))
                if chord_elem is not None:
                    chord_notes.append(next_elem)
                    index += 1
                else:
                    break  # Not a chord note
            else:
                break  # Not a note
        return chord_notes, index

    def handle_backup_forward(self, elem, tag):
        """
        Handles backup and forward elements to adjust the current time.

        Parameters:
        - elem: The XML element representing the backup or forward.
        - tag: The tag name ('backup' or 'forward').
        """
        duration_elem = elem.find(self.ns_tag('duration'))
        if duration_elem is not None:
            duration_divisions = int(duration_elem.text)
            duration = (duration_divisions / self.divisions) * (60.0 / self.tempo)
            # Adjust current_time for all voices
            for voice in self.voice_current_times:
                if tag == "backup":
                    self.voice_current_times[voice] -= duration
                elif tag == "forward":
                    self.voice_current_times[voice] += duration

    def calculate_measure_duration(self, measure_start_time, implicit):
        """
        Calculates the duration of the measure.

        Parameters:
        - measure_start_time: The start time of the measure.
        - implicit: Boolean indicating if the measure is implicit (pickup measure).

        Returns:
        - measure_duration: The duration of the measure in seconds.
        """
        # Get the expected measure duration based on time signature
        beats, beat_type = self.time_signature
        # Calculate the duration of one beat in seconds
        beat_duration = (60.0 / self.tempo) * (4 / beat_type)
        expected_measure_duration = beats * beat_duration

        if implicit:
            # For implicit measures, measure duration is the maximum of voice times minus measure start time
            measure_end_time = max(self.voice_current_times.values()) if self.voice_current_times else measure_start_time
            measure_duration = measure_end_time - measure_start_time
        else:
            # For explicit measures, measure duration is expected_measure_duration
            measure_duration = expected_measure_duration

            # If the total duration of notes and rests is less than expected, we need to adjust the voice_current_times
            # Add implicit rests to fill the measure
            for voice in self.voice_current_times:
                voice_time = self.voice_current_times[voice]
                if voice_time - measure_start_time < expected_measure_duration:
                    # Advance the current_time to the end of the measure
                    self.voice_current_times[voice] = measure_start_time + expected_measure_duration

        return measure_duration


    def parse_attributes(self, attributes_elem):
        # Divisions
        divisions_elem = attributes_elem.find(self.ns_tag('divisions'))
        if divisions_elem is not None:
            self.divisions = int(divisions_elem.text)
        # Key signature
        key_elem = attributes_elem.find(self.ns_tag('key'))
        if key_elem is not None:
            fifths_elem = key_elem.find(self.ns_tag('fifths'))
            if fifths_elem is not None:
                self.key_signature = int(fifths_elem.text)
        # Time signature
        time_elem = attributes_elem.find(self.ns_tag('time'))
        if time_elem is not None:
            beats_elem = time_elem.find(self.ns_tag('beats'))
            beat_type_elem = time_elem.find(self.ns_tag('beat-type'))
            if beats_elem is not None and beat_type_elem is not None:
                beats = int(beats_elem.text)
                beat_type = int(beat_type_elem.text)
                self.time_signature = (beats, beat_type)

    def parse_direction(self, direction_elem):
        # Handle tempo changes
        sound_elem = direction_elem.find(self.ns_tag('sound'))
        if sound_elem is not None and 'tempo' in sound_elem.attrib:
            self.tempo = float(sound_elem.attrib['tempo'])

    def get_voice_and_staff(self, note_elem):
        # Get voice number (default to 1 if not specified)
        voice_elem = note_elem.find(self.ns_tag('voice'))
        voice_number = int(voice_elem.text) if voice_elem is not None else 1

        # Get staff number (default to 1 if not specified)
        staff_elem = note_elem.find(self.ns_tag('staff'))
        staff_number = int(staff_elem.text) if staff_elem is not None else 1

        return voice_number, staff_number


    def get_duration(self, note_elem):
        # Get duration in divisions
        duration_elem = note_elem.find(self.ns_tag('duration'))
        duration_divisions = int(duration_elem.text) if duration_elem is not None else 0

        # Handle time-modification (e.g., tuplets)
        time_mod_elem = note_elem.find(self.ns_tag('time-modification'))
        if time_mod_elem is not None:
            actual_notes_elem = time_mod_elem.find(self.ns_tag('actual-notes'))
            normal_notes_elem = time_mod_elem.find(self.ns_tag('normal-notes'))
            if actual_notes_elem is not None and normal_notes_elem is not None:
                actual_notes = int(actual_notes_elem.text)
                normal_notes = int(normal_notes_elem.text)
                # Adjust duration_divisions
                duration_divisions = duration_divisions * normal_notes / actual_notes

        # Calculate duration in seconds
        duration = (duration_divisions / self.divisions) * (60.0 / self.tempo)
        return duration_divisions, duration


    def process_pitch(self, note_elem):
        pitch_elem = note_elem.find(self.ns_tag('pitch'))
        if pitch_elem is None:
            return None  # Rest or unpitched note

        step = pitch_elem.find(self.ns_tag('step')).text
        octave = int(pitch_elem.find(self.ns_tag('octave')).text)

        # Initial alter value
        alter_elem = pitch_elem.find(self.ns_tag('alter'))
        alter = int(alter_elem.text) if alter_elem is not None else 0

        # Process accidental element if present
        accidental_elem = note_elem.find(self.ns_tag('accidental'))
        if accidental_elem is not None:
            accidental_text = accidental_elem.text.strip()
            # Map accidental to alter value
            accidental_map = {
                'flat': -1,
                'sharp': 1,
                'natural': 0,
                'double-flat': -2,
                'double-sharp': 2,
                'flat-flat': -2,
                'sharp-sharp': 2,
            }
            accidental_alter = accidental_map.get(accidental_text)
            if accidental_alter is not None:
                alter = accidental_alter

        # Adjust for key signature if no alter or accidental is specified
        if alter_elem is None and accidental_elem is None:
            accidentals = self.get_key_signature_accidentals()
            if step in accidentals:
                if self.key_signature > 0:
                    alter += 1  # Apply sharp
                elif self.key_signature < 0:
                    alter -= 1  # Apply flat

        # Map step to semitone
        step_to_semitone = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        semitone = step_to_semitone[step] + alter

        # Calculate MIDI note number
        midi_note = (octave + 1) * 12 + semitone

        return midi_note


    def get_key_signature_accidentals(self):
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
        return key_signature_accidentals.get(self.key_signature, [])

    def parse_note_element(self, note_elem, current_time_override=None):
        # Check if it's a rest
        is_rest = note_elem.find(self.ns_tag('rest')) is not None

        # Get voice and staff numbers
        voice_number, staff_number = self.get_voice_and_staff(note_elem)

        # Get duration
        duration_divisions, duration = self.get_duration(note_elem)
        duration_seconds = duration

        # Get the current_time for this voice
        if current_time_override is not None:
            current_time = current_time_override
        else:
            current_time = self.voice_current_times.get(voice_number, 0.0)

        if is_rest:
            # Return None since we don't need to create a Note object for a rest
            return None, duration_seconds, voice_number
        else:
            # Process pitch
            midi_note = self.process_pitch(note_elem)
            if midi_note is None:
                # Unpitched note or rest
                return None, duration_seconds, voice_number

            # Create the note object
            note_obj = Note(
                start_time=current_time,
                pitch=Pitch(midi_note=midi_note),
                duration=duration,
                staff=staff_number,
                voice=voice_number
            )

            return note_obj, duration_seconds, voice_number
