from .qt import QtWidgets, QtGui, QtCore
from .notes_item import NotesItem
from .song import Song


class Overview(QtWidgets.QGraphicsView):
    clicked = QtCore.Signal(object)

    def __init__(self):
        super().__init__()

        self.setBackgroundRole(QtGui.QPalette.ColorRole.NoRole)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))        
        # self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setRenderHints(QtGui.QPainter.Antialiasing)

        self._scene = QtWidgets.QGraphicsScene(parent=self)
        self.setScene(self._scene)

        self.group = QtWidgets.QGraphicsItemGroup()
        tr = QtGui.QTransform()
        tr.scale(1, -1)
        self.group.setTransform(tr)
        self._scene.addItem(self.group)

        self.notes_item = NotesItem()
        self.notes_item.setParentItem(self.group)

        self.time_line = QtWidgets.QGraphicsLineItem()
        pen = QtGui.QPen(QtGui.QColor(255, 255, 255, 128))
        pen.setCosmetic(True)
        self.time_line.setPen(pen)
        self.time_line.setParentItem(self.group)

    def set_song(self, song: Song):
        self.notes_item.set_notes(song.notes)
        self.resizeEvent()

    def set_time(self, time):
        self.time_line.setLine(0, time, 88, time)

    def mousePressEvent(self, event):
        time = self.group.mapFromScene(self.mapToScene(event.pos())).y()
        self.clicked.emit(time)
        event.accept()

    def mouseReleaseEvent(self, event):
        pass

    def mouseMoveEvent(self, event):
        time = self.group.mapFromScene(self.mapToScene(event.pos())).y()
        self.clicked.emit(time)

    def resizeEvent(self, event=None):
        self.fitInView(self.notes_item, QtCore.Qt.AspectRatioMode.IgnoreAspectRatio)
        
