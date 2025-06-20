import music21
from .song import Song, Note, Pitch, Part


def load_musicxml_music21(filename):
    # Parse the MusicXML file
    score = music21.converter.parse(filename)
    
    # Flatten the score to access all elements
    flat_score = score.flat
    
    # Alternatively, use secondsMap if timing issues arise
    seconds_map = flat_score.secondsMap
    
    # Initialize an empty list to hold events
    events = []
    
    # Iterate over all elements in the flat score or seconds_map
    for element_info in seconds_map:
        element = element_info['element']
        if isinstance(element, music21.note.Note):
            # Extract timing information
            start_time = element_info['offsetSeconds']
            duration = element_info['durationSeconds']
            
            # Extract pitch information
            midi_note = element.pitch.midi
            pitch = Pitch(midi_note=midi_note)
            
            # Extract part (instrument) information
            part = element.getContextByClass(music21.stream.Part)
            part_name = part.partName if part and part.partName else "Unknown Part"
            part_obj = Part(name=part_name)
            
            # Extract staff information
            # staff = element.staff if element.staff else 1
            
            # Create a Note instance
            note = Note(
                pitch=pitch,
                start_time=start_time,
                duration=duration,
                part=part_obj,
                # staff=staff
            )
            
            # Add the note to events
            events.append(note)
    
    # Create and return a Song instance
    return Song(events)



from typing import List
import zipfile, os, shutil
import xml.etree.ElementTree as ET
from .song import (Song, Pitch, Note, Rest, Event, Barline, Part,
                   TempoChange, KeySignatureChange, TimeSignatureChange)


def load_musicxml(filename, add_line_numbers=False):
    parser = MusicXMLParser()
    return parser.parse(filename, add_line_numbers=add_line_numbers)


