import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytest
import tempfile
import os
import zipfile
import xml.etree.ElementTree as ET
from pianofalls.musicxml import load_musicxml, MusicXMLParser


def test_load_musicxml():
    musicxml_content = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE score-partwise PUBLIC
    "-//Recordare//DTD MusicXML 3.1 Partwise//EN"
    "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="3.1">
    <part-list>
        <score-part id="P1">
            <part-name>Music</part-name>
        </score-part>
    </part-list>
    <part id="P1">
        <measure number="1">
            <attributes>
                <divisions>4</divisions>
            </attributes>
            <note>
                <pitch>
                    <step>C</step>
                    <octave>4</octave>
                </pitch>
                <duration>4</duration>
                <voice>1</voice>
                <type>whole</type>
            </note>
        </measure>
    </part>
</score-partwise>
'''

    # Create a temporary mxl file (which is a zip file)
    with tempfile.NamedTemporaryFile('wb', delete=False, suffix='.mxl') as temp_file:
        temp_filename = temp_file.name
        with zipfile.ZipFile(temp_file, 'w') as zf:
            # The mxl file should contain the musicxml content in a file called 'score.xml'
            zf.writestr('META-INF/container.xml', '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="container">
   <rootfiles>
      <rootfile full-path="score.xml" media-type="application/vnd.recordare.musicxml+xml"/>
   </rootfiles>
</container>
''')
            zf.writestr('score.xml', musicxml_content)

    try:
        song = load_musicxml(temp_filename)
        notes = song.notes  # Assuming Song has an attribute 'notes'
        assert len(notes) == 1
        note = notes[0]
        assert note.pitch.midi_note == 60  # C4
        assert note.start_time == 0.0
        expected_duration = (4 / 4) * (60 / 120.0)  # divisions=4, tempo=120 BPM
        assert note.duration == expected_duration  # Should be 1.0
    finally:
        os.remove(temp_filename)


def test_parser_overlapping_notes_due_to_new_voice():
    xml_content = '''
    <score-partwise>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions>
            <time>
              <beats>4</beats>
              <beat-type>4</beat-type>
            </time>
          </attributes>
          <note>
            <pitch>
              <step>D</step>
              <octave>3</octave>
            </pitch>
            <duration>2</duration>
            <voice>1</voice>
            <type>half</type>
            <staff>1</staff>
          </note>
        </measure>
        <measure number="2">
          <note>
            <pitch>
              <step>C</step>
              <alter>1</alter>
              <octave>2</octave>
            </pitch>
            <duration>1</duration>
            <voice>6</voice>
            <type>quarter</type>
            <staff>2</staff>
          </note>
        </measure>
      </part>
    </score-partwise>
    '''
    # Parse the XML content
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)

    # Simulate parsing as in parser.parse()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.part_info = {'P1': {'name': 'Piano'}}
    part_elem = root.find('part')
    parser.parse_part(part_elem, part_index=0)

    notes = parser.notes
    assert len(notes) == 2
    note1, note2 = notes

    # Note 1 (Measure 1)
    assert note1.pitch.midi_note == 50  # D3
    assert note1.start_time == 0.0
    duration_note1 = (2 / parser.divisions_per_quarter) * (60 / parser.tempo)  # divisions=1, duration=2
    assert note1.duration == duration_note1

    # Measure Duration
    beats, beat_type = parser.time_signature
    beat_duration = (60.0 / parser.tempo) * (4 / beat_type)
    measure_duration = beats * beat_duration  # 2.0 seconds

    # Note 2 (Measure 2)
    expected_start_time_note2 = note1.start_time + measure_duration  # Should be 2.0 seconds
    duration_note2 = (1 / parser.divisions_per_quarter) * (60 / parser.tempo)  # duration=1
    assert note2.start_time == expected_start_time_note2
    assert note2.duration == duration_note2
    assert note2.pitch.midi_note == 37  # C#2


