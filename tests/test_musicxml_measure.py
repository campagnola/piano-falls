import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytest
import xml.etree.ElementTree as ET
from pianofalls.musicxml import parse_measure

def ns_tag(tag):
    return tag

def test_measure_single_note():
    xml_measure = '''
    <measure number="1">
        <note>
            <pitch>
                <step>C</step>
                <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <type>whole</type>
            <voice>1</voice>
        </note>
    </measure>
    '''
    measure_elem = ET.fromstring(xml_measure)
    divisions = 4  # Commonly, divisions are set to 4 for quarter notes
    tempo = 60.0   # 60 BPM
    part_index = 0
    key_signature = 0  # Default key signature (C major)
    voice_current_times = {}
    ties = {}

    notes = parse_measure(
        measure_elem,
        ns_tag,
        divisions,
        tempo,
        part_index,
        voice_current_times,
        key_signature,
        ties
    )

    assert len(notes) == 1
    note = notes[0]
    assert note['pitch'].midi_note == 60  # Middle C
    assert note['start_time'] == 0.0
    expected_duration = (4 / divisions) * (60 / tempo)
    assert note['duration'] == expected_duration  # Whole note duration
    assert note['voice'] == 1

def test_measure_multiple_notes():
    xml_measure = '''
    <measure number="1">
        <note>
            <pitch>
                <step>G</step>
                <octave>4</octave>
            </pitch>
            <duration>2</duration>
            <type>half</type>
            <voice>1</voice>
        </note>
        <note>
            <pitch>
                <step>E</step>
                <octave>4</octave>
            </pitch>
            <duration>2</duration>
            <type>half</type>
            <voice>1</voice>
        </note>
    </measure>
    '''
    measure_elem = ET.fromstring(xml_measure)
    divisions = 2  # Half notes are 2 divisions
    tempo = 60.0   # 60 BPM
    part_index = 0
    key_signature = 0
    voice_current_times = {}
    ties = {}

    notes = parse_measure(
        measure_elem,
        ns_tag,
        divisions,
        tempo,
        part_index,
        voice_current_times,
        key_signature,
        ties
    )

    assert len(notes) == 2
    note1, note2 = notes

    # First note assertions
    assert note1['pitch'].midi_note == 67  # G4
    assert note1['start_time'] == 0.0
    expected_duration = (2 / divisions) * (60 / tempo)
    assert note1['duration'] == expected_duration  # Half note duration

    # Second note assertions
    assert note2['pitch'].midi_note == 64  # E4
    assert note2['start_time'] == note1['start_time'] + note1['duration']
    assert note2['duration'] == expected_duration  # Half note duration

def test_measure_with_chord():
    xml_measure = '''
    <measure number="1">
        <note>
            <pitch>
                <step>C</step>
                <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <type>whole</type>
            <voice>1</voice>
        </note>
        <note>
            <chord/>
            <pitch>
                <step>E</step>
                <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <type>whole</type>
            <voice>1</voice>
        </note>
        <note>
            <chord/>
            <pitch>
                <step>G</step>
                <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <type>whole</type>
            <voice>1</voice>
        </note>
    </measure>
    '''
    measure_elem = ET.fromstring(xml_measure)
    divisions = 4  # Quarter note divisions
    tempo = 60.0   # 60 BPM
    part_index = 0
    key_signature = 0
    voice_current_times = {}
    ties = {}

    notes = parse_measure(
        measure_elem,
        ns_tag,
        divisions,
        tempo,
        part_index,
        voice_current_times,
        key_signature,
        ties
    )

    assert len(notes) == 3
    note1, note2, note3 = notes

    # All notes should have the same start_time
    assert note1['start_time'] == note2['start_time'] == note3['start_time'] == 0.0

    # Durations should be equal
    expected_duration = (4 / divisions) * (60 / tempo)
    assert note1['duration'] == note2['duration'] == note3['duration'] == expected_duration

    # Verify pitches
    assert note1['pitch'].midi_note == 60  # C4
    assert note2['pitch'].midi_note == 64  # E4
    assert note3['pitch'].midi_note == 67  # G4

