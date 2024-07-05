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
    
    notes = []
    for note in xml.notes:
        note_dict = {'start_time': note.start_time, 'pitch': note.pitch, 'duration': note.duration}
        notes.append(note_dict)


def parse_musicxml(xml_str):
    from musicxml.parser.parser import _parse_node
    xml = ET.fromstring(xml_str)
    return _parse_node(xml)    
