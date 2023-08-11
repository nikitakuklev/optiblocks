import json
import logging

import pyqtgraph as pg
from PyQt5 import QtWidgets
from PyQt5.QtGui import QScreen

from optiblocks.tree.tree import ModelContainer
from sample_model import make_dummy_model


def make_window():
    logging.basicConfig(level=logging.DEBUG)

    win = QtWidgets.QWidget()
    win.setFixedSize(1280, 800)
    win.stree = stree = ModelContainer(win)
    model = make_dummy_model()
    stree.set_model(model)

    monitors = QScreen.virtualSiblings(win.screen())
    monitor = monitors[1].availableGeometry()
    win.move(monitor.left(), monitor.top())

    layout = QtWidgets.QHBoxLayout()
    win.setLayout(layout)

    l1 = QtWidgets.QVBoxLayout()
    layout.addLayout(l1, 4)
    l1.addWidget(stree.tree, 4)
    bar = QtWidgets.QWidget()
    bar.setFixedHeight(100)
    l1.addWidget(bar)

    tp = QtWidgets.QTextEdit()
    tp.setFixedWidth(150)
    layout.addWidget(tp)

    tp2 = QtWidgets.QTextEdit()
    layout.addWidget(tp2)
    tp2.setFixedWidth(150)

    def update():
        tp.setText(json.dumps(model.dict(), indent=2, sort_keys=False))
        tp2.setText(model.schema_json(indent=2))

    def clear_style():
        stree.tree.setStyleSheet("")

    def model_update_cb(mc):
        update()

    stree.add_callback(model_update_cb)

    update()

    l2 = QtWidgets.QGridLayout()
    bar.setLayout(l2)

    def get_b(s):
        b = QtWidgets.QPushButton()
        b.setAutoDefault(False)
        # b.setFixedWidth(20)
        b.setFixedHeight(20)
        b.setText(s)
        return b

    b = get_b("Refresh")
    b.clicked.connect(update)
    l2.addWidget(b, 0, 1)

    b = get_b("Clear style")
    b.clicked.connect(clear_style)
    l2.addWidget(b, 0, 2)

    b = get_b("Debug style")
    b.clicked.connect(stree.tree.set_debug_style)
    l2.addWidget(b, 0, 3)

    tp3 = QtWidgets.QTextEdit()
    l2.addWidget(tp3, 0, 0)

    def sel_cb(sel):
        info = sel[0]
        tp3.setText(f'Current selection: {info}\nCurrent parameter: {info.param}')
        tp3.append(f'Parent parameter: {info.param.parent()}')


    stree.tree.selection_callbacks = [sel_cb]
    return win


if __name__ == '__main__':
    app = pg.mkQApp("Pydantic Tree Debug")
    win = make_window()
    win.show()
    pg.exec()
    # timer = QTimer()
    # timer.timeout.connect(update)
    # timer.start(1000)
