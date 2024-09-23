import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytest
import xml.etree.ElementTree as ET
from pianofalls.musicxml import parse_note_element


def test_single_note_middle_c():
    xml_note = '''
    <note>
        <pitch>
            <step>C</step>
            <octave>4</octave>
        </pitch>
        <duration>1</duration>
        <voice>1</voice>
    </note>
    '''
    elem = ET.fromstring(xml_note)
    ns_tag = lambda tag: tag  # No namespace

    divisions = 1
    tempo = 60.0
    current_time = 0.0
    part_index = 0

    note, duration_divisions, voice_number, is_chord, is_rest, updated_current_time = parse_note_element(
        elem=elem,
        ns_tag=ns_tag,
        divisions=divisions,
        tempo=tempo,
        current_time=current_time,
        part_index=part_index
    )

    # Update current_time
    current_time = updated_current_time

    assert note is not None
    assert note['pitch'].midi_note == 60  # Middle C
    assert note['start_time'] == 0.0
    assert note['duration'] == 1.0
    assert note['voice'] == 1
    assert note['staff'] == 1
    # Ensure current_time advanced correctly
    assert current_time == 1.0

def test_note_with_sharp():
    xml_note = '''
    <note>
        <pitch>
            <step>C</step>
            <alter>1</alter>
            <octave>4</octave>
        </pitch>
        <duration>1</duration>
        <voice>1</voice>
    </note>
    '''
    elem = ET.fromstring(xml_note)
    ns_tag = lambda tag: tag

    divisions = 1
    tempo = 60.0
    current_time = 0.0
    part_index = 0

    note, _, _, _, _, updated_current_time = parse_note_element(
        elem, ns_tag, divisions, tempo, current_time, part_index
    )
    # Update current_time
    current_time = updated_current_time

    assert note is not None
    assert note['pitch'].midi_note == 61  # C#
    # Ensure current_time advanced correctly
    assert current_time == 1.0

def test_rest():
    xml_note = '''
    <note>
        <rest/>
        <duration>1</duration>
        <voice>1</voice>
    </note>
    '''
    elem = ET.fromstring(xml_note)
    ns_tag = lambda tag: tag

    divisions = 1
    tempo = 60.0
    current_time = 0.0
    part_index = 0

    note, duration_divisions, voice_number, is_chord, is_rest, updated_current_time = parse_note_element(
        elem, ns_tag, divisions, tempo, current_time, part_index
    )
    # Update current_time
    current_time = updated_current_time

    assert note is None
    assert is_rest is True
    assert duration_divisions == 1
    # Ensure current_time advanced correctly
    assert current_time == 1.0

def test_chord_notes():
    xml_notes = [
        '''
        <note>
            <pitch>
                <step>C</step>
                <octave>4</octave>
            </pitch>
            <duration>1</duration>
            <voice>1</voice>
        </note>
        ''',
        '''
        <note>
            <chord/>
            <pitch>
                <step>E</step>
                <octave>4</octave>
            </pitch>
            <duration>1</duration>
            <voice>1</voice>
        </note>
        '''
    ]

    ns_tag = lambda tag: tag
    divisions = 1
    tempo = 60.0
    current_time = 0.0
    part_index = 0
    chord_notes = []
    max_duration_divisions = 0

    for xml_note in xml_notes:
        elem = ET.fromstring(xml_note)
        note, duration_divisions, voice_number, is_chord, is_rest, _ = parse_note_element(
            elem, ns_tag, divisions, tempo, current_time, part_index
        )
        chord_notes.append(note)
        # Keep track of the maximum duration divisions
        if duration_divisions > max_duration_divisions:
            max_duration_divisions = duration_divisions

    # After processing all chord notes, advance current_time
    duration = (max_duration_divisions / divisions) * (60.0 / tempo)
    current_time += duration

    # Assertions
    for note in chord_notes:
        assert note['start_time'] == 0.0  # All chord notes start at the same time

    # Ensure current_time advanced correctly
    assert current_time == 1.0

def test_multiple_voices():
    xml_note1 = '''
    <note>
        <pitch>
            <step>C</step>
            <octave>4</octave>
        </pitch>
        <duration>1</duration>
        <voice>1</voice>
    </note>
    '''
    xml_note2 = '''
    <note>
        <pitch>
            <step>E</step>
            <octave>4</octave>
        </pitch>
        <duration>1</duration>
        <voice>2</voice>
    </note>
    '''

    elem1 = ET.fromstring(xml_note1)
    elem2 = ET.fromstring(xml_note2)
    ns_tag = lambda tag: tag

    divisions = 1
    tempo = 60.0
    part_index = 0

    # Initialize current_time for each voice
    current_times = {1: 0.0, 2: 0.0}

    # First note in voice 1
    note1, duration_divisions1, voice_number1, _, _, updated_current_time1 = parse_note_element(
        elem1, ns_tag, divisions, tempo, current_times[1], part_index
    )
    # Update current_time for voice 1
    current_times[voice_number1] = updated_current_time1

    # First note in voice 2
    note2, duration_divisions2, voice_number2, _, _, updated_current_time2 = parse_note_element(
        elem2, ns_tag, divisions, tempo, current_times[2], part_index
    )
    # Update current_time for voice 2
    current_times[voice_number2] = updated_current_time2

    assert note1['start_time'] == 0.0
    assert note2['start_time'] == 0.0
    assert note1['voice'] == 1
    assert note2['voice'] == 2
    # Ensure current_times advanced correctly
    assert current_times[1] == 1.0
    assert current_times[2] == 1.0

