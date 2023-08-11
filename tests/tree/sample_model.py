import pydantic
from pydantic import BaseModel, Field
from pydantic import conint
from typing import Dict, List, TypeVar

BoundFloat = TypeVar('BoundFloat', bound=float)


class Door(BaseModel):
    side: str = 'left'


class Engine(BaseModel):
    hp: float = 100.0


class Extra(BaseModel):
    name: str


class AC(Extra):
    name = 'air conditioner'


class CruiseControl(Extra):
    name = 'cruise control'


class Car(BaseModel):
    brand: str = Field('Honda', alias='bla', description='the brand of the car')
    keycodes: List[float] = Field([1.0, 2.0, 3.0], description='this list has secret key floats')
    available: bool = True
    properties: Dict[str, float] = {'seats': 1.0, 'sunroof': 1.0}
    varproperties: Dict[str, List[float]] = {'volume': [400,450], 'height': [1.0,1.2]}
    extras: List[Extra] = Field([], description='List of the extra options in the car')
    max_speed: BoundFloat = Field(0.0)
    engine: Engine = Engine()
    price: conint(gt=1000.0, lt=10000) = Field(3000.1, description='this field reflects the price '
                                                                   'of the car in US dollars')
    mpg: float = Field(3000.0, description='EPA mileage')
    model: str = Field('Civic', description='test')


class Vehicles(BaseModel):
    cars: list[Car] = []


def make_dummy_model():
    C = Car(extras=[AC(), CruiseControl()], max_speed=66.0)
    C2 = Car(brand='Ford', model='Focus', keycodes=[1.0, 2.0], max_speed=33, available=False)
    T = Vehicles(cars=[C, C2])
    return T
