from qtpy import QtWidgets, QtGui, QtCore

class View(QtWidgets.QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QtWidgets.QGraphicsScene(parent=self)
        self.setScene(self.scene)

        self.setBackgroundRole(QtGui.QPalette.ColorRole.NoRole)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))        
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)

        self.keys = []
        self.items = []

        self.keyboard = Keyboard()
        self.scene.addItem(self.keyboard)

        self.waterfall = Waterfall()
        self.scene.addItem(self.waterfall)

        self.resizeEvent()


    def resizeEvent(self, event=None):
        w = 88
        h = w * self.height() / self.width()
        self.fitInView(QtCore.QRectF(0, 0, w, h), QtCore.Qt.AspectRatioMode.IgnoreAspectRatio)

        key_height = 88 * 0.114
        waterfall_height = h - key_height
        self.keyboard.setGeometry(0, waterfall_height, 88, key_height)
        self.waterfall.setGeometry(0, 0, 88, waterfall_height)

    def wheelEvent(self, ev):
        # super().wheelEvent(ev)
        return


class Waterfall(QtWidgets.QGraphicsWidget):
    def __init__(self):
        super().__init__()
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape)

        self.notes = []
        for i in range(88):
            note = RectItem(i, i, 1, 1, pen=(255, 255, 255), brush=(100, 100, 255))
            self.notes.append(note)
            note.setParentItem(self)


class Keyboard(QtWidgets.QGraphicsWidget):
    def __init__(self):
        super().__init__()

        width = 88
        height = 0.114 * width
        white_key_width = 88 / 52
        black_key_width = 88 * (7 / 52) / 12
        black_key_offset = 3.5 * white_key_width - 5.5 * black_key_width
        white_key_index = 0
        black_key_index = 0
        self.keys = []

        for key_id in range(88):
            is_black_key = (key_id % 12) in [1, 4, 6, 9, 11]
            if is_black_key:
                key = {
                    'x_pos': key_id * black_key_width + black_key_offset,
                    'height': 0.6,
                    'width': black_key_width,
                    'color': (0, 0, 0),
                    'sub_index': black_key_index,
                }
            else:
                key = {
                    'x_pos': white_key_index * white_key_width,
                    'height': 1.0,
                    'width': white_key_width,
                    'color': (255, 255, 255),
                    'sub_index': white_key_index,
                }
            key['key_id'] = key_id
            key['pressed'] = False
            key['item'] = RectItem(
                x=key['x_pos'], 
                y=-0.1, 
                w=key['width'], 
                h=10.1 * key['height'],
                brush=key['color'],
                pen=(0, 0, 0),
                radius=0.2,
                z=10 if is_black_key else 0,
            )
            key['item'].setParentItem(self)
            self.keys.append(key)
            if is_black_key:
                black_key_index += 1
            else:
                white_key_index += 1


class Pen(QtGui.QPen):
    def __init__(self, r, g=None, b=None):
        if isinstance(r, tuple):
            r, g, b = r
        if r is None:
            super().__init__(QtGui.QPen.NoPen)
        else:
            super().__init__(QtGui.QColor(r, g, b))
        self.setCosmetic(True)


class Brush(QtGui.QBrush):
    def __init__(self, r, g=None, b=None):
        if isinstance(r, tuple):
            r, g, b = r
        if r is None:
            super().__init__(QtGui.QPen.NoBrush)
        else:
            super().__init__(QtGui.QColor(r, g, b))


class RectItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, x, y, w, h, pen, brush, radius=0, z=0):
        super().__init__(x, y, w, h)
        self.setPen(Pen(pen))
        self.setBrush(Brush(brush))
        self.setZValue(z)


if __name__ == '__main__':
    import sys

    app = QtWidgets.QApplication([])
    w = View()
    w.show()

    if sys.flags.interactive == 0:
        app.exec_()