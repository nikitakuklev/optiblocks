import pytest, logging
from PyQt5.QtWidgets import QWidget

from optiblocks.tree.parameters import FloatFieldParameter
from optiblocks.tree.tree import ModelContainer
from sample_model import make_dummy_model
from tree_test_gui import make_window


@pytest.fixture
def model():
    logging.basicConfig(level=logging.DEBUG)
    model = make_dummy_model()
    return model


def test_model_write(qtbot, model):
    win = QWidget()
    stree = ModelContainer(win)
    stree.set_model(model)
    win.show()
    qtbot.addWidget(win)

    t = stree.tree
    rp = stree.rp
    root = rp.children()[0]

    car_price_1 = root.child(*['cars', 'cars[0]', 'price'])
    print(car_price_1, type(car_price_1))

    assert isinstance(car_price_1, FloatFieldParameter)

    ival = model.cars[0].price

    with pytest.raises(ValueError):
        car_price_1.setValue('invalid')
    assert model.cars[0].price == ival == car_price_1.opts['value']

    #car_price_1.setValue(420)
    #assert model.cars[0].price == car_price_1.opts['value'] == 420
    pitems = list(car_price_1.items)
    assert len(pitems) == 1

    pi = pitems[0]
    pi.widget.lineEdit().setText(str(420.0))
    assert model.cars[0].price == car_price_1.opts['value'] == 420



def test_tree_change_value(qtbot):
    win = make_window()
    win.show()
    qtbot.addWidget(win)
