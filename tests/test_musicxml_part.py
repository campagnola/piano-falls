import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytest
import xml.etree.ElementTree as ET
from pianofalls.musicxml import parse_part


# Define the helper function ns_tag
def ns_tag(tag):
    return tag


def test_part_with_tempo_changes():
    xml_part = '''
    <part id="P1">
        <measure number="1">
            <attributes>
                <divisions>4</divisions>
            </attributes>
            <direction placement="above">
                <sound tempo="60"/>
            </direction>
            <note>
                <pitch>
                    <step>C</step>
                    <octave>4</octave>
                </pitch>
                <duration>4</duration>
                <voice>1</voice>
            </note>
        </measure>
        <measure number="2">
            <direction placement="above">
                <sound tempo="120"/>
            </direction>
            <note>
                <pitch>
                    <step>D</step>
                    <octave>4</octave>
                </pitch>
                <duration>4</duration>
                <voice>1</voice>
            </note>
        </measure>
    </part>
    '''
    part_elem = ET.fromstring(xml_part)
    part_index = 0
    initial_tempo = 60.0  # Initial tempo

    notes = parse_part(part_elem, ns_tag, part_index, initial_tempo=initial_tempo)

    assert len(notes) == 2
    note1, note2 = notes

    # Note 1 (Measure 1)
    assert note1['pitch'].midi_note == 60  # C4
    assert note1['start_time'] == 0.0
    duration_note1 = (4 / 4) * (60 / 60)  # divisions = 4, tempo = 60 BPM
    assert note1['duration'] == duration_note1

    # Note 2 (Measure 2)
    start_time_note2 = note1['start_time'] + note1['duration']
    assert note2['pitch'].midi_note == 62  # D4
    assert note2['start_time'] == start_time_note2
    duration_note2 = (4 / 4) * (60 / 120)  # divisions = 4, tempo = 120 BPM
    assert note2['duration'] == duration_note2

def test_part_with_time_signature_changes():
    xml_part = '''
    <part id="P1">
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
                    <step>E</step>
                    <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
            </note>
            <note>
                <pitch>
                    <step>F</step>
                    <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
            </note>
            <note>
                <pitch>
                    <step>G</step>
                    <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
            </note>
        </measure>
        <measure number="2">
            <attributes>
                <divisions>2</divisions>
                <time>
                    <beats>4</beats>
                    <beat-type>4</beat-type>
                </time>
            </attributes>
            <note>
                <pitch>
                    <step>A</step>
                    <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
            </note>
            <note>
                <pitch>
                    <step>B</step>
                    <octave>4</octave>
                </pitch>
                <duration>2</duration>
                <voice>1</voice>
            </note>
            <note>
                <pitch>
                    <step>C</step>
                    <octave>5</octave>
                </pitch>
                <duration>4</duration>
                <voice>1</voice>
            </note>
        </measure>
    </part>
    '''
    part_elem = ET.fromstring(xml_part)
    part_index = 0
    initial_tempo = 90.0  # Set a constant tempo for simplicity

    notes = parse_part(part_elem, ns_tag, part_index, initial_tempo=initial_tempo)

    assert len(notes) == 6
    total_duration = 0.0

    # Measure 1 notes
    for i in range(3):
        note = notes[i]
        expected_start_time = total_duration
        expected_duration = (2 / 2) * (60 / initial_tempo)  # divisions = 2
        assert note['start_time'] == pytest.approx(expected_start_time, 0.0001)
        assert note['duration'] == pytest.approx(expected_duration, 0.0001)
        total_duration += expected_duration

    # Measure 2 notes
    for i in range(3, 6):
        note = notes[i]
        expected_start_time = total_duration
        if i < 5:
            expected_duration = (2 / 2) * (60 / initial_tempo)
            total_duration += expected_duration
        else:
            expected_duration = (4 / 2) * (60 / initial_tempo)  # Whole note
            total_duration += expected_duration
        assert note['start_time'] == pytest.approx(expected_start_time, 0.0001)
        assert note['duration'] == pytest.approx(expected_duration, 0.0001)

