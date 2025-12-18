from .qt import QtWidgets, QtCore, QtGui


def rating_to_stars(rating):
    """
    Convert rating (0-10) to star display string (0-5 stars).
    """
    full_stars = rating // 2
    half_star = (rating % 2) == 1
    empty_stars = 5 - full_stars - (1 if half_star else 0)

    stars = '★' * full_stars
    if half_star:
        stars += '⯪'  # Half star
    stars += '☆' * empty_stars

    return stars


class RatingWidget(QtWidgets.QWidget):
    """
    Popup widget for selecting song ratings.

    Displays 5 stars that can be clicked to set rating from 0-10
    (each star represents 2 points, with half-star precision).

    Emits rating_changed signal with new rating value (0-10).
    """

    rating_changed = QtCore.Signal(int)

    def __init__(self, current_rating=0, parent=None):
        super().__init__(parent, QtCore.Qt.Popup | QtCore.Qt.FramelessWindowHint)
        self.current_rating = current_rating
        self.hover_rating = current_rating

        # Create label to show stars
        self.label = QtWidgets.QLabel(self)
        font = QtGui.QFont()
        font.setPointSize(12)
        self.label.setFont(font)
        self.label.setAlignment(QtCore.Qt.AlignCenter)

        # Setup UI
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.setContentsMargins(2, 2, 2, 2)

        self.setMouseTracking(True)
        self.label.setMouseTracking(True)
        self.setFixedSize(180, 50)

        # Styling
        self.setStyleSheet("""
            RatingWidget {
                background-color: white;
                border: 2px solid #555;
                border-radius: 4px;
            }
            QLabel {
                color: #FFD700;
            }
        """)

        self._update_display()

    def _update_display(self):
        """Update the star display based on hover_rating."""
        self.label.setText(rating_to_stars(self.hover_rating))

    def mouseMoveEvent(self, event):
        """Update hover_rating based on mouse position."""
        x = event.pos().x()

        self.hover_rating = min(max(int(11 * x / self.width()), 0), 10)
        self._update_display()

    def mousePressEvent(self, event):
        """Set rating and emit signal."""
        if event.button() == QtCore.Qt.LeftButton:
            self.rating_changed.emit(self.hover_rating)
            self.close()

    def leaveEvent(self, event):
        """Restore current rating when mouse leaves."""
        self.hover_rating = self.current_rating
        self._update_display()

    def keyPressEvent(self, event):
        """Close on Escape."""
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)