def test_measure_with_rests():
    xml_measure = '''
    <measure number="1">
        <note>
            <rest/>
            <duration>2</duration>
            <type>half</type>
            <voice>1</voice>
        </note>
        <note>
            <pitch>
                <step>D</step>
                <octave>4</octave>
            </pitch>
            <duration>2</duration>
            <type>half</type>
            <voice>1</voice>
        </note>
    </measure>
    '''
    measure_elem = ET.fromstring(xml_measure)
    divisions = 2  # Half note divisions
    tempo = 60.0   # 60 BPM
    part_index = 0
    key_signature = 0
    voice_current_times = {}
    ties = {}

    notes = parse_measure(
        measure_elem,
        ns_tag,
        divisions,
        tempo,
        part_index,
        voice_current_times,
        key_signature,
        ties
    )

    assert len(notes) == 1
    note = notes[0]

    # The note should start after the rest duration
    rest_duration_seconds = (2 / divisions) * (60 / tempo)
    assert note['start_time'] == rest_duration_seconds

    # Verify pitch and duration
    expected_duration = (2 / divisions) * (60 / tempo)
    assert note['pitch'].midi_note == 62  # D4
    assert note['duration'] == expected_duration  # Should be equal to half note duration

def test_measure_multiple_voices():
    xml_measure = '''
    <measure number="1">
        <!-- Voice 1 -->
        <note>
            <pitch>
                <step>C</step>
                <octave>5</octave>
            </pitch>
            <duration>4</duration>
            <type>whole</type>
            <voice>1</voice>
        </note>
        <!-- Voice 2 -->
        <note>
            <pitch>
                <step>G</step>
                <octave>3</octave>
            </pitch>
            <duration>2</duration>
            <type>half</type>
            <voice>2</voice>
        </note>
        <note>
            <pitch>
                <step>F</step>
                <octave>3</octave>
            </pitch>
            <duration>2</duration>
            <type>half</type>
            <voice>2</voice>
        </note>
    </measure>
    '''
    measure_elem = ET.fromstring(xml_measure)
    divisions = 4  # Quarter note divisions
    tempo = 60.0   # 60 BPM
    part_index = 0
    key_signature = 0
    voice_current_times = {}
    ties = {}

    notes = parse_measure(
        measure_elem,
        ns_tag,
        divisions,
        tempo,
        part_index,
        voice_current_times,
        key_signature,
        ties
    )

    assert len(notes) == 3
    # Separate notes by voice
    voice1_notes = [n for n in notes if n['voice'] == 1]
    voice2_notes = [n for n in notes if n['voice'] == 2]

    # Voice 1 assertions
    assert len(voice1_notes) == 1
    note_v1 = voice1_notes[0]
    assert note_v1['pitch'].midi_note == 72  # C5
    assert note_v1['start_time'] == 0.0
    expected_duration_v1 = (4 / divisions) * (60 / tempo)
    assert note_v1['duration'] == expected_duration_v1

    # Voice 2 assertions
    assert len(voice2_notes) == 2
    note_v2_1, note_v2_2 = voice2_notes
    expected_duration_v2 = (2 / divisions) * (60 / tempo)
    assert note_v2_1['pitch'].midi_note == 55  # G3
    assert note_v2_1['start_time'] == 0.0
    assert note_v2_1['duration'] == expected_duration_v2
    assert note_v2_2['pitch'].midi_note == 53  # F3
    assert note_v2_2['start_time'] == note_v2_1['start_time'] + note_v2_1['duration']
    assert note_v2_2['duration'] == expected_duration_v2

def test_measure_tempo_change():
    xml_measure = '''
    <measure number="1">
        <direction placement="above">
            <sound tempo="60"/>
        </direction>
        <note>
            <pitch>
                <step>D</step>
                <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <type>whole</type>
            <voice>1</voice>
        </note>
        <direction placement="above">
            <sound tempo="120"/>
        </direction>
        <note>
            <pitch>
                <step>E</step>
                <octave>4</octave>
            </pitch>
            <duration>4</duration>
            <type>whole</type>
            <voice>1</voice>
        </note>
    </measure>
    '''
    measure_elem = ET.fromstring(xml_measure)
    divisions = 4  # Quarter note divisions
    initial_tempo = 60.0   # Initial tempo
    part_index = 0
    key_signature = 0
    voice_current_times = {}
    ties = {}

    notes = parse_measure(
        measure_elem,
        ns_tag,
        divisions,
        initial_tempo,
        part_index,
        voice_current_times,
        key_signature,
        ties
    )

    assert len(notes) == 2
    note1, note2 = notes

    # First note at initial tempo
    expected_duration_note1 = (4 / divisions) * (60 / 60.0)  # 4 divisions at 60 BPM
    assert note1['start_time'] == 0.0
    assert note1['duration'] == expected_duration_note1

    # Second note at new tempo
    expected_start_time_note2 = note1['start_time'] + note1['duration']
    expected_duration_note2 = (4 / divisions) * (60 / 120.0)  # 4 divisions at 120 BPM
    assert note2['start_time'] == expected_start_time_note2
    assert note2['duration'] == expected_duration_note2

