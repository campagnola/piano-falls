from .qt import QtCore, QtGui, QtWidgets, GraphicsItemGroup, Pen, Brush, Color
from .song import Song
from .notes_item import NotesItem

# Scene units per second at zoom=1. Used to convert between time and scene coordinates.
_PIXELS_PER_SECOND = 6


class Waterfall(QtWidgets.QGraphicsWidget):
    def __init__(self, display_model):
        super().__init__()
        self.setFlag(self.GraphicsItemFlag.ItemClipsChildrenToShape)

        self.group = GraphicsItemGroup(self)

        self.notes_item = NotesItem(display_model)
        self.group.addToGroup(self.notes_item)

        self._loop_items = []

        self.current_time = 0.0
        self.requested_time = 0.0
        self.zoom_factor = 1.0
        # Vertical offset of the play line from the bottom, in seconds at zoom=1.
        # Notes at current_time appear at this visual position rather than at the bottom.
        self.play_line_seconds = 0.0

        # Horizontal line marking where notes should be played.
        # Drawn in widget-local coordinates (not subject to the note transform).
        play_line_pen = Pen((55, 55, 55, 200))
        play_line_pen.setWidthF(1.5)
        self.play_line_item = QtWidgets.QGraphicsLineItem(0, 0, 88, 0, self)
        self.play_line_item.setPen(play_line_pen)
        self.play_line_item.setZValue(10)

        # limit the update rate to 60 fps
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self._update_time)
        self.update_timer.start(16)

        self.update_transform()

    def set_time(self, time):
        self.requested_time = time

    def _update_time(self):
        req_time = self.requested_time
        if req_time != self.current_time:    
            self.current_time = req_time
            self.update_transform()

    def zoom(self, factor: float):
        """Multiply the zoom by the given factor"""
        self.set_zoom(self.zoom_factor * factor)

    def set_zoom(self, factor: float):
        self.zoom_factor = factor
        self.update_transform()

    def set_play_line(self, seconds: float):
        """Set the play line offset from the bottom, in seconds at zoom=1."""
        self.play_line_seconds = seconds
        self.update_transform()

    def update_transform(self):
        # The play line sits at a fixed pixel distance from the bottom regardless of zoom.
        # play_line_seconds * _PIXELS_PER_SECOND converts to scene units at zoom=1.
        play_line_scene_y = self.play_line_seconds * _PIXELS_PER_SECOND
        base_y = self.geometry().height() - play_line_scene_y

        transform = QtGui.QTransform()
        transform.translate(0, base_y)
        transform.scale(1, -_PIXELS_PER_SECOND * self.zoom_factor)
        transform.translate(0, -self.current_time)
        self.group.setTransform(transform)

        self.play_line_item.setPos(0, base_y)

    def set_loops(self, loops):
        """Update the display to show active loop regions as horizontal bands."""
        # Remove existing loop items from the scene
        for item in self._loop_items:
            if item.scene() is not None:
                item.scene().removeItem(item)
        self._loop_items = []

        fill_brush = Brush((100, 200, 100, 40))
        line_pen = Pen((100, 200, 100, 180))

        for loop in loops:
            if not loop.get('active'):
                continue
            start = loop['start']
            end = loop['end']

            # Low-opacity filled region between loop boundaries
            rect = QtWidgets.QGraphicsRectItem(0, start, 88, end - start)
            rect.setBrush(fill_brush)
            rect.setPen(Pen(None))
            rect.setZValue(-2)
            self.group.addToGroup(rect)
            self._loop_items.append(rect)

            # Boundary lines at start and end
            for y in (start, end):
                line = QtWidgets.QGraphicsLineItem(0, y, 88, y)
                line.setPen(line_pen)
                line.setZValue(-1)
                self.group.addToGroup(line)
                self._loop_items.append(line)

    def resizeEvent(self, event):
        self.update_transform()