def test_measure_duration_from_time_signature():
    xml_content = '''
    <score-partwise>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>4</divisions>
            <time>
              <beats>4</beats>
              <beat-type>4</beat-type>
            </time>
          </attributes>
          <note>
            <pitch>
              <step>C</step>
              <octave>4</octave>
            </pitch>
            <duration>16</duration>  <!-- Correct duration for a whole note -->
            <type>whole</type>
          </note>
        </measure>
        <measure number="2">
          <note>
            <pitch>
              <step>D</step>
              <octave>4</octave>
            </pitch>
            <duration>16</duration>  <!-- Correct duration for a whole note -->
            <type>whole</type>
          </note>
        </measure>
      </part>
    </score-partwise>
    '''
    # Parse the XML content
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)

    # Simulate parsing as in parser.parse()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.part_info = {'P1': {'name': 'Piano'}}
    part_elem = root.find('part')
    parser.parse_part(part_elem, part_index=0)

    notes = parser.notes
    assert len(notes) == 2
    note1, note2 = notes

    # Tempo is default 120 BPM
    tempo = 120.0
    # Time signature is 4/4
    beats = 4
    beat_type = 4
    beat_duration = (60.0 / tempo) * (4 / beat_type)  # 0.5 seconds per beat
    expected_measure_duration = beats * beat_duration  # 2.0 seconds

    # Note 1 (Measure 1)
    assert note1.pitch.midi_note == 60  # C4
    assert note1.start_time == 0.0
    duration_note1 = (16 / parser.divisions_per_quarter) * (60.0 / tempo)  # divisions=4, duration=16
    assert note1.duration == duration_note1  # Should be 2.0 seconds

    # Note 2 (Measure 2)
    expected_start_time_note2 = expected_measure_duration  # Should be 2.0 seconds
    assert note2.start_time == expected_start_time_note2
    duration_note2 = duration_note1
    assert note2.duration == duration_note2

    # Cumulative time after both measures
    expected_cumulative_time = expected_measure_duration * 2  # 4.0 seconds
    assert parser.cumulative_time == expected_cumulative_time


def test_pickup_measure():
    xml_content = '''
    <score-partwise>
      <part id="P1">
        <measure number="1" implicit="yes">
          <attributes>
            <divisions>4</divisions>
            <time>
              <beats>4</beats>
              <beat-type>4</beat-type>
            </time>
          </attributes>
          <note>
            <pitch>
              <step>G</step>
              <octave>4</octave>
            </pitch>
            <duration>8</duration>  <!-- Correct duration for a half note -->
            <type>half</type>
          </note>
        </measure>
        <measure number="2">
          <note>
            <pitch>
              <step>C</step>
              <octave>4</octave>
            </pitch>
            <duration>16</duration>  <!-- Correct duration for a whole note -->
            <type>whole</type>
          </note>
        </measure>
      </part>
    </score-partwise>
    '''
    # Parse the XML content
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)

    # Simulate parsing as in parser.parse()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.part_info = {'P1': {'name': 'Piano'}}
    part_elem = root.find('part')
    parser.parse_part(part_elem, part_index=0)

    notes = parser.notes
    assert len(notes) == 2
    note1, note2 = notes

    # Tempo is default 120 BPM
    tempo = 120.0
    # Time signature is 4/4
    beats = 4
    beat_type = 4
    beat_duration = (60.0 / tempo) * (4 / beat_type)  # 0.5 seconds per beat
    expected_measure_duration = beats * beat_duration  # 2.0 seconds

    # Note 1 (Pickup Measure)
    assert note1.pitch.midi_note == 67  # G4
    assert note1.start_time == 0.0
    duration_note1 = (8 / parser.divisions_per_quarter) * (60.0 / tempo)  # divisions=4, duration=8
    assert note1.duration == duration_note1  # Should be 1.0 seconds

    # Note 2 (Measure 2)
    expected_start_time_note2 = duration_note1  # Should be 1.0 seconds
    assert note2.start_time == expected_start_time_note2
    duration_note2 = (16 / parser.divisions_per_quarter) * (60.0 / tempo)  # Should be 2.0 seconds
    assert note2.duration == duration_note2

    # Cumulative time after both measures
    expected_cumulative_time = duration_note1 + expected_measure_duration  # 1.0 + 2.0 = 3.0 seconds
    assert parser.cumulative_time == expected_cumulative_time


