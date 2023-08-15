import pytest, logging
from PyQt5.QtWidgets import QWidget
from pydantic import ValidationError

from optiblocks.tree.parameters import FloatFieldParameter, FloatParameter, IntegerFieldParameter, \
    ListFieldParameter, ModelGroupParameter
from optiblocks.tree.tree import ModelContainer
from sample_model import AC, make_dummy_model
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

    rp = stree.rp
    root = rp.children()[0]

    car1 = root.child(*['cars', 'cars[0]'])
    car_price_1 = root.child(*['cars', 'cars[0]', 'price'])
    assert isinstance(car_price_1, FloatFieldParameter)
    print(car_price_1, type(car_price_1))

    ival = model.cars[0].price
    with pytest.raises(ValueError):
        car_price_1.setValue('invalid')
    assert model.cars[0].price == ival == car_price_1.opts['value'] == car_price_1.value()

    #
    v1 = car_price_1.find_validator()
    assert v1 == car1

    c1 = car_price_1.find_change_handler()
    assert c1 == car1

    with pytest.raises(ValueError):
        car_price_1.handle_change(car_price_1, 'value', 20)

    with pytest.raises(ValidationError):
        car_price_1.handle_self_change(420.2)
    assert car_price_1.value() == ival

    car_price_1.handle_self_change(1420.2)
    assert model.cars[0].price == 1420.2
    assert car_price_1.opts['value'] == 3000

    # TODO: implement update
    #assert car_price_1.value() == 1420.2
    car_price_1.opts['value'] = 1420.2
    assert car_price_1.value() == 1420.2

    # car_price_1.setValue(420)
    # assert model.cars[0].price == car_price_1.opts['value'] == 420
    pitems = list(car_price_1.items)
    assert len(pitems) == 1

    pi = pitems[0]
    pi.widget.lineEdit().setText(str(420.0))
    assert model.cars[0].price == car_price_1.opts['value'] == 420


def test_list_field(qtbot, model):
    win = QWidget()
    stree = ModelContainer(win)
    stree.set_model(model)
    win.show()
    qtbot.addWidget(win)

    rp = stree.rp
    root = rp.children()[0]

    car1 = root.child(*['cars', 'cars[0]'])
    keycodes = root.child(*['cars', 'cars[0]', 'keycodes'])
    keycodes1 = root.child(*['cars', 'cars[0]', 'keycodes', 'keycodes[0]'])

    assert isinstance(keycodes, ListFieldParameter)
    assert isinstance(keycodes1, FloatParameter)

    v1 = keycodes1.find_validator()
    assert v1 == car1

    c1 = keycodes1.find_change_handler()
    assert c1 == car1


def test_tree_read(qtbot, model):
    win = QWidget()
    stree = ModelContainer(win)
    stree.set_model(model)
    win.show()
    qtbot.addWidget(win)

    rp = stree.rp
    root = rp.children()[0]

    car1 = root.child(*['cars', 'cars[0]'])
    assert isinstance(car1, ModelGroupParameter)

    car_price_1 = root.child(*['cars', 'cars[0]', 'price'])
    assert isinstance(car_price_1, FloatFieldParameter)
    assert car1.get_model_value(car_price_1) == 3000.1

    vin = root.child(*['cars', 'cars[0]', 'vin'])
    assert isinstance(vin, IntegerFieldParameter)
    assert car1.get_model_value(vin) == 12345

    e0 = root.child(*['cars', 'cars[0]', 'extras', 'extras[0]'])
    assert isinstance(e0, ModelGroupParameter)
    assert e0.basemodel == model.cars[0].extras[0]
    assert isinstance(e0.basemodel, AC)
    assert root.child(*['cars', 'cars[0]', 'extras']).get_model_value(e0) == AC()

    k = root.child(*['cars', 'cars[0]', 'keycodes'])
    k0 = root.child(*['cars', 'cars[0]', 'keycodes', 'keycodes[0]'])
    assert isinstance(k0, FloatParameter)
    assert k.get_model_value(k0) == 1.0
    assert k.parent().get_model_value(k0.parent()) == [1.0, 2.0, 3.0]


def test_tree_change_value(qtbot):
    win = make_window()
    win.show()
    qtbot.addWidget(win)
