from PySide6 import QtGui
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsItem,
    QVBoxLayout,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QGestureEvent,
)
from PySide6.QtGui import QPen, QBrush, QColor
from PySide6.QtCore import Qt
import sys
import random

ROW_COUNT = 30
ROW_HEIGHT = 20
COL_COUNT = 200
COL_WIDTH = 20
FIRST_COL_WIDTH = 100
ARROWS = ["←", "→"]


class KnitGraphicsView(QGraphicsView):
    def __init__(self, scene, parent):
        super().__init__(scene, parent)
        self.firstColumn = parent.firstColumn
        self.firstRow = parent.firstRow
        self.cornerMask = parent.cornerMask

        self.grabGesture(Qt.GestureType.PinchGesture)
        # self.grabGesture(Qt.GestureType.TapGesture)

    def scrollContentsBy(self, dx, dy):
        hbar = self.horizontalScrollBar()
        vbar = self.verticalScrollBar()

        currentScale = self.transform().m11()
        hpos = hbar.value() / currentScale
        vpos = vbar.value() / currentScale

        self.firstColumn.setX(hpos)
        self.firstRow.setY(vpos)
        self.cornerMask.setPos(hpos, vpos)

        super().scrollContentsBy(dx, dy)

    def wheelEvent(self, event):
        if Qt.KeyboardModifier.ControlModifier not in event.modifiers():
            return super().wheelEvent(event)

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        """
        Zoom in or out of the view.
        """
        zoomInFactor = 1.01

        # Zoom
        speed = event.angleDelta().y()
        zoomFactor = pow(zoomInFactor, speed)

        self.zoomBy(zoomFactor)

    def zoomBy(self, zoomFactor):
        minScale = 0.5
        maxScale = 4

        currentScale = self.transform().m11()
        newScale = currentScale * zoomFactor

        if newScale < minScale:
            self.scale(minScale / currentScale, minScale / currentScale)
        elif newScale > maxScale:
            self.scale(maxScale / currentScale, maxScale / currentScale)
        else:
            self.scale(zoomFactor, zoomFactor)

    def event(self, evt):
        if isinstance(evt, QGestureEvent):
            return self.gestureEvent(evt)
        return super().event(evt)

    def gestureEvent(self, event):
        pinch = event.gesture(Qt.PinchGesture)
        if pinch:
            self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
            self.zoomBy(pinch.scaleFactor())
        return True


class Window(QMainWindow):
    def __init__(self):
        super().__init__()

        # Window properties
        self.title = "QGraphicsView knit progress POC"
        self.top = 200
        self.left = 500
        self.width = 900
        self.height = 500

        self.InitWindow()

    def InitWindow(self):
        self.setWindowIcon(QtGui.QIcon("codeloop.png"))
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        self.createGraphicsView()

        self.setCentralWidget(self.graphicsView)

        self.show()

    def createGraphicsView(self):
        self.scene = QGraphicsScene()

        self.createShapes()

        # Create QGraphicsView and set its geometry
        self.graphicsView = KnitGraphicsView(self.scene, self)
        self.graphicsView.setGeometry(0, 0, self.width, self.height)
        self.graphicsView.ensureVisible(0, 0, 0, 0)

    def createShapes(self):
        for y in range(ROW_COUNT):
            for x in range(COL_COUNT):
                self.scene.addRect(
                    FIRST_COL_WIDTH + COL_WIDTH * x + 1,
                    ROW_HEIGHT * (y + 1) + 1,
                    COL_WIDTH - 2,
                    ROW_HEIGHT - 2,
                    QPen(Qt.NoPen),
                    QBrush(QColor.fromHsv(random.randrange(360), 200, 200)),
                )

        self.firstRow = self.scene.addRect(
            0, 0, FIRST_COL_WIDTH + COL_WIDTH * COL_COUNT, ROW_HEIGHT, QPen(), QBrush()
        )

        for x in range(COL_COUNT):
            colnum = 100 - x if x < 100 else x - 99
            rect = self.scene.addRect(
                0,
                0,
                COL_WIDTH,
                ROW_HEIGHT,
                QPen(Qt.NoPen),
                QBrush(Qt.darkYellow if x < 100 else Qt.darkGreen),
            )
            rect.setPos(FIRST_COL_WIDTH + COL_WIDTH * x, 0)
            if colnum % 10 == 0:
                text = QGraphicsSimpleTextItem(f"{colnum}", rect)
                text.setPos((COL_WIDTH - text.boundingRect().width()) / 2, 1)
                text.setBrush(QBrush(Qt.white))
            rect.setParentItem(self.firstRow)

        self.firstColumn = self.scene.addRect(
            0, 0, FIRST_COL_WIDTH, ROW_HEIGHT * ROW_COUNT, QPen(), QBrush(Qt.white)
        )

        for y in range(ROW_COUNT):
            rect = self.scene.addRect(
                0,
                0,
                FIRST_COL_WIDTH,
                ROW_HEIGHT,
                QPen(Qt.black),
                QBrush(QColor.fromHsv(random.randrange(360), 200, 200)),
            )
            text = QGraphicsSimpleTextItem(f"Row {y} {ARROWS[y % 2]}", rect)
            rect.setPos(0, ROW_HEIGHT * (y + 1))
            text.setPos(10, 2)
            rect.setParentItem(self.firstColumn)
        self.scene.setSceneRect(
            0, 0, FIRST_COL_WIDTH + COL_WIDTH * COL_COUNT, ROW_HEIGHT * ROW_COUNT
        )

        self.cornerMask = self.scene.addRect(
            0, 0, FIRST_COL_WIDTH, ROW_HEIGHT, QPen(Qt.black), QBrush(Qt.white)
        )


App = QApplication(sys.argv)
window = Window()
sys.exit(App.exec())
