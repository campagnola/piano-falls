import numpy as np
from pianofalls.qt import QtGui, QtCore


class GraphicsViewUpdateWatcher(QtCore.QObject):
    new_frame = QtCore.Signal(object)

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.timer = QtCore.QTimer()
        # use qt event filter to detect when view is repainted
        view.viewport().installEventFilter(self)
        # import pyqtgraph as pg
        # self.v = pg.ImageView()
        # self.v.show()

    def eventFilter(self, obj, event):
        try:
            if obj == self.view.viewport() and event.type() == QtCore.QEvent.Paint:
                self.timer.singleShot(0, self.emit_frame)
        except RuntimeError:
            pass  # exit error
        return False
    
    def emit_frame(self):
        # import time
        # start = time.time()
        # frame = self.widget.grab().toImage()
        # print(time.time() - start)
        # array = ndarray_from_qimage(frame)[..., :3]
        # self.new_frame.emit(array[:64, :512].copy())

        source_rect = self.view.waterfall.sceneBoundingRect()
        source_rect.setLeft(-2)
        source_rect.setRight(source_rect.right() + 2)
        source_rect.setTop(source_rect.bottom() - source_rect.width() * 64 / 512)
        img = render_scene_to_rgb_bytes(self.view.scene, source_rect, 512, 64)
        # self.v.setImage(img.transpose(1, 0, 2))
        self.new_frame.emit(img)


def render_scene_to_rgb_bytes(scene, source_rect, width, height):
    # Create a QImage with the specified size and format
    image = QtGui.QImage(width, height, QtGui.QImage.Format_RGB888)
    
    # Fill the image with white (optional)
    image.fill(QtCore.Qt.black)
    
    # Create a QPainter to paint on the QImage
    painter = QtGui.QPainter(image)

    # # Calculate the scaling factor
    # scale_x = width / source_rect.width()
    # scale_y = height / source_rect.height()
    
    # # Apply the scaling transformation
    # painter.scale(scale_x, scale_y)

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
