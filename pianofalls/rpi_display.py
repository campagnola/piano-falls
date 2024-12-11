import socket, threading, time, atexit
import numpy as np
import pyqtgraph as pg
from .qt import QtGui, QtCore
from .config import config
from .keyboard import Keyboard
from .song import Note


def interpolate_frames(frame1, frame2, s, gamma=0.5):
    """Interpolate between two frames using gamma correction
    When s=0, the output is frame1; when s=1, the output is frame2"""
    interp = frame1 * (1 - s)**gamma + frame2 * s**gamma
    return np.clip(interp, 0, 255).astype('uint8')


def draw_interpolated_line(frame, row, col1, col2, color, gamma=0.5):
    irow = int(row)
    row_fraction = row % 1
    if 0 <= irow < frame.shape[0]:
        frame[irow, col1:col2] = np.clip(frame[irow, col1:col2].astype('int16') + color * (1 - row_fraction)**gamma, 0, 255).astype('uint8')
    if 0 <= irow + 1 < frame.shape[0]:
        frame[irow+1, col1:col2] = np.clip(frame[irow+1, col1:col2].astype('int16') + color * row_fraction**gamma, 0, 255).astype('uint8')
    return (irow, irow+1), (1-row_fraction, row_fraction)


def draw_interpolated_box(frame, row1, row2, col1, col2, color, gamma=0.5):
    """
    Row1 and row2 are floats representing the top and bottom of the box to draw.
    Example: 
    row1 = 1.3, row2 = 3.7
    [ 0 | 1 | 2 | 3 | 4 | 5 ]
         ^row1     ^row2
        ^start_row  ^end_row 
    """
    # decide how much box to draw in each pixel
    start_row = int(row1)
    end_row = int(row2) + 1
    draw_amount = np.ones(end_row - start_row)
    draw_amount[0] -= row1 - start_row
    draw_amount[-1] -= end_row - row2
    # draw first row
    if 0 <= start_row < frame.shape[0]:
        frame[start_row, col1:col2] = color * draw_amount[0]**gamma
    # draw middle rows
    if len(draw_amount) > 2:
        r1 = np.clip(start_row + 1, 0, frame.shape[0])
        r2 = np.clip(end_row - 1, 0, frame.shape[0])
        frame[r1:r2, col1:col2] = color
    # draw last row if needed
    if len(draw_amount) > 1 and (0 <= end_row < frame.shape[0]):
        frame[end_row-1, col1:col2] = color * draw_amount[-1]**gamma


class FrameSender:
    def __init__(self, host, port, udp=False):
        
        self.host = host
        self.port = port
        self.udp = udp

        self.next_frame = None
        self.stop = False

        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

        atexit.register(self.close)

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

            self._send_frame(sock, frame)

        # send a blank frame before closing socket
        rows, cols = config['rpi_display']['resolution']
        self._send_frame(sock, np.zeros((rows, cols, 3), dtype='uint8'))
        time.sleep(0.2)  # why is this necessary? without it, the last frame is not displayed

        sock.close()

    def send_frame(self, frame):
        self.next_frame = frame

    def close(self):
        self.stop = True

    def _send_frame(self, sock, frame):
        if self.udp:
            frame = frame.tobytes()
            sent = 0
            max_size = 65507
            while sent < len(frame):
                sock.sendto(frame[sent:sent+max_size], (self.host, self.port))
                sent += max_size
        else:
            sock.sendall(frame)




class RPiRenderer:
    def __init__(self, mainwindow, sender):
        self.mainwindow = mainwindow
        self.song = None
        self.time_range = (0, 1)
        self.sender = sender

        mainwindow.song_changed.connect(self.set_song)
        mainwindow.scroller.current_time_changed.connect(self.set_time)

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(1000 // 30)

    def set_song(self, song):
        self.song = song

    def set_time(self, time):
        self.set_time_range((time, time + 3))

    def set_time_range(self, time_range):
        self.time_range = time_range

    def render_frame(self, time_range):
        track_colors = self.mainwindow.track_list.track_colors()
        rows, cols = config['rpi_display']['resolution']
        first_col, last_col = config['rpi_display']['bounds']
        used_cols = last_col - first_col
        all_keyspec = Keyboard.key_spec()
        frame = np.zeros((rows, cols, 3), dtype='uint8')
        
        events = self.song.get_events_active_in_range(time_range)
        row_scale = rows / (time_range[1] - time_range[0])  # pixels per second
        col_scale = used_cols / 88  # pixels per white key

        # how many pixels have we moved to account for start of time range (float)
        y_pixel_offset = time_range[0] * row_scale

        for event in events:
            if not isinstance(event, Note):
                continue
            note = event
            if note.duration == 0:
                continue
            try:
                keyspec = all_keyspec[note.pitch.key]
            except IndexError:
                continue
            color = track_colors.get(note.track, (100, 100, 100))
            start_y_pixel = y_pixel_offset + (frame.shape[0]-1) - (row_scale * note.start_time)
            stop_y_pixel = start_y_pixel - (row_scale * note.duration)

            w = int(keyspec['width'] * col_scale)
            x1 = first_col + int(keyspec['x_pos'] * col_scale)
            x2 = x1 + w
            draw_interpolated_box(frame, stop_y_pixel, start_y_pixel, x1, x2, np.array(color))
            draw_interpolated_line(frame, start_y_pixel, x1, x2, np.array([255, 255, 255]))


        return frame
    
    def update_frame(self):
        if self.song is None:
            return
        frame = self.render_frame(self.time_range)
        self.sender.send_frame(frame)


class GraphicsViewUpdateWatcher(QtCore.QObject):
    """Every time a GraphicsView is repainted, emit a signal with the new frame.
    """
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

