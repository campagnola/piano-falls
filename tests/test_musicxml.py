import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytest
import tempfile
import os
import zipfile
from pianofalls.musicxml import load_musicxml


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
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
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