def test_note_pitch_with_flat_key_signature():
    xml_content = '''
    <score-partwise>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions>
            <key>
              <fifths>-2</fifths> <!-- Key of B♭ major (2 flats) -->
            </key>
            <time>
              <beats>4</beats>
              <beat-type>4</beat-type>
            </time>
          </attributes>
          <note>
            <pitch>
              <step>B</step>
              <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <type>whole</type>
            <staff>1</staff>
          </note>
          <note>
            <pitch>
              <step>E</step>
              <octave>5</octave>
            </pitch>
            <duration>4</duration>
            <type>whole</type>
            <staff>1</staff>
          </note>
          <note>
            <pitch>
              <step>A</step>
              <alter>1</alter>
              <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <type>whole</type>
            <staff>1</staff>
          </note>
        </measure>
      </part>
    </score-partwise>
    '''
    # Parse the XML content
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)

    # Simulate parsing as in parser.parse()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.part_info = {'P1': {'name': 'Piano'}}
    part_elem = root.find('part')
    parser.parse_part(part_elem, part_index=0)

    notes = parser.notes
    assert len(notes) == 3
    note_b_flat, note_e_flat, note_a_sharp = notes

    # Note B in key of B♭ major (2 flats), should be B♭ (MIDI note 70)
    assert note_b_flat.pitch.midi_note == 70  # B♭4

    # Note E in key of B♭ major (2 flats), should be E♭ (MIDI note 75)
    assert note_e_flat.pitch.midi_note == 75  # E♭5

    # Note A♯ with explicit alter, should be A♯ (MIDI note 70)
    # Alter from <alter> element takes precedence
    assert note_a_sharp.pitch.midi_note == 70  # A♯4


def test_get_voice_and_staff():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    note_xml = '''
    <note>
        <voice>2</voice>
        <staff>3</staff>
    </note>
    '''
    note_elem = ET.fromstring(note_xml)
    voice_number, staff_number = parser.get_voice_and_staff(note_elem)
    assert voice_number == 2
    assert staff_number == 3


def test_get_duration():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.divisions_per_quarter = 4  # Example divisions
    parser.tempo = 120.0  # Example tempo
    note_xml = '''
    <note>
        <duration>4</duration>
    </note>
    '''
    note_elem = ET.fromstring(note_xml)
    duration_divisions, duration = parser.get_duration(note_elem)
    assert duration_divisions == 4
    assert duration == (4 / 4) * (60.0 / 120.0)  # Expected duration in seconds


def test_process_pitch():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.key_signature = -2  # Key of B♭ major (2 flats)
    note_xml = '''
    <note>
        <pitch>
            <step>E</step>
            <octave>5</octave>
        </pitch>
    </note>
    '''
    note_elem = ET.fromstring(note_xml)
    midi_note = parser.process_pitch(note_elem)
    assert midi_note == 75  # E♭5


def test_parse_note_element():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.divisions_per_quarter = 1
    parser.tempo = 120.0
    parser.key_signature = -2  # Key of B♭ major
    note_xml = '''
    <note>
        <duration>1</duration>
        <voice>1</voice>
        <pitch>
            <step>B</step>
            <octave>4</octave>
        </pitch>
    </note>
    '''
    note_elem = ET.fromstring(note_xml)
    note_obj, duration_seconds, voice_number = parser.parse_note_element(note_elem)
    assert note_obj is not None
    assert note_obj.pitch.midi_note == 70  # B♭4
    assert note_obj.duration == (1 / parser.divisions_per_quarter) * (60.0 / parser.tempo)
    assert note_obj.voice == 1
    assert duration_seconds == note_obj.duration


def test_rests_are_handled_correctly():
    xml_content = '''
    <score-partwise>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions>
            <time>
              <beats>4</beats>
              <beat-type>4</beat-type>
            </time>
          </attributes>
          <note>
            <rest/>
            <duration>2</duration>
            <voice>1</voice>
            <type>half</type>
          </note>
          <note>
            <pitch>
              <step>C</step>
              <octave>4</octave>
            </pitch>
            <duration>2</duration>
            <voice>1</voice>
            <type>half</type>
          </note>
        </measure>
      </part>
    </score-partwise>
    '''
    # Parse the XML content
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)

    # Simulate parsing as in parser.parse()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.part_info = {'P1': {'name': 'Piano'}}
    part_elem = root.find('part')
    parser.parse_part(part_elem, part_index=0)

    notes = parser.notes
    assert len(notes) == 1  # Only one note object (the rest does not create a Note)
    note = notes[0]

    # Verify that the note's start_time accounts for the rest duration
    # Rest duration: (2 / divisions) * (60 / tempo) = (2 / 1) * 0.5 = 1.0 seconds
    expected_start_time = 1.0
    assert note.start_time == expected_start_time
    # Note duration: (2 / divisions) * (60 / tempo) = (2 / 1) * 0.5 = 1.0 seconds
    expected_duration = 1.0
    assert note.duration == expected_duration
    assert note.pitch.midi_note == 60  # C4