def test_timing_with_different_durations():
    xml_note1 = '''
    <note>
        <pitch>
            <step>C</step>
            <octave>4</octave>
        </pitch>
        <duration>1</duration>
        <voice>1</voice>
    </note>
    '''
    xml_note2 = '''
    <note>
        <pitch>
            <step>D</step>
            <octave>4</octave>
        </pitch>
        <duration>2</duration>
        <voice>1</voice>
    </note>
    '''

    ns_tag = lambda tag: tag
    divisions = 1
    tempo = 60.0
    part_index = 0

    current_time = 0.0

    # First note
    elem1 = ET.fromstring(xml_note1)
    note1, duration_divisions1, voice_number1, _, _, updated_current_time1 = parse_note_element(
        elem1, ns_tag, divisions, tempo, current_time, part_index
    )
    # Update current_time
    current_time = updated_current_time1

    # Second note
    elem2 = ET.fromstring(xml_note2)
    note2, duration_divisions2, voice_number2, _, _, updated_current_time2 = parse_note_element(
        elem2, ns_tag, divisions, tempo, current_time, part_index
    )
    # Update current_time
    current_time = updated_current_time2

    assert note1['start_time'] == 0.0
    assert note1['duration'] == 1.0
    assert note2['start_time'] == 1.0  # Starts after first note ends
    assert note2['duration'] == 2.0
    # Ensure current_time advanced correctly
    assert current_time == 3.0

def test_chord_with_different_durations():
    xml_note1 = '''
    <note>
        <pitch>
            <step>C</step>
            <octave>4</octave>
        </pitch>
        <duration>1</duration>
        <voice>1</voice>
    </note>
    '''
    xml_note2 = '''
    <note>
        <chord/>
        <pitch>
            <step>E</step>
            <octave>4</octave>
        </pitch>
        <duration>2</duration> <!-- Different duration -->
        <voice>1</voice>
    </note>
    '''

    elem1 = ET.fromstring(xml_note1)
    elem2 = ET.fromstring(xml_note2)
    ns_tag = lambda tag: tag

    divisions = 1
    tempo = 60.0
    current_time = 0.0
    part_index = 0

    # First note
    note1, duration_divisions1, voice_number1, is_chord1, _, updated_current_time1 = parse_note_element(
        elem1, ns_tag, divisions, tempo, current_time, part_index
    )
    # Since it's not a chord, current_time doesn't advance yet

    # Second note (chord)
    note2, duration_divisions2, voice_number2, is_chord2, _, updated_current_time2 = parse_note_element(
        elem2, ns_tag, divisions, tempo, current_time, part_index
    )
    # For chord notes, current_time doesn't advance yet

    # After processing all chord notes, advance current_time by the longest duration
    max_duration = max(
        (duration_divisions1 / divisions) * (60.0 / tempo),
        (duration_divisions2 / divisions) * (60.0 / tempo)
    )
    current_time += max_duration

    assert note1['start_time'] == 0.0
    assert note2['start_time'] == 0.0
    assert note1['duration'] == 1.0
    assert note2['duration'] == 2.0  # Different duration
    # Ensure current_time advanced correctly
    assert current_time == 2.0  # Advanced by the longest duration

def test_notes_with_tempo_change():
    xml_note1 = '''
    <note>
        <pitch>
            <step>C</step>
            <octave>4</octave>
        </pitch>
        <duration>1</duration>
        <voice>1</voice>
    </note>
    '''
    xml_note2 = '''
    <note>
        <pitch>
            <step>D</step>
            <octave>4</octave>
        </pitch>
        <duration>1</duration>
        <voice>1</voice>
    </note>
    '''

    ns_tag = lambda tag: tag
    divisions = 1
    part_index = 0

    current_time = 0.0

    # First note at tempo 60 BPM
    tempo1 = 60.0
    elem1 = ET.fromstring(xml_note1)
    note1, duration_divisions1, voice_number1, _, _, updated_current_time1 = parse_note_element(
        elem1, ns_tag, divisions, tempo1, current_time, part_index
    )
    # Update current_time
    current_time = updated_current_time1

    # Second note at tempo 120 BPM
    tempo2 = 120.0
    elem2 = ET.fromstring(xml_note2)
    note2, duration_divisions2, voice_number2, _, _, updated_current_time2 = parse_note_element(
        elem2, ns_tag, divisions, tempo2, current_time, part_index
    )
    # Update current_time
    current_time = updated_current_time2

    assert note1['start_time'] == 0.0
    assert note1['duration'] == 1.0  # At tempo 60 BPM
    assert note2['start_time'] == 1.0  # Next note starts after 1 second
    assert note2['duration'] == 0.5    # At tempo 120 BPM, duration is shorter
    # Ensure current_time advanced correctly
    assert current_time == 1.5

if __name__ == '__main__':
    pytest.main()
