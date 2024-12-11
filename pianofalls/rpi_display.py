import numpy as np
from .qt import QtGui, QtCore
from .config import config


import queue
import socket, sys
import threading
import numpy as np
import time




def interpolate_frames(frame1, frame2, s, gamma=0.5):    
    interp = frame1 * (1 - s)**gamma + frame2 * s**gamma
    return np.clip(interp, 0, 255).astype('uint8')


class FrameSender:
    def __init__(self, host, port, udp=False):
        
        self.host = host
        self.port = port
        self.udp = udp

        self.next_frame = None
        self.stop = False

        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        if self.udp:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, data[0].nbytes + 10)
        else:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))

        last_frame = None
        while not self.stop:
            frame = self.next_frame
            if frame is last_frame:
                time.sleep(0.003)
                continue
            last_frame = frame

            if self.udp:
                frame = frame.tobytes()
                sent = 0
                max_size = 65507
                while sent < len(frame):
                    sock.sendto(frame[sent:sent+max_size], (self.host, self.port))
                    sent += max_size
            else:
                sock.sendall(frame)

        sock.close()

    def send_frame(self, frame):
        self.next_frame = frame

    def close(self):
        self.stop = True


class GraphicsViewUpdateWatcher(QtCore.QObject):
    new_frame = QtCore.Signal(object)

    def __init__(self, view):
        super().__init__()
        self.resolution = config['rpi_display']['resolution']
        self.view = view
        self.timer = QtCore.QTimer()
        # use qt event filter to detect when view is repainted
        view.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        try:
            if obj == self.view.viewport() and event.type() == QtCore.QEvent.Paint:
                self.timer.singleShot(0, self.emit_frame)
        except RuntimeError:
            pass  # exit error
        return False
    
    def emit_frame(self):
        img = self.render_frame_from_scene()
        self.new_frame.emit(img)

    def render_frame_from_screenshot(self):
        rows, cols = self.resolution
        frame = self.view.grab().toImage()
        array = ndarray_from_qimage(frame)[..., :3]
        return self.new_frame.emit(array[:rows, :cols].copy())

    def render_frame_from_scene(self):
        rows, cols = self.resolution
        source_rect = self.view.waterfall.sceneBoundingRect()
        source_rect.setLeft(-2)
        source_rect.setRight(source_rect.right() + 2)
        source_rect.setTop(source_rect.bottom() - source_rect.width() * rows / cols)
        return render_scene_to_rgb_bytes(self.view.scene, source_rect, cols, rows)


def render_scene_to_rgb_bytes(scene, source_rect, width, height):
    # Create a QImage with the specified size and format
    image = QtGui.QImage(width, height, QtGui.QImage.Format_RGB888)
    
    # Fill the image with white (optional)
    image.fill(QtCore.Qt.black)
    
    # Create a QPainter to paint on the QImage
    painter = QtGui.QPainter(image)

    # Render the specified region of the scene into the QImage
    target_rect = QtCore.QRectF(0, 0, width, height)
    scene.render(painter, target_rect, source_rect)
    
    # End the painting
    painter.end()
    
    # Extract the 8-bit RGB values
    ptr = image.bits()
    ptr.setsize(image.sizeInBytes())
    
    arr = np.array(ptr).reshape((height, image.bytesPerLine()))[:, :width * 3].reshape((height, width, 3))
    return np.ascontiguousarray(arr)


def ndarray_from_qimage(qimg):
    img_ptr = qimg.bits()

    if img_ptr is None:
        raise ValueError("Null QImage not supported")

    h, w = qimg.height(), qimg.width()
    bpl = qimg.bytesPerLine()
    depth = qimg.depth()
    logical_bpl = w * depth // 8

    # sizeInBytes() was introduced in Qt 5.10
    # however PyQt5 5.12 will fail with:
    #   "TypeError: QImage.sizeInBytes() is a private method"
    # note that sizeInBytes() works fine with:
    #   PyQt5 5.15, PySide2 5.12, PySide2 5.15
    img_ptr.setsize(h * bpl)

    memory = np.frombuffer(img_ptr, dtype=np.ubyte).reshape((h, bpl))
    memory = memory[:, :logical_bpl]

    if depth in (8, 24, 32):
        dtype = np.uint8
        nchan = depth // 8
    elif depth in (16, 64):
        dtype = np.uint16
        nchan = depth // 16
    else:
        raise ValueError("Unsupported Image Type")

    shape = h, w
    if nchan != 1:
        shape = shape + (nchan,)
    arr = memory.view(dtype).reshape(shape)
    return arr.copy()

