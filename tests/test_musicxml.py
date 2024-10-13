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
    duration_note1 = (2 / parser.divisions) * (60 / parser.tempo)  # divisions=1, duration=2
    assert note1.duration == duration_note1

    # Measure Duration
    beats, beat_type = parser.time_signature
    beat_duration = (60.0 / parser.tempo) * (4 / beat_type)
    measure_duration = beats * beat_duration  # 2.0 seconds

    # Note 2 (Measure 2)
    expected_start_time_note2 = note1.start_time + measure_duration  # Should be 2.0 seconds
    duration_note2 = (1 / parser.divisions) * (60 / parser.tempo)  # duration=1
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
            <duration>4</duration>
            <type>whole</type>
          </note>
          <!-- Missing notes/rests to fill the measure -->
        </measure>
        <measure number="2">
          <note>
            <pitch>
              <step>D</step>
              <octave>4</octave>
            </pitch>
            <duration>4</duration>
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
    beat_duration = (60.0 / tempo) * (4 / beat_type)
    expected_measure_duration = beats * beat_duration  # 2.0 seconds

    # Note 1 (Measure 1)
    assert note1.pitch.midi_note == 60  # C4
    assert note1.start_time == 0.0
    duration_note1 = (4 / parser.divisions) * (60 / tempo)  # divisions=4, duration=4
    assert note1.duration == duration_note1

    # The measure duration should be 2.0 seconds
    # Even though the note duration is shorter, the measure should be 2.0 seconds
    assert parser.cumulative_time == expected_measure_duration * 2  # Two measures

    # Note 2 (Measure 2)
    expected_start_time_note2 = expected_measure_duration  # Starts at 2.0 seconds
    assert note2.start_time == expected_start_time_note2
    duration_note2 = duration_note1
    assert note2.duration == duration_note2


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
            <duration>2</duration>
            <type>half</type>
          </note>
        </measure>
        <measure number="2">
          <note>
            <pitch>
              <step>C</step>
              <octave>4</octave>
            </pitch>
            <duration>4</duration>
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
    beat_duration = (60.0 / tempo) * (4 / beat_type)
    expected_measure_duration = beats * beat_duration  # 2.0 seconds

    # Note 1 (Pickup Measure)
    assert note1.pitch.midi_note == 67  # G4
    assert note1.start_time == 0.0
    duration_note1 = (2 / parser.divisions) * (60 / tempo)  # divisions=4, duration=2
    assert note1.duration == duration_note1

    # Since the pickup measure is implicit, cumulative_time should be equal to the duration of note1
    assert parser.cumulative_time == duration_note1 + expected_measure_duration  # Total time after both measures

    # Note 2 (Measure 2)
    expected_start_time_note2 = duration_note1  # Starts immediately after pickup note
    assert note2.start_time == expected_start_time_note2
    duration_note2 = (4 / parser.divisions) * (60 / tempo)
    assert note2.duration == duration_note2


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
    parser.divisions = 4  # Example divisions
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
    parser.divisions = 1
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
    note_obj, duration_seconds = parser.parse_note_element(note_elem)
    assert note_obj is not None
    assert note_obj.pitch.midi_note == 70  # B♭4
    assert note_obj.duration == (1 / parser.divisions) * (60.0 / parser.tempo)
    assert note_obj.voice == 1
    assert duration_seconds == note_obj.duration