class MusicXMLParser:
    def __init__(self):
        # Initialize parser state
        self.divisions_per_quarter = 1  # Default divisions per quarter note
        self.tempo = 120.0  # Default tempo in BPM
        self.key_signature = 0  # Default key signature (C major/a minor)
        self.time_signature = (4, 4)  # Default time signature
        self.current_time = 0
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

    def read_musicxml_file(self, filename, add_line_numbers=False):
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
                        # parse such that we can keep track of line numbers
                        return read_xml_with_line_numbers(score_data, add_line_numbers=add_line_numbers)
                except (KeyError, ET.ParseError):
                    # No container.xml or unable to parse it
                    pass

                # Fallback: search for the first .xml or .musicxml file in the zip archive
                for name in zf.namelist():
                    if (name.endswith('.xml') or name.endswith('.musicxml')) and '/' not in name:
                        score_data = zf.read(name)
                        return read_xml_with_line_numbers(score_data, add_line_numbers=add_line_numbers)
                raise Exception('No MusicXML file found in the MXL archive.')
        else:
            # It's an uncompressed MusicXML file
            score_data = open(filename, 'rb').read()            
            return read_xml_with_line_numbers(score_data, add_line_numbers=add_line_numbers)

    def parse(self, filename, add_line_numbers=False):
        # Read the MusicXML file
        root = self.read_musicxml_file(filename, add_line_numbers=add_line_numbers)
        
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
        parsed_parts = []
        for part_elem in parts:
            part = self.parse_part(part_elem)
            parsed_parts.append(part)

        # Collate all measures from all parts
        all_measures:List[List[Measure]] = []
        for part in parsed_parts:
            for i,measure in enumerate(part):
                if i >= len(all_measures):
                    all_measures.append([])
                all_measures[i].append(measure) 

        # assign real start times and durations to notes
        all_notes = self.calculate_event_times(all_measures)

        # Create a Song instance with the notes
        song = Song(events=all_notes)
        return song

    def calculate_event_times(self, all_measures) -> List[Event]:
        all_notes = []
        current_time = 0
        current_tempo = 120
        class NoteStopEvent(Event):
            def __init__(self, note):
                self.note = note
                self.start_quarters = note.start_quarters + note.duration_quarters
                Event.__init__(self, start_time=None, duration=0, duration_quarters=0)
            def __repr__(self):
                return f"<NoteStopEvent {self.note}>"

        for measures in all_measures:
            last_time_quarters = 0

            # collect all events in this measure, across all parts
            events = []
            for measure in measures:
                events.extend(measure.events)
            # for events with nonzero duration, also add a stop event
            for ev in events:
                if getattr(ev, 'debug', False):
                    print(f"DEBUG picked up event: {ev}")
                if ev.duration_quarters > 0:
                    events.append(NoteStopEvent(ev))
            # sort all events in the measure by start time
            events.sort(key=lambda ev: ev.start_quarters)

            # assign real start times and durations to notes
            for ev in events:
                # calculate change in time since last event
                dq = ev.start_quarters - last_time_quarters
                dt = dq * 60 / current_tempo
                current_time += dt
                last_time_quarters = ev.start_quarters

                # set start time of this event
                ev.start_time = current_time
                if getattr(ev, 'debug', False):
                    print(f"DEBUG assigned start time: {ev}")
                
                # if this is a tempo change, update the current tempo
                if isinstance(ev, TempoChange):
                    current_tempo = ev.tempo

                # if this is a stop event, remove the corresponding note from active events
                # and set its duration
                if isinstance(ev, NoteStopEvent):
                    ev.note.duration = current_time - ev.note.start_time
                    if ev.note.debug:
                        print(f"DEBUG assigned duration: {ev}")
                else:
                    all_notes.append(ev)

                assert ev.start_time is not None, f"Event {ev} has no start time"
            
                
            all_notes.append(Barline(start_time=current_time))

        # run through all events and merge tied notes
        merged_notes = []
        tied_notes = {}
        for ev in all_notes:
            if not isinstance(ev, Note):
                merged_notes.append(ev)
                continue
            tie_key = (ev.part, ev.staff, ev.pitch.midi_note)
            # Handle tie start/stop
            if 'stop' in ev.tie_types:
                try:
                    # This note is tied to a previous note; extend the duration of the previous note
                    # and skip adding this note to the list
                    tied_note = tied_notes.pop(tie_key)
                    tied_note.duration = ev.start_time + ev.duration - tied_note.start_time
                except KeyError:
                    print(f"Warning: Tie stop event without corresponding start event: {ev}")
                    print(f"   current ties: {tied_notes}")
            else:
                merged_notes.append(ev)

            if 'start' in ev.tie_types:  # note can be both a stop and start!
                tied_notes[tie_key] = ev

        # offset all start times such that the first playable note starts at time 0
        offset = None
        for ev in merged_notes:
            if offset is None and isinstance(ev, Note):
                offset = ev.start_time
            if offset is not None:
                ev.start_time -= offset
            assert ev.duration is not None

        return merged_notes

    def parse_part(self, part_elem):
        """Collect all notes and other events in this part, return a list of measures

        Each measure contains a set of events with attributes start_quarters and duration_quarters,
        where start_quarters is the number of quarter notes since the beginning of the measure when the
        event starts.
        """
        # Reset parser state for the new part
        self.ties = {}
        self.divisions_per_quarter = None
        self.key_signature = None
        self.time_signature = None

        # Iterate through measures, collecting all notes/rests/etc
        measure_elements = part_elem.findall(self.ns_tag('measure'))
        measures = [self.parse_measure(measure_elem) for measure_elem in measure_elements]
        part_id = part_elem.attrib['id']
        part_info = self.part_info.get(part_id, {})
        part_info['id'] = part_id
        part = MusicXMLPart(part_info, measures)        
        # each measure is a list of musical elements (notes, rests, changes, etc) having a start time
        # and optional duration in quarter notes relative to the measure beginning

        # adjust times for grace notes with stolen time
        part.handle_stolen_time()

        for measure in measures:
            measure.set_part(part)

        return part
 
    def parse_measure(self, measure_elem):
        """
        Parse a measure element and return a list of Note instances with start times relative to the measure.

        Returns:
        - notes: List of Note instances.
        - measure_duration: Duration of the measure in seconds.
        """
        measure_number = int(measure_elem.attrib['number'])

        items = []

        # Track time for this measure in quarters since divisions and tempo may change at any time
        current_quarters = 0

        last_non_chord_note = None

        # Process measure elements
        items = []
        for elem in measure_elem:
            tag = self.get_local_tag(elem.tag)
            if tag == "attributes":
                attributes = self.parse_attributes(elem)
                for item in attributes:
                    item.start_quarters = current_quarters
                # items should include updates to key signature, time signature, divisions, etc.
                items.extend(attributes)

            elif tag == "direction":
                items.extend(self.parse_direction(elem, current_quarters))

            elif tag == "note":
                item = self.parse_note_element(elem)
                item.measure_number = measure_number
                item.start_quarters = current_quarters
                item.repr_keys = item.repr_keys.copy()
                item.repr_keys.extend(['start_quarters', 'duration_quarters', 'measure_number'])
                items.append(item)

                # advance clock unless this is a chord note
                if not item.is_chord:
                    last_non_chord_note = item
                    current_quarters += item.duration_quarters
                else:
                    # if this is a chord note, set the start time to the last non-chord note
                    item.start_quarters = last_non_chord_note.start_quarters

            elif tag in ("backup", "forward"):
                duration_elem = elem.find(self.ns_tag('duration'))
                if duration_elem is not None:
                    duration_quarters = int(duration_elem.text) / self.divisions_per_quarter
                    if tag == "backup":
                        current_quarters -= duration_quarters
                    elif tag == "forward":
                        current_quarters += duration_quarters

            elif tag in ("print", "harmony", "barline"):
                # ignore these tags for now (we should handle chord names eventually)
                pass

            else:
                print(f"Warning: Ignoring unsupported element inside measure: {tag}")

        measure = Measure(measure_number, events=items)
        for item in items:
            item.measure = measure            
       
        return measure

    def parse_attributes(self, attributes_elem):
        attr_events = []
        for attr in attributes_elem:
            tag = self.get_local_tag(attr.tag)
            if tag == 'divisions':
                self.divisions_per_quarter = int(attr.text)
                # do we need to remember these?
                # attr_events.append(DivisionsChange(int(attr.text)))
            elif tag == 'key':
                fifths = int(attr.find(self.ns_tag('fifths')).text)
                attr_events.append(KeySignatureChange(fifths, duration_quarters=0))
            elif tag == 'time':
                beats = int(attr.find(self.ns_tag('beats')).text)
                beat_type = int(attr.find(self.ns_tag('beat-type')).text)
                attr_events.append(TimeSignatureChange(beats, beat_type, duration_quarters=0))
            elif tag in ['clef', 'staves']:
                # ignore these for now
                pass
            else:
                print(f"Warning: Ignoring unsupported attribute: {tag}")

        return attr_events

    def parse_direction(self, direction_elem, current_quarters):
        items = []
        sound_elem = direction_elem.find(self.ns_tag('sound'))
        if sound_elem is not None and 'tempo' in sound_elem.attrib:
            tempo = float(sound_elem.attrib['tempo'])
            items.append(TempoChange(start_quarters=current_quarters, duration_quarters=0, tempo=tempo))
        return items

    def get_voice_and_staff(self, note_elem):
        # Get voice number (default to 1 if not specified)
        voice_elem = note_elem.find(self.ns_tag('voice'))
        voice_number = int(voice_elem.text) if voice_elem is not None else 1

        # Get staff number (default to 1 if not specified)
        staff_elem = note_elem.find(self.ns_tag('staff'))
        staff_number = int(staff_elem.text) if staff_elem is not None else 1

        return voice_number, staff_number

    def get_note_duration(self, note_elem):
        """Get the duration of a note 
        
        Returns
        -------
        duration_divisions : int
            Duration of the note in divisions
        stolen_time : float
            Time stolen from the next (positive values) or previous (negative values) note
        grace_elem : Element | None
            The grace element if the note is a grace note, otherwise None
        """
        # by default, time is not stolen
        stolen_time = 0.0

        # Get duration in divisions
        duration_elem = note_elem.find(self.ns_tag('duration'))
        duration_divisions = int(duration_elem.text) if duration_elem is not None else 0

        # Handle time-modification (e.g., tuplets)
        # NOPE - even when a tuplet is specified, the duration should still be correct
        # time_mod_elem = note_elem.find(self.ns_tag('time-modification'))
        # if time_mod_elem is not None:
        #     actual_notes_elem = time_mod_elem.find(self.ns_tag('actual-notes'))
        #     normal_notes_elem = time_mod_elem.find(self.ns_tag('normal-notes'))
        #     if actual_notes_elem is not None and normal_notes_elem is not None:
        #         actual_notes = int(actual_notes_elem.text)
        #         normal_notes = int(normal_notes_elem.text)
        #         # Adjust duration_divisions
        #         duration_divisions = duration_divisions * normal_notes / actual_notes

        # Handle grace notes
        grace_elem = note_elem.find(self.ns_tag('grace'))
        if grace_elem is not None:
            # if make-time attribute is present, use it to calculate the duration in divisions
            if 'make-time' in grace_elem.attrib:
                duration_divisions = float(grace_elem.attrib['make-time'])
            elif 'steal-time-following' in grace_elem.attrib:
                stolen_time = float(grace_elem.attrib['steal-time-following'])
            elif 'steal-time-previous' in grace_elem.attrib:
                stolen_time = -float(grace_elem.attrib['steal-time-previous'])
            else:
                stolen_time = 'default'  # no timing specified; decide later

        return duration_divisions, stolen_time, grace_elem

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
            accidentals = key_signature_accidentals.get(self.key_signature, [])
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

        return Pitch(midi_note=midi_note)

    def parse_note_element(self, note_elem):
        # Check if it's a rest
        is_rest = note_elem.find(self.ns_tag('rest')) is not None

        # Get voice and staff numbers
        voice_number, staff_number = self.get_voice_and_staff(note_elem)

        # Get duration
        duration_divisions, stolen_time, grace_elem = self.get_note_duration(note_elem)
        duration_quarters = duration_divisions / self.divisions_per_quarter

        # Get tie
        tie_elems = note_elem.findall(self.ns_tag('tie'))
        tie_types = [tie_elem.attrib['type'] for tie_elem in tie_elems]

        # Get chord
        is_chord = note_elem.find(self.ns_tag('chord')) is not None

        # get type
        type_elem = note_elem.find(self.ns_tag('type'))
        note_type = None if type_elem is None else type_elem.text

        is_grace = grace_elem is not None
        grace_slash = None if grace_elem is None else grace_elem.attrib.get('slash', None)

        # marked in xml to trigger debug output
        debug = note_elem.attrib.get('debug', None) is not None

        if is_rest:
            return Rest(duration_quarters=duration_quarters, voice_number=voice_number, is_grace=is_grace, debug=debug)
        else:
            pitch = self.process_pitch(note_elem)
            return Note(
                start_time=None,  # will set this later
                pitch=pitch,
                duration_quarters=duration_quarters,
                staff=staff_number,
                voice=voice_number,
                xml=note_elem,
                stolen_time=stolen_time,
                is_grace=is_grace,
                grace_slash=grace_slash,
                tie_types=tie_types,
                is_chord=is_chord,
                note_type=note_type,
                line_number=note_elem.attrib.get('xml_lineno', None),
                debug=debug,
            )


