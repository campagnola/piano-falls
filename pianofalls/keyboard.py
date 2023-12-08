from .qt import QtWidgets, RectItem, Color, Brush


class Keyboard(QtWidgets.QGraphicsWidget):
    def __init__(self):
        super().__init__()
        self.keys = self.key_spec()
        for key in self.keys:
            key['pressed'] = False
            key['item'] = KeyItem(key)
            key['item'].setParentItem(self)

    @staticmethod
    def key_spec():
        """Generate a list of dicts describing the shape and location of piano keys."""
        width = 88
        height = 0.114 * width
        white_key_width = 88 / 52
        black_key_width = 88 * (7 / 52) / 12
        black_key_offset = 3.5 * white_key_width - 5.5 * black_key_width
        white_key_index = 0
        black_key_index = 0
        keys = []

        for key_id in range(88):
            is_black_key = (key_id % 12) in [1, 4, 6, 9, 11]
            if is_black_key:
                key = {
                    'x_pos': key_id * black_key_width + black_key_offset,
                    'height': 0.6,
                    'width': black_key_width,
                    'color': (0, 0, 0),
                    'sub_index': black_key_index,
                    'is_black_key': True,
                }
            else:
                key = {
                    'x_pos': white_key_index * white_key_width,
                    'height': 1.0,
                    'width': white_key_width,
                    'color': (255, 255, 255),
                    'sub_index': white_key_index,
                    'is_black_key': False,
                }
            key['key_id'] = key_id
            keys.append(key)
            if is_black_key:
                black_key_index += 1
            else:
                white_key_index += 1
        return keys

    def midi_message(self, msg):
        if msg.type == 'note_on':
            self.key_on(msg.note - 21)
        elif msg.type == 'note_off':
            self.key_off(msg.note - 21)

    def key_on(self, key_id):
        key = self.keys[key_id]
        key['pressed'] = True
        key['item'].update_press_state()

    def key_off(self, key_id):
        key = self.keys[key_id]
        key['pressed'] = False
        key['item'].update_press_state()


class KeyItem(RectItem):
    def __init__(self, key):
        super().__init__(
            x=key['x_pos'], 
            y=-0.1, 
            w=key['width'], 
            h=10.1 * key['height'],
            brush=key['color'],
            pen=(0, 0, 0),
            radius=0.2,
            z=10 if key['is_black_key'] else 0,
        )
        self.key = key

    def update_press_state(self):
        if self.key['pressed']:
            color = Color(self.key['color']).mix(Color((150, 180, 220)))
            self.setBrush(Brush(color))
        else:
            self.setBrush(Brush(self.key['color']))
