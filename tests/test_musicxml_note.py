import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import xml.etree.ElementTree as ET
from pianofalls.musicxml import parse_note_element


def ns_tag(tag):
    return tag

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
    divisions = 1
    tempo = 60.0
    current_time = 0.0
    part_index = 0
    key_signature = 0

    note, duration_divisions, voice_number, is_chord, is_rest, updated_current_time = parse_note_element(
        elem=elem,
        ns_tag=ns_tag,
        divisions=divisions,
        tempo=tempo,
        current_time=current_time,
        part_index=part_index,
        key_signature=key_signature
    )

    current_time = updated_current_time

    assert note is not None
    assert note['pitch'].midi_note == 60
    assert note['start_time'] == 0.0
    assert note['duration'] == 1.0
    assert note['voice'] == 1
    assert note['staff'] == 1
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
    divisions = 1
    tempo = 60.0
    current_time = 0.0
    part_index = 0
    key_signature = 0

    note, _, _, _, _, updated_current_time = parse_note_element(
        elem, ns_tag, divisions, tempo, current_time, part_index, key_signature
    )
    current_time = updated_current_time

    assert note is not None
    assert note['pitch'].midi_note == 61
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
    divisions = 1
    tempo = 60.0
    current_time = 0.0
    part_index = 0
    key_signature = 0

    note, duration_divisions, voice_number, is_chord, is_rest, updated_current_time = parse_note_element(
        elem, ns_tag, divisions, tempo, current_time, part_index, key_signature
    )
    current_time = updated_current_time

    assert note is None
    assert is_rest is True
    assert duration_divisions == 1
    assert current_time == 1.0

def test_chord_notes():
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
        <duration>1</duration>
        <voice>1</voice>
    </note>
    '''

    elem1 = ET.fromstring(xml_note1)
    elem2 = ET.fromstring(xml_note2)
    divisions = 1
    tempo = 60.0
    current_time = 0.0
    part_index = 0
    key_signature = 0

    chord_notes = []
    max_duration_divisions = 0

    note1, duration_divisions1, voice_number1, is_chord1, is_rest1, _ = parse_note_element(
        elem1, ns_tag, divisions, tempo, current_time, part_index, key_signature
    )
    chord_notes.append(note1)
    if duration_divisions1 > max_duration_divisions:
        max_duration_divisions = duration_divisions1

    note2, duration_divisions2, voice_number2, is_chord2, is_rest2, _ = parse_note_element(
        elem2, ns_tag, divisions, tempo, current_time, part_index, key_signature
    )
    chord_notes.append(note2)
    if duration_divisions2 > max_duration_divisions:
        max_duration_divisions = duration_divisions2

    duration = (max_duration_divisions / divisions) * (60.0 / tempo)
    current_time += duration

    assert note1 is not None
    assert note2 is not None
    assert note1['start_time'] == note2['start_time'] == 0.0
    assert is_chord2 is True
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
    divisions = 1
    tempo = 60.0
    part_index = 0
    key_signature = 0

    current_times = {1: 0.0, 2: 0.0}

    note1, duration_divisions1, voice_number1, _, _, updated_current_time1 = parse_note_element(
        elem1, ns_tag, divisions, tempo, current_times[1], part_index, key_signature
    )
    current_times[voice_number1] = updated_current_time1

    note2, duration_divisions2, voice_number2, _, _, updated_current_time2 = parse_note_element(
        elem2, ns_tag, divisions, tempo, current_times[2], part_index, key_signature
    )
    current_times[voice_number2] = updated_current_time2

    assert note1['start_time'] == 0.0
    assert note2['start_time'] == 0.0
    assert note1['voice'] == 1
    assert note2['voice'] == 2
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

    divisions = 1
    tempo = 60.0
    part_index = 0
    key_signature = 0
    current_time = 0.0

    elem1 = ET.fromstring(xml_note1)
    note1, duration_divisions1, voice_number1, _, _, updated_current_time1 = parse_note_element(
        elem1, ns_tag, divisions, tempo, current_time, part_index, key_signature
    )
    current_time = updated_current_time1

    elem2 = ET.fromstring(xml_note2)
    note2, duration_divisions2, voice_number2, _, _, updated_current_time2 = parse_note_element(
        elem2, ns_tag, divisions, tempo, current_time, part_index, key_signature
    )
    current_time = updated_current_time2

    assert note1['start_time'] == 0.0
    assert note1['duration'] == 1.0
    assert note2['start_time'] == 1.0
    assert note2['duration'] == 2.0
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
        <duration>2</duration>
        <voice>1</voice>
    </note>
    '''

    elem1 = ET.fromstring(xml_note1)
    elem2 = ET.fromstring(xml_note2)
    divisions = 1
    tempo = 60.0
    current_time = 0.0
    part_index = 0
    key_signature = 0

    chord_notes = []
    max_duration_divisions = 0

    note1, duration_divisions1, voice_number1, is_chord1, _, _ = parse_note_element(
        elem1, ns_tag, divisions, tempo, current_time, part_index, key_signature
    )
    chord_notes.append(note1)
    if duration_divisions1 > max_duration_divisions:
        max_duration_divisions = duration_divisions1

    note2, duration_divisions2, voice_number2, is_chord2, _, _ = parse_note_element(
        elem2, ns_tag, divisions, tempo, current_time, part_index, key_signature
    )
    chord_notes.append(note2)
    if duration_divisions2 > max_duration_divisions:
        max_duration_divisions = duration_divisions2

    duration = (max_duration_divisions / divisions) * (60.0 / tempo)
    current_time += duration

    assert note1['start_time'] == note2['start_time'] == 0.0
    assert note1['duration'] == 1.0
    assert note2['duration'] == 2.0
    assert current_time == 2.0

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

    divisions = 1
    part_index = 0
    key_signature = 0

    current_time = 0.0

    tempo1 = 60.0
    elem1 = ET.fromstring(xml_note1)
    note1, duration_divisions1, voice_number1, _, _, updated_current_time1 = parse_note_element(
        elem1, ns_tag, divisions, tempo1, current_time, part_index, key_signature
    )
    current_time = updated_current_time1

    tempo2 = 120.0
    elem2 = ET.fromstring(xml_note2)
    note2, duration_divisions2, voice_number2, _, _, updated_current_time2 = parse_note_element(
        elem2, ns_tag, divisions, tempo2, current_time, part_index, key_signature
    )
    current_time = updated_current_time2

    assert note1['start_time'] == 0.0
    assert note1['duration'] == 1.0
    assert note2['start_time'] == 1.0
    assert note2['duration'] == 0.5
    assert current_time == 1.5