def test_chord_notes_start_simultaneously():
    xml_content = '''
    <score-partwise>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>1</divisions>
          </attributes>
          <note>
            <pitch>
              <step>C</step>
              <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <voice>1</voice>
            <type>whole</type>
          </note>
          <note>
            <chord/>
            <pitch>
              <step>E</step>
              <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <voice>1</voice>
            <type>whole</type>
          </note>
          <note>
            <chord/>
            <pitch>
              <step>G</step>
              <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <voice>1</voice>
            <type>whole</type>
          </note>
        </measure>
      </part>
    </score-partwise>
    '''
    # Parse the XML content
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)

    # Simulate parsing as in parser.parse()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.part_info = {'P1': {'name': 'Piano'}}
    part_elem = root.find('part')
    parser.parse_part(part_elem, part_index=0)

    notes = parser.notes
    assert len(notes) == 3
    note_c, note_e, note_g = notes

    # All chord notes should have the same start_time
    assert note_c.start_time == note_e.start_time == note_g.start_time == 0.0

    # All chord notes should have the same duration
    assert note_c.duration == note_e.duration == note_g.duration == (4 / parser.divisions_per_quarter) * (60 / parser.tempo)

    # Verify pitches
    assert note_c.pitch.midi_note == 60  # C4
    assert note_e.pitch.midi_note == 64  # E4
    assert note_g.pitch.midi_note == 67  # G4


def test_collect_chord_notes():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    measure_elements = [
        ET.fromstring('<note><pitch><step>C</step><octave>4</octave></pitch></note>'),
        ET.fromstring('<note><chord/><pitch><step>E</step><octave>4</octave></pitch></note>'),
        ET.fromstring('<note><pitch><step>G</step><octave>4</octave></pitch></note>')
    ]
    chord_notes, next_index = parser.collect_chord_notes(measure_elements, 0)
    assert len(chord_notes) == 2
    assert parser.get_local_tag(chord_notes[0].tag) == 'note'
    assert parser.get_local_tag(chord_notes[1].tag) == 'note'
    assert next_index == 2  # Next index to process


def test_process_notes():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.divisions_per_quarter = 4
    parser.tempo = 120.0
    parser.cumulative_time = 0.0
    note_elems = [
        ET.fromstring('''
        <note>
            <duration>16</duration>
            <voice>1</voice>
            <pitch>
                <step>C</step>
                <octave>4</octave>
            </pitch>
        </note>
        '''),
        ET.fromstring('''
        <note>
            <chord/>
            <duration>16</duration>
            <voice>1</voice>
            <pitch>
                <step>E</step>
                <octave>4</octave>
            </pitch>
        </note>
        ''')
    ]
    notes = parser.process_notes(note_elems)
    assert len(notes) == 2
    assert notes[0].pitch.midi_note == 60  # C4
    assert notes[1].pitch.midi_note == 64  # E4
    assert notes[0].start_time == notes[1].start_time == 0.0
    assert notes[0].duration == notes[1].duration == (16 / parser.divisions_per_quarter) * (60.0 / parser.tempo)


def test_handle_backup_forward():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.divisions_per_quarter = 1
    parser.tempo = 60.0
    parser.voice_current_times = {1: 2.0, 2: 2.0}
    backup_elem = ET.fromstring('<backup><duration>1</duration></backup>')
    parser.handle_backup_forward(backup_elem, 'backup')
    assert parser.voice_current_times[1] == 1.0
    assert parser.voice_current_times[2] == 1.0

    forward_elem = ET.fromstring('<forward><duration>2</duration></forward>')
    parser.handle_backup_forward(forward_elem, 'forward')
    assert parser.voice_current_times[1] == 3.0
    assert parser.voice_current_times[2] == 3.0


def test_calculate_measure_duration():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.divisions_per_quarter = 4
    parser.tempo = 120.0
    parser.time_signature = (4, 4)  # 4/4 time
    parser.cumulative_time = 0.0
    parser.voice_current_times = {1: 2.0, 2: 2.0}

    # Explicit measure
    measure_duration = parser.calculate_measure_duration(0.0, implicit=False)
    assert measure_duration == 2.0  # Expected measure duration in seconds
    assert parser.voice_current_times[1] == 2.0
    assert parser.voice_current_times[2] == 2.0

    # Implicit measure
    parser.voice_current_times = {1: 1.0, 2: 1.5}
    measure_duration = parser.calculate_measure_duration(0.0, implicit=True)
    assert measure_duration == 1.5  # Maximum voice time minus start time


