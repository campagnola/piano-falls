import zipfile
import xml.etree.ElementTree as ET


def load_musicxml(filename):
    """Load a MusicXML file"""
    if filename.endswith('.mxl'):
        with zipfile.ZipFile(filename) as z:
            with z.open('META-INF/container.xml') as f:
                container = ET.parse(f)
                rootfile = container.find('.//rootfile')
                musicxml_path = rootfile.attrib['full-path']
            with z.open(musicxml_path) as f:
                xml = parse_musicxml(f.read())
    else:
        with open(filename) as f:
            xml = parse_musicxml(f.read())

    # iterate over parts in the score
    notes = []
    xml.find_children('XMLPartList')[0].find_children('XMLScorePart')[0]

    for part in xml.findall('.//part'):
        current_time = 0
        for measure in part.findall('.//measure'):
            for note in measure.findall('.//note'):
                note_dict = {
                    'start_time': msg_time, 'pitch': Pitch(midi_note=msg.note), 'duration': None, 
                    'track': message['track'], 'track_n': message['track_n'],
                    'on_msg': message, 'off_msg': None
                }
                notes.append(note_dict)
        parts.append(notes)
    return xml


def parse_musicxml(xml_str):
    from musicxml.parser.parser import _parse_node
    xml = ET.fromstring(xml_str)
    return _parse_node(xml)    