def write_mxl(musicxml_root, mxl_file):
    """Write an mxl file from an xml root element. 

    Zips a score.xml and a META-INF/container.xml file into a .mxl file.
    """
    # create a temp directory
    path = os.path.splitext(mxl_file)[0]
    tmp_path = os.path.join(path, '_tmp')
    meta_inf_path = os.path.join(tmp_path, 'META-INF')
    try:
        os.makedirs(meta_inf_path)

        # write score.xml
        score_xml_path = os.path.join(tmp_path, 'score.xml')
        with open(score_xml_path, 'wb') as f:
            f.write(ET.tostring(musicxml_root))

        # write container.xml
        container_xml = """
            <?xml version="1.0" encoding="UTF-8"?>
            <container>
            <rootfiles>
                <rootfile full-path="score.xml">
                </rootfile>
            </rootfiles>
            </container>
        """
        container_xml_path = os.path.join(meta_inf_path, 'container.xml')
        with open(container_xml_path, 'w') as f:
            f.write(container_xml)

        # zip the files
        zipfile = shutil.make_archive(tmp_path, 'zip', tmp_path)
        os.rename(zipfile, mxl_file)

    finally:
        shutil.rmtree(tmp_path)


class XmlLineReader:
    """Iterates over an XML file line-by-line, keeping track of the current line.
    
    https://stackoverflow.com/a/78924329/643629
    """
    def __init__(self, xml_str):
        self._iter = iter(xml_str.splitlines())
        self.line = -1

    def read(self, *_):
        try:
            self.line += 1
            return next(self._iter)
        except:
            return None
        