def test_calculate_measure_duration_explicit_measure():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.time_signature = (4, 4)
    parser.tempo = 120.0
    parser.cumulative_time = 0.0
    parser.voice_current_times = {1: 2.0}

    # Explicit measure (not implicit)
    measure_start_time = 0.0
    implicit = False
    measure_duration = parser.calculate_measure_duration(measure_start_time, implicit)

    # Expected measure duration
    beat_duration = (60.0 / parser.tempo) * (4 / parser.time_signature[1])
    expected_measure_duration = parser.time_signature[0] * beat_duration  # beats * beat_duration
    assert measure_duration == expected_measure_duration
    assert parser.cumulative_time == 0.0  # cumulative_time should not change in this method


def test_parse_measure_cumulative_time_update():
    xml_content = '''
    <measure>
        <attributes>
            <divisions>4</divisions>
            <time>
                <beats>4</beats>
                <beat-type>4</beat-type>
            </time>
        </attributes>
        <note>
            <pitch>
                <step>C</step>
                <octave>4</octave>
            </pitch>
            <duration>16</duration>
            <type>whole</type>
        </note>
    </measure>
    '''
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.cumulative_time = 0.0

    measure_notes, measure_duration = parser.parse_measure(root)
    expected_measure_duration = 2.0  # For a whole note at 120 BPM
    assert measure_duration == expected_measure_duration
    assert parser.cumulative_time == expected_measure_duration
    assert len(measure_notes) == 1
    note = measure_notes[0]
    assert note.start_time == 0.0
    assert note.duration == expected_measure_duration


def test_parse_measure_with_rest_and_correct_timing():
    xml_content = '''
    <measure>
        <attributes>
            <divisions>4</divisions>
            <time>
                <beats>4</beats>
                <beat-type>4</beat-type>
            </time>
        </attributes>
        <note>
            <rest/>
            <duration>8</duration>
            <type>half</type>
        </note>
        <note>
            <pitch>
                <step>E</step>
                <octave>4</octave>
            </pitch>
            <duration>8</duration>
            <type>half</type>
        </note>
    </measure>
    '''
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.cumulative_time = 0.0

    measure_notes, measure_duration = parser.parse_measure(root)
    expected_measure_duration = 2.0  # For 4/4 measure at 120 BPM
    assert measure_duration == expected_measure_duration
    assert parser.cumulative_time == expected_measure_duration
    assert len(measure_notes) == 1
    note = measure_notes[0]
    assert note.start_time == parser.cumulative_time - measure_duration + 1.0  # After the rest
    assert note.duration == 1.0


def test_parse_part_cumulative_time_reset():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.part_info = {'P1': {'name': 'Piano'}}
    xml_content = '''
    <part id="P1">
        <measure number="1">
            <attributes>
                <divisions>4</divisions>
            </attributes>
            <note>
                <pitch>
                    <step>C</step>
                    <octave>4</octave>
                </pitch>
                <duration>16</duration>
                <type>whole</type>
            </note>
        </measure>
        <measure number="2">
            <note>
                <pitch>
                    <step>D</step>
                    <octave>4</octave>
                </pitch>
                <duration>16</duration>
                <type>whole</type>
            </note>
        </measure>
    </part>
    '''
    part_elem = ET.fromstring(xml_content)
    parser.parse_part(part_elem, part_index=0)
    assert parser.cumulative_time == 4.0  # Two measures of 2.0 seconds each


