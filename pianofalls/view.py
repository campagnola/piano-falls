from .qt import QtWidgets, QtGui, QtCore
from .keyboard import Keyboard
from .waterfall import Waterfall
from .midi import Song


class View(QtWidgets.QGraphicsView):

    wheel_event = QtCore.Signal(object)

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
        self.setRenderHints(QtGui.QPainter.Antialiasing)

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

    def wheelEvent(self, event):
        self.wheel_event.emit(event)

    def set_song(self, song:Song):
        self.waterfall.set_song(song)
        self.song = song
        self.resizeEvent()

    def set_time(self, time):
        self.waterfall.set_time(time)

    def connect_midi_input(self, midi_input):
        midi_input.message.connect(self.on_midi_message, QtCore.Qt.ConnectionType.QueuedConnection)

    def on_midi_message(self, midi_input, msg):
        self.keyboard.midi_message(msg)