def test_measure_time_signature_change():
    xml_measure = '''
    <measure number="1">
        <attributes>
            <divisions>2</divisions>
            <time>
                <beats>3</beats>
                <beat-type>4</beat-type>
            </time>
        </attributes>
        <note>
            <pitch>
                <step>F</step>
                <octave>4</octave>
            </pitch>
            <duration>2</duration>
            <type>quarter</type>
            <voice>1</voice>
        </note>
        <note>
            <pitch>
                <step>A</step>
                <octave>4</octave>
            </pitch>
            <duration>2</duration>
            <type>quarter</type>
            <voice>1</voice>
        </note>
        <note>
            <pitch>
                <step>C</step>
                <octave>5</octave>
            </pitch>
            <duration>2</duration>
            <type>quarter</type>
            <voice>1</voice>
        </note>
    </measure>
    '''
    measure_elem = ET.fromstring(xml_measure)
    divisions = 2  # Quarter note divisions as per <divisions>
    tempo = 90.0   # 90 BPM
    part_index = 0
    key_signature = 0
    voice_current_times = {}
    ties = {}

    notes = parse_measure(
        measure_elem,
        ns_tag,
        divisions,
        tempo,
        part_index,
        voice_current_times,
        key_signature,
        ties
    )

    assert len(notes) == 3
    total_duration = 0.0
    for i, note in enumerate(notes):
        expected_start_time = total_duration
        expected_duration = (2 / divisions) * (60 / tempo)
        assert note['start_time'] == pytest.approx(expected_start_time, 0.0001)
        assert note['duration'] == pytest.approx(expected_duration, 0.0001)
        total_duration += expected_duration

def test_measure_with_tuplet():
    xml_measure = '''
    <measure number="1">
        <note>
            <duration>1</duration>
            <type>eighth</type>
            <time-modification>
                <actual-notes>3</actual-notes>
                <normal-notes>2</normal-notes>
            </time-modification>
            <pitch>
                <step>E</step>
                <octave>4</octave>
            </pitch>
            <voice>1</voice>
        </note>
        <note>
            <duration>1</duration>
            <type>eighth</type>
            <time-modification>
                <actual-notes>3</actual-notes>
                <normal-notes>2</normal-notes>
            </time-modification>
            <pitch>
                <step>F</step>
                <octave>4</octave>
            </pitch>
            <voice>1</voice>
        </note>
        <note>
            <duration>1</duration>
            <type>eighth</type>
            <time-modification>
                <actual-notes>3</actual-notes>
                <normal-notes>2</normal-notes>
            </time-modification>
            <pitch>
                <step>G</step>
                <octave>4</octave>
            </pitch>
            <voice>1</voice>
        </note>
    </measure>
    '''
    measure_elem = ET.fromstring(xml_measure)
    divisions = 2  # Divisions per quarter note
    tempo = 120.0  # 120 BPM
    part_index = 0
    key_signature = 0
    voice_current_times = {}
    ties = {}

    notes = parse_measure(
        measure_elem,
        ns_tag,
        divisions,
        tempo,
        part_index,
        voice_current_times,
        key_signature,
        ties
    )

    assert len(notes) == 3
    total_duration = 0.0
    for note in notes:
        expected_start_time = total_duration
        duration_divisions = 1 * (2 / 3)  # Adjusted for triplet
        expected_duration = (duration_divisions / divisions) * (60 / tempo)
        assert note['start_time'] == pytest.approx(expected_start_time, 0.0001)
        assert note['duration'] == pytest.approx(expected_duration, 0.0001)
        total_duration += expected_duration