def test_cumulative_time_after_each_measure():
    xml_content = '''
    <score-partwise>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>4</divisions>
            <time>
              <beats>4</beats>
              <beat-type>4</beat-type>
            </time>
          </attributes>
          <note>
            <pitch>
              <step>C</step>
              <octave>4</octave>
            </pitch>
            <duration>16</duration>  <!-- Whole note -->
            <type>whole</type>
          </note>
        </measure>
        <measure number="2">
          <note>
            <pitch>
              <step>D</step>
              <octave>4</octave>
            </pitch>
            <duration>16</duration>  <!-- Whole note -->
            <type>whole</type>
          </note>
        </measure>
      </part>
    </score-partwise>
    '''
    # Parse the XML content
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.part_info = {'P1': {'name': 'Piano'}}
    part_elem = root.find('part')

    # Initialize cumulative_time to 0
    parser.cumulative_time = 0.0

    # Parse measures one by one and check cumulative_time
    measures = part_elem.findall('measure')
    expected_cumulative_times = []
    for measure_elem in measures:
        measure_notes, measure_duration = parser.parse_measure(measure_elem)
        parser.cumulative_time += measure_duration
        expected_cumulative_times.append(parser.cumulative_time)

    # Check if cumulative_time is as expected after each measure
    # For 4/4 time at 120 BPM, each measure should be 2.0 seconds
    assert expected_cumulative_times == [2.0, 4.0], f"Cumulative times: {expected_cumulative_times}"



def test_calculate_measure_duration_scenarios():
    parser = MusicXMLParser()
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.time_signature = (4, 4)
    parser.tempo = 120.0

    # Test with implicit measure
    parser.voice_current_times = {1: 1.5}
    measure_duration = parser.calculate_measure_duration(0.0, implicit=True)
    assert measure_duration == 1.5, f"Expected measure_duration 1.5, got {measure_duration}"

    # Test with explicit measure, voice time less than expected
    parser.voice_current_times = {1: 1.5}
    measure_duration = parser.calculate_measure_duration(0.0, implicit=False)
    expected_duration = 2.0  # For 4/4 time at 120 BPM
    assert measure_duration == expected_duration, f"Expected measure_duration {expected_duration}, got {measure_duration}"
    # Check if voice_current_times have been adjusted
    assert parser.voice_current_times[1] == expected_duration, f"Expected voice_current_time {expected_duration}, got {parser.voice_current_times[1]}"


def test_multiple_parts_and_voices():
    xml_content = '''
    <score-partwise>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>4</divisions>
            <time>
              <beats>4</beats>
              <beat-type>4</beat-type>
            </time>
          </attributes>
          <note>
            <pitch>
              <step>C</step>
              <octave>4</octave>
            </pitch>
            <duration>8</duration>  <!-- Half note -->
            <type>half</type>
            <voice>1</voice>
          </note>
          <note>
            <pitch>
              <step>E</step>
              <octave>4</octave>
            </pitch>
            <duration>8</duration>  <!-- Half note -->
            <type>half</type>
            <voice>2</voice>
          </note>
        </measure>
      </part>
    </score-partwise>
    '''
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.part_info = {'P1': {'name': 'Piano'}}
    part_elem = root.find('part')
    parser.parse_part(part_elem, part_index=0)
    
    # Check cumulative_time after parsing the measure
    expected_cumulative_time = 2.0  # For 4/4 measure at 120 BPM
    assert parser.cumulative_time == expected_cumulative_time, f"Expected cumulative_time {expected_cumulative_time}, got {parser.cumulative_time}"


def test_voice_current_times_after_measures():
    xml_content = '''
    <score-partwise>
      <part id="P1">
        <measure number="1">
          <attributes>
            <divisions>4</divisions>
          </attributes>
          <note>
            <pitch>
              <step>G</step>
              <octave>4</octave>
            </pitch>
            <duration>4</duration>  <!-- Quarter note -->
            <type>quarter</type>
            <voice>1</voice>
          </note>
          <note>
            <pitch>
              <step>B</step>
              <octave>4</octave>
            </pitch>
            <duration>8</duration>  <!-- Half note -->
            <type>half</type>
            <voice>2</voice>
          </note>
        </measure>
      </part>
    </score-partwise>
    '''
    parser = MusicXMLParser()
    root = ET.fromstring(xml_content)
    parser.ns_tag = lambda tag: tag  # No namespace
    parser.part_info = {'P1': {'name': 'Piano'}}
    part_elem = root.find('part')
    parser.parse_part(part_elem, part_index=0)

    # Given divisions=4 and tempo=120 BPM
    # Quarter note duration: (4 / 4) * (60 / 120) = 0.5 sec
    # Half note duration: (8 / 4) * (60 / 120) = 1.0 sec
    expected_voice_times = {1: 0.5, 2: 1.0}
    assert parser.voice_current_times == expected_voice_times, f"Expected voice_current_times {expected_voice_times}, got {parser.voice_current_times}"