def read_xml_with_line_numbers(xml_str, add_line_numbers=False):
    source = XmlLineReader(xml_str)
    iter = ET.iterparse(source, ("start",))
    for _, elem in iter:
        if add_line_numbers:
            elem.set("xml_lineno", str(source.line + 1))
    return iter.root


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


class Measure:
    def __init__(self, number:int, events: List[Event]):
        self.number = number
        self.events = events

    def __iter__(self):
        return iter(self.events)
    
    def __len__(self):
        return len(self.events)

    def set_part(self, part):
        self.part = part
        for item in self.events:
            item.part = part


class MusicXMLPart(Part):
    def __init__(self, info, measures: List[Measure]):
        name = info.get('name', f'Part {info["id"]}')
        Part.__init__(self, name=name)
        self.info = info
        self.measures = measures

        # annotate all events with part info
        for measure in self.measures:
            for event in measure:
                event.part = self

    def __repr__(self):
        return f"<Part {self.info['id']}: {self.name}>"

    def __iter__(self):
        return iter(self.measures)

    def __len__(self):
        return len(self.measures)

    def handle_stolen_time(self):
        """Adjust note timing for grace notes with stolen time"""

        all_notes = []
        for measure in self.measures:
            all_notes.extend([ev for ev in measure.events if isinstance(ev, Note)])
        
        next_note = None
        while all_notes:
            prev_note = next_note
            next_note = None
            grace_notes = []
            while all_notes:
                note = all_notes.pop(0)
                if not isinstance(note, Note):
                    continue
                is_grace_note = getattr(note, 'stolen_time', 0) != 0
                if is_grace_note:
                    grace_notes.append(note)
                    continue
                else:
                    if grace_notes:
                        next_note = note
                        break
                    else:
                        prev_note = note

            if len(grace_notes) == 0:
                continue

            # we now have a previous note + grace notes + next note
            # first steal time from other notes and give to grace notes
            gn_start_quarters = grace_notes[0].start_quarters
            for i,gn in enumerate(grace_notes):
                if gn.stolen_time == 'default':
                    # we can decide how to render the grace note; no timing was specified
                    stolen_note = next_note
                    stolen_duration_quarters = 0.25
                    if gn.grace_slash:
                        stolen_duration_quarters *= 0.5 * 0.85
                else:
                    stolen_note = next_note if gn.stolen_time > 0 else prev_note
                    assert stolen_note is not None, "Grace note has no note to steal time from"
                    if not hasattr(stolen_note, '_original_duration_quarters'):
                        # if there are multiple grace notes, keep the stolen time proportional to the original duration
                        stolen_note._original_duration_quarters = stolen_note.duration_quarters
                    stolen_duration_quarters = stolen_note._original_duration_quarters * abs(gn.stolen_time) / 100
                gn.duration_quarters = stolen_duration_quarters
                if stolen_note is prev_note:
                    prev_note.duration_quarters -= stolen_duration_quarters
                    gn_start_quarters -= stolen_duration_quarters
                elif stolen_note is next_note:
                    next_note.duration_quarters -= stolen_duration_quarters
                    next_note.start_quarters += stolen_duration_quarters

                assert gn.duration_quarters > 0, "Grace note has no duration"

            # next, determine the start time of the grace notes
            for gn in grace_notes:
                gn.start_quarters = gn_start_quarters
                gn_start_quarters += gn.duration_quarters
                if gn.start_quarters < 0:
                    # if grace note start time is negative, it must take time from the previous measure
                    assert last_note.measure != gn.measure
                    # move the note to the previous measure and adjust the start time
                    gn.measure = last_note.measure
                    gn.start_quarters += last_note.start_quarters + last_note.duration_quarters


class DivisionsChange(Event):
    def __init__(self, divisions, start_time=None, **kwds):
        self.divisions = divisions
        super().__init__(start_time=start_time, **kwds)
