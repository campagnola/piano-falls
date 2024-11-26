import os, sys, subprocess, shutil, tempfile, copy, code, pdb
import xml.etree.ElementTree as ET
from pianofalls.musicxml import MusicXMLParser, load_musicxml, write_mxl
from pianofalls.midi import load_midi
from pianofalls.song import Song


def count_measures(mxl_root: ET.Element):
    # loop over all parts
    n_measures = 0
    for part in mxl_root.findall('part'):
        n_measures += len(part.findall('measure'))

    return n_measures

def extract_measures(mxl_root, n):
    """Return a deep copy of the original xml with only the first n measures"""
    new_root = copy.deepcopy(mxl_root)
    measures_remaining = n
    for part in new_root.findall('part'):
        measures = part.findall('measure')
        for measure in measures:
            if measures_remaining > 0:
                measures_remaining -= 1
            else:
                part.remove(measure)
    return new_root


def sort_notes(notes):
    return sorted(notes, key=lambda n: (n.start_time, n.pitch.midi_note))


def compare_songs(song1, song2, names):
    notes1 = sort_notes(song1.notes)
    notes2 = sort_notes(song2.notes)

    print(f'Comparing {names[0]} : {names[1]}')
    print(f'  lengths: {len(notes1)}: {len(notes2)}')
    def close(a, b):
        dif = abs(a - b)
        return dif < 1e-2 or dif / max(abs(a), abs(b)) < 1e-2
    i = 0
    while notes1 and notes2:
        note1 = notes1.pop(0)
        note2 = notes2.pop(0)
        differences = []
        if not close(note1.start_time, note2.start_time):
            differences.append(f'start time {note1.start_time} != {note2.start_time}')
        if note1.pitch != note2.pitch:
            differences.append(f'pitch {note1.pitch} != {note2.pitch}')
        if not close(note1.duration, note2.duration):
            differences.append(f'duration {note1.duration} != {note2.duration}')
        if differences:
            diffs = "\n  ".join(differences)
            print(f'Note {i} differences:\n  {diffs}')
            print(f'   {note1} vs {note2}')
            xmlstr = ET.tostring(note1.xml)
            # replace all "> " with ">\n "
            xmlstr = xmlstr.replace(b'> ', b'>\n ')
            print(xmlstr.decode())
            code.interact(local=locals())
            return False
        i += 1
    if notes1 or notes2:
        print(f'Different number of notes {len(song1.notes)} vs {len(song2.notes)}')
        code.interact(local=locals())
        return False
    return True



if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python test_parser.py <path_to_mxl_file>')
        sys.exit(1)

    mxl_file = sys.argv[1]

    parser = MusicXMLParser()
    original_xml = parser.read_musicxml_file(mxl_file)
    n_measures = count_measures(original_xml)
    assert n_measures > 0, 'No measures found in the musicxml file'
    print(f'Found {n_measures} measures in {mxl_file}')
    
    temp_dir = tempfile.mkdtemp()
    try:
        difference_found = False
        for i in range(1, n_measures):
            print(f'Checking {i} measures...')
            short_xml = extract_measures(original_xml, i)

            # write xml to a temp file
            # temp_mxl_path = os.path.join(temp_dir, f'truncated_{i:04d}.mxl')
            # write_mxl(short_xml, temp_mxl_path)
            temp_mxl_path = os.path.join(temp_dir, f'truncated_{i:04d}.xml')
            with open(temp_mxl_path, 'w') as f:
                xmlstr = ET.tostring(short_xml, encoding='unicode')
                xmlstr = xmlstr.replace('> ', '>\n ')
                f.write(xmlstr)

            # convert temp file to midi
            temp_mid_path = os.path.join(temp_dir, f'truncated_{i:04d}.mid')
            musescore_cmd = f'musescore3 -o "{temp_mid_path}" "{temp_mxl_path}"'
            ret = subprocess.run(musescore_cmd, shell=True)
            if ret.returncode != 0:
                print(f'Error converting {temp_mxl_path} to midi')
                break

            # parse the original song
            song_from_mxl = load_musicxml(temp_mxl_path)
            song_from_mid = load_midi(temp_mid_path)

            # compare files
            try:
                if compare_songs(song_from_mxl, song_from_mid, ('mxl', 'midi')) is False:
                    print(f'Files differ at measure {i}')
                    difference_found = True
                    break
            except Exception as e:  
                # post mortem debug
                print(f'Error comparing songs at measure {i}')
                print(e)
                pdb.post_mortem()
                raise e

        if difference_found is False:
            print('No differences found')
    finally:
        # print(temp_dir)
        shutil.rmtree(temp_dir)