def test_part_with_key_signature_changes():
    xml_part = '''
    <part id="P1">
        <measure number="1">
            <attributes>
                <divisions>4</divisions>
                <key>
                    <fifths>0</fifths> <!-- C major -->
                </key>
            </attributes>
            <note>
                <pitch>
                    <step>F</step>
                    <octave>4</octave>
                </pitch>
                <duration>4</duration>
                <voice>1</voice>
            </note>
        </measure>
        <measure number="2">
            <attributes>
                <key>
                    <fifths>1</fifths> <!-- G major -->
                </key>
            </attributes>
            <note>
                <pitch>
                    <step>F</step>
                    <octave>4</octave>
                </pitch>
                <duration>4</duration>
                <voice>1</voice>
            </note>
        </measure>
    </part>
    '''
    part_elem = ET.fromstring(xml_part)
    part_index = 0
    initial_tempo = 120.0  # Set a constant tempo for simplicity

    notes = parse_part(part_elem, ns_tag, part_index, initial_tempo=initial_tempo)

    assert len(notes) == 2
    note1, note2 = notes

    # Note 1 (C major): F natural
    assert note1['pitch'].midi_note == 65  # F4

    # Note 2 (G major): F#
    # Since the key signature is G major (one sharp), F should be sharp
    # MIDI note for F#4 is 66
    assert note2['pitch'].midi_note == 66  # F#4

def test_part_with_note_ties():
    xml_part = '''
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
                <duration>4</duration>
                <tie type="start"/>
                <notations>
                    <tied type="start"/>
                </notations>
                <voice>1</voice>
            </note>
        </measure>
        <measure number="2">
            <note>
                <pitch>
                    <step>G</step>
                    <octave>4</octave>
                </pitch>
                <duration>4</duration>
                <tie type="stop"/>
                <notations>
                    <tied type="stop"/>
                </notations>
                <voice>1</voice>
            </note>
        </measure>
    </part>
    '''
    part_elem = ET.fromstring(xml_part)
    part_index = 0
    initial_tempo = 60.0  # Set a constant tempo for simplicity

    notes = parse_part(part_elem, ns_tag, part_index, initial_tempo=initial_tempo)

    assert len(notes) == 1
    note = notes[0]

    # The note's duration should be the sum of the durations in both measures
    expected_duration = ((4 / 4) * (60 / initial_tempo)) * 2  # Whole note duration * 2
    assert note['pitch'].midi_note == 67  # G4
    assert note['start_time'] == 0.0
    assert note['duration'] == expected_duration

def test_part_multiple_voices_with_state_carryover():
    xml_part = '''
    <part id="P1">
        <measure number="1">
            <attributes>
                <divisions>4</divisions>
            </attributes>
            <!-- Voice 1 -->
            <note>
                <pitch>
                    <step>C</step>
                    <octave>5</octave>
                </pitch>
                <duration>4</duration>
                <voice>1</voice>
            </note>
            <!-- Voice 2 -->
            <note>
                <pitch>
                    <step>E</step>
                    <octave>4</octave>
                </pitch>
                <duration>4</duration>
                <voice>2</voice>
            </note>
        </measure>
        <measure number="2">
            <direction placement="above">
                <sound tempo="90"/>
            </direction>
            <!-- Voice 1 -->
            <note>
                <pitch>
                    <step>D</step>
                    <octave>5</octave>
                </pitch>
                <duration>4</duration>
                <voice>1</voice>
            </note>
            <!-- Voice 2 -->
            <note>
                <pitch>
                    <step>F</step>
                    <octave>4</octave>
                </pitch>
                <duration>4</duration>
                <voice>2</voice>
            </note>
        </measure>
    </part>
    '''
    part_elem = ET.fromstring(xml_part)
    part_index = 0
    initial_tempo = 60.0  # Initial tempo

    notes = parse_part(part_elem, ns_tag, part_index, initial_tempo=initial_tempo)

    assert len(notes) == 4
    # Separate notes by voice
    voice1_notes = [n for n in notes if n['voice'] == 1]
    voice2_notes = [n for n in notes if n['voice'] == 2]

    # Durations and start times
    duration_measure1 = (4 / 4) * (60 / initial_tempo)  # divisions = 4, tempo = 60 BPM
    duration_measure2 = (4 / 4) * (60 / 90.0)  # divisions = 4, tempo = 90 BPM

    # Voice 1 assertions
    assert len(voice1_notes) == 2
    note_v1_1, note_v1_2 = voice1_notes
    assert note_v1_1['start_time'] == 0.0
    assert note_v1_1['duration'] == duration_measure1
    assert note_v1_2['start_time'] == note_v1_1['start_time'] + note_v1_1['duration']
    assert note_v1_2['duration'] == duration_measure2

    # Voice 2 assertions
    assert len(voice2_notes) == 2
    note_v2_1, note_v2_2 = voice2_notes
    assert note_v2_1['start_time'] == 0.0
    assert note_v2_1['duration'] == duration_measure1
    assert note_v2_2['start_time'] == note_v2_1['start_time'] + note_v2_1['duration']
    assert note_v2_2['duration'] == duration_measure2

# Add this to allow the test script to be run directly
if __name__ == '__main__':
    pytest.main()
