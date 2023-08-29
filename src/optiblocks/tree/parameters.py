import builtins
import copy
import logging
from abc import ABC, abstractmethod
from typing import Type

import pyqtgraph.Qt
from PyQt5 import QtCore
from pydantic import BaseModel, validate_model
from pydantic.fields import FieldInfo
from pydantic.types import ConstrainedNumberMeta
from pyqtgraph.parametertree import Parameter

from .parameteritems import BooleanParameterItem, NumericParameterItem, \
    PydanticGroupParameterItem, SimplePydanticParameterItem, \
    SliderParameterItem, StringParameterItem

translate = QtCore.QCoreApplication.translate

logger = logging.getLogger(__name__)


class PydanticGroupParameter(Parameter):
    """
    Group parameters are used mainly as a generic parent item that holds (and groups!) a set
    of child parameters.

    It also provides a simple mechanism for displaying a button or combo
    that can be used to add new parameters to the group. To enable this, the group
    must be initialized with the 'addText' option (the text will be displayed on
    a button which, when clicked, will cause addNew() to be called). If the 'addList'
    option is specified as well, then a dropdown-list of addable items will be displayed
    instead of a button.
    """
    sigAddNew = pyqtgraph.Qt.QtCore.Signal(object, object)  # self, type

    def __init__(self, **opts):
        Parameter.__init__(self, **opts)
        self.value = opts.get('value', '')
        self.desc = opts.get('desc', "<no description>")
        self.typehint = opts.get('typehint', '')
        self.field: FieldInfo = opts.get('field', None)

    def addNew(self, typ=None):
        """
        This method is called when the user has requested to add a new item to the group.
        By default, it emits ``sigAddNew(self, typ)``.
        """
        self.sigAddNew.emit(self, typ)

    def setAddList(self, vals):
        """Change the list of options available for the user to add to the group."""
        self.setOpts(addList=vals)

    def makeTreeItem(self, depth):
        return PydanticGroupParameterItem(self, depth, self.value, self.desc, self.typehint)


def validate_pydantic_model(modelt:Type[BaseModel], new_dict: dict):
    """
    Validates a dictionary against the model class
    See https://github.com/pydantic/pydantic/issues/1864

    Parameters
    ----------
    modelt: Type
        Base model class
    new_dict: dict
        Dictionary of options
    """

    values, fields_set, validation_error = validate_model(
            modelt, new_dict
    )
    if validation_error:
        raise validation_error


class ModelGroupParameter(PydanticGroupParameter):
    """
    Represents a group backed by BaseModel, and will handle all writes for it.
    """
    itemClass = PydanticGroupParameterItem

    def __init__(self, basemodel: BaseModel, **opts):
        super().__init__(**opts)
        self.value = opts.get('value', '')
        self.desc = opts.get('desc', "<no description>")
        self.typehint = f'Model[{basemodel.__class__.__name__}]'
        self.basemodel = basemodel
        logger.debug(f'Made ModelGroupParameter {self.typehint=}')

    def __str__(self):
        return (f'{self.__class__.__name__} for model ({self.basemodel.__class__.__name__}) with'
                f' ({self.desc})'
                f' ({self.typehint})')

    def makeTreeItem(self, depth):
        logger.debug(f'Making Item for ModelGroupParameter {self.typehint=}')
        return PydanticGroupParameterItem(self, depth, self.value, self.desc, self.typehint)

    def handle_change_fun(self, param, child, fun):
        """ Apply change to a field in-place """
        assert isinstance(child, (FieldParameter, PydanticGroupParameter))
        logger.debug(f'Model group ({self}) change from ({child.name()})')
        try:
            field_name = child.name()
            field_value = getattr(self.basemodel, field_name)
            logger.debug(f'Old value ({field_value})')
            new_value = fun(field_value)

            d = self.basemodel.dict()
            d[field_name] = new_value
            logger.debug(f'New value ({new_value})')
            validate_pydantic_model(self.basemodel.__class__, d)

            setattr(self.basemodel, field_name, new_value)
            logger.debug(f'Set OK')
        except Exception as ex:
            logger.debug(f'Set FAIL')
            raise ex

    def get_model_value(self, child):
        field_name = child.name()
        field_value = getattr(self.basemodel, field_name)
        return field_value

    def propose_change(self, param, child, fun):
        assert isinstance(child, (FieldParameter, PydanticGroupParameter))
        logger.debug(f'Model group ({self}) proposal from ({child.name()})')
        try:
            field_name = child.name()
            field_value = getattr(self.basemodel, field_name)
            new_value = copy.deepcopy(field_value)
            new_value = fun(new_value, do_copy=True)

            d = self.basemodel.dict()
            d[field_name] = new_value
            validate_pydantic_model(self.basemodel.__class__, d)

            # We won't actually use the new model to preserve non-field values
            logger.debug(f'Validation OK')
            # TODO: Propagate to parent models
            return True
        except Exception as ex:
            logger.debug(f'Proposal FAIL')
            logger.debug(f'Exception {ex=}')
            raise ex

    def get_change_fun(self, child, data):
        pass

    def find_self_change_handler(self):
        """ Model change will be handled by parent """
        return self.parent().find_change_handler()

    def find_change_handler(self):
        """ Model is responsible for validation """
        return self

    def find_validator(self):
        """ Model is responsible for validation """
        return self


class RegularPydanticGroupParameter(PydanticGroupParameter):
    def find_change_handler(self):
        return self

    def find_validator(self):
        return self.parent().find_validator()


class ListFieldParameter(RegularPydanticGroupParameter):
    # def handle_change(self, param, child, fun):
    #     assert child in self.children()
    #     logger.debug(f'({self.name()}) handling change ({child.name()})')
    #     idx = self.children().index(child)
    #     obj = self.parent().get_model_value(self)
    #     obj[idx] = fun(obj[idx])

    def handle_change_fun(self, param, child, fun):
        logger.debug(f'{self.__class__.__name__} ({self.name()}) change from '
                     f'({child.name()}), fwd to ({self.parent()})')
        # obj = self.parent().get_model_value(self)
        idx = self.children().index(child)

        def change_fun(x):
            x[idx] = fun(x[idx])
            return x

        self.parent().handle_change_fun(param, self, change_fun)

    def get_model_value(self, child):
        idx = self.children().index(child)
        obj = self.parent().get_model_value(self)
        return obj[idx]

    def propose_change(self, param, child, fun):
        logger.debug(f'{self.__class__.__name__} ({self.name()}) proposal from ({child.name()}), '
                     f'fwd to ({self.parent()})')
        idx = self.children().index(child)

        def change_fun(x, do_copy):
            if do_copy:
                x = copy.copy(x)
            x[idx] = fun(x[idx])
            return x

        return self.parent().propose_change(param, self, change_fun)


class DictFieldParameter(RegularPydanticGroupParameter):
    """ DictField - only handles edits to its key-value pairs """

    def handle_change_fun(self, param, child, fun):
        logger.debug(f'Dict field ({self.name()}) forwarding proxy from ({child.name()})')
        # key = param.name()
        # model = self.parent().basemodel
        # field_value = getattr(self.basemodel, key)
        # new_value = copy.deepcopy(field_value)
        # model[key] = fun(model[key])
        # keys = param.field
        # key = param.name()
        idx = self.children().index(child)

        def change_fun(x):
            keys = list(x.keys())
            key = keys[idx]
            x[key] = fun(x[key])
            return x

        self.parent().handle_change_fun(param, self, change_fun)

    def get_model_value(self, child):
        obj = self.parent().get_model_value(self)
        keys = list(obj.keys())
        idx = self.children().index(child)
        key = keys[idx]
        return obj[key]

    def propose_change(self, param, child, fun):
        assert child in self.children()
        logger.debug(f'Dict field ({self.name()}) proposal from ({child.name()})')
        idx = self.children().index(child)

        def change_fun(x, do_copy):
            if do_copy:
                x = copy.copy(x)
            keys = list(x.keys())
            key = keys[idx]
            x[key] = fun(x[key])
            return x

        return self.parent().propose_change(param, self, change_fun)

    def get_change_fun(self, child, data):
        assert child in self.children()
        key = child.name()

        def change_fun(x):
            x[key] = data

        return change_fun


###############

class FieldParameter(Parameter):
    """ Represents a pydantic field parameter that is a lead (will not contain children) """
    _type = None

    def __init__(self, **opts):
        assert self._type is not None
        super().__init__(**opts, type=self._type)
        self.desc = opts.get('desc', "<no field description>")
        self.typehint = opts.get('typehint', '')
        self.field: FieldInfo = opts.get('field', None)

    @abstractmethod
    def makeTreeItem(self, depth):
        pass

    def handle_self_change(self, data):
        logger.debug(f'Field ({self.name()}) self-change ({data}) fwd to'
                     f' ({self.parent()})')

        def change_fun(x):
            return data

        self.parent().handle_change_fun(self, self, change_fun)

    def propose_self_change(self, data):
        logger.debug(f'Field ({self.name()}) proposed self-change ({data})')

        def change_fun(x, do_copy):
            return data

        return self.parent().propose_change(self, self, change_fun)

    def _interpretValue(self, v):
        typ = self.opts['type'] or 'str'
        logger.debug(f'Interpreting {v} as {typ}')

        def _missing_interp(v):
            return v

        interpreter = getattr(builtins, typ, _missing_interp)
        return interpreter(v)

    def find_change_handler(self):
        return self.parent().find_change_handler()

    def find_validator(self):
        return self.parent().find_validator()

    def __str__(self):
        return (f'{self.__class__.__name__} with {self.desc=} {self.typehint=} '
                f'{self.field=}')


class FloatFieldParameter(FieldParameter):
    _type = 'float'

    def makeTreeItem(self, depth):
        return NumericParameterItem(self, depth, self.desc, self.typehint)

    def _interpretValue(self, v):
        return float(v)


class SliderFloatFieldParameter(FloatFieldParameter):
    def makeTreeItem(self, depth):
        return SliderParameterItem(self, depth, self.desc, self.typehint)


class IntegerFieldParameter(FieldParameter):
    _type = 'int'

    def makeTreeItem(self, depth):
        return NumericParameterItem(self, depth, self.desc, self.typehint)

    def _interpretValue(self, v):
        return int(v)


class BooleanFieldParameter(FieldParameter):
    _type = 'bool'

    def makeTreeItem(self, depth):
        return BooleanParameterItem(self, depth, self.desc, self.typehint)

    def _interpretValue(self, v):
        return bool(v)


class StringFieldParameter(FieldParameter):
    _type = 'str'

    def makeTreeItem(self, depth):
        return SimplePydanticParameterItem(self, depth, self.desc, self.typehint)


##############
class RegularGroupParameter(PydanticGroupParameter):
    def __init__(self, **opts):
        super().__init__(**opts)
        self.desc = opts.get('desc', "")

    def find_change_handler(self):
        return self

    def find_validator(self):
        return self.parent().find_validator()


class ListParameter(RegularGroupParameter):
    def handle_change(self, param, child, fun):
        assert child in self.children()
        logger.debug(f'({self.name()}) fwd proxy from ({child.name()})')
        idx = self.children().index(child)
        obj = self.parent().get_model_value(self)
        obj[idx] = fun(obj[idx])

    def get_model_value(self, child):
        obj = self.parent().get_model_value()
        idx = self.children().index(child)
        return obj[idx]

    def propose_change(self, param, child, fun):
        logger.debug(f'List parameter ({self.name()}) fwd from ({child.name()})')
        idx = self.children().index(child)

        def change_fun(x, do_copy):
            if do_copy:
                x = copy.copy(x)
            x[idx] = fun(x[idx])
            return x

        return self.parent().propose_change(param, self, change_fun)


class DictParameter(RegularGroupParameter):
    def handle_change(self, param, child, fun):
        assert child in self.children()
        logger.debug(f'Dict ({self.name()}) fwd proxy from ({child.name()})')
        key = param.name()
        obj = self.parent().get_model_value(self)
        obj[key] = fun(obj[key])

    def get_model_value(self, child):
        obj = self.parent().get_model_value()
        key = child.name()
        return obj[key]

    def propose_change(self, param, child, fun):
        assert child in self.children()
        logger.debug(f'Dict ({self.name()}) fwd proxy from ({child.name()})')
        key = param.name()

        def change_fun(x, do_copy):
            if do_copy:
                x = copy.copy(x)
            x[key] = fun(x[key])
            return x

        return self.parent().propose_change(param, self, change_fun)


#####################

class PrimitiveParameter(Parameter):
    _type = None

    def __init__(self, **opts):
        assert isinstance(opts['name'], str), f'{opts}'
        assert self._type is not None
        super().__init__(**opts, type=self._type)
        self.desc = opts.get('desc', "")
        self.typehint = opts.get('typehint', '')

    def handle_self_change(self, data):
        logger.debug(f'{self.__class__.__name__} ({self.name()}) self-change ({data}), fwd to'
                     f' ({self.parent()})')

        def change_fun(x):
            return data

        # self.parent().handle_change(self, self, change_fun)
        self.parent().handle_change_fun(self, self, change_fun)

    def propose_self_change(self, data):
        logger.debug(f'{self.__class__.__name__} ({self.name()}) proposed self-change {data}')

        def change_fun(x):
            return data

        return self.parent().propose_change(self, self, change_fun)

    def _interpretValue(self, v):
        interpreter = getattr(builtins, self._type)
        return interpreter(v)

    def find_change_handler(self):
        return self.parent().find_change_handler()

    def find_validator(self):
        return self.parent().find_validator()


class FloatParameter(PrimitiveParameter):
    _type = 'float'

    def makeTreeItem(self, depth):
        return NumericParameterItem(self, depth, self.desc, self.typehint)


class StringParameter(PrimitiveParameter):
    _type = 'str'

    def makeTreeItem(self, depth):
        return StringParameterItem(self, depth, self.desc, self.typehint)


#########################

class FieldHandler(ABC):

    def __call__(self, *args, **kwargs):
        return self.process(*args, **kwargs)

    @abstractmethod
    def process(self, field, value, parent):
        pass


class StringHandler(FieldHandler):
    def process(self, field, value, parent):
        name = field.alias or field.name
        desc = field.field_info.description
        title = f'{name}'
        typehint = f'Field[{type(value).__name__}]'
        return StringFieldParameter(name=name, field=field, parent=parent,
                                    value=value, title=title,
                                    desc=desc, typehint=typehint)


class FloatHandler(FieldHandler):

    def process(self, field, value, parent):
        name = field.alias or field.name
        desc = field.field_info.description
        title = f'{name}'
        an = field.annotation

        lb = '>= -inf'
        ub = '<= +inf'
        if isinstance(an, ConstrainedNumberMeta):
            if an.ge is not None:
                lb = f'>= {an.ge}'
            elif an.gt is not None:
                lb = f'>= {an.gt}'

            if an.le is not None:
                ub = f'<= {an.le}'
            elif an.lt is not None:
                ub = f'< {an.lt}'

        bounds = f'[{lb},{ub}]'
        # (allowed: {field.annotation})
        typehint = f'Field[{type(value).__name__}] {bounds}'
        logger.debug(f'FloatHandler {name=} {value=} {title=} {typehint=}')
        return FloatFieldParameter(name=name, field=field, parent=parent,
                                   value=value, title=title,
                                   desc=desc, typehint=typehint)


class BooleanHandler(FieldHandler):
    def process(self, field, value, parent):
        name = field.alias or field.name
        desc = field.field_info.description
        title = f'{name}'
        an = field.annotation
        typehint = f'Field[{type(value).__name__}]'
        return BooleanFieldParameter(name=name, field=field, parent=parent,
                                     value=value, title=title,
                                     desc=desc, typehint=typehint)


class IntHandler(FloatHandler):
    def process(self, field, value, parent):
        name = field.alias or field.name
        desc = field.field_info.description
        title = f'{name}'
        an = field.annotation

        lb = '>= -inf'
        ub = '<= +inf'
        if isinstance(an, ConstrainedNumberMeta):
            if an.ge is not None:
                lb = f'>= {an.ge}'
            elif an.gt is not None:
                lb = f'>= {an.gt}'

            if an.le is not None:
                ub = f'<= {an.le}'
            elif an.lt is not None:
                ub = f'< {an.lt}'

        bounds = f'[{lb},{ub}]'
        # (allowed: {field.annotation})
        typehint = f'Field[{type(value).__name__}] {bounds}'
        logger.debug(f'IntegerHandler {name=} {value=} {title=} {typehint=}')
        return IntegerFieldParameter(name=name, field=field, parent=parent,
                                     value=value, title=title,
                                     desc=desc, typehint=typehint)


####################

class PrimitiveHandler(ABC):

    def __call__(self, *args, **kwargs):
        return self.process(*args, **kwargs)

    @abstractmethod
    def process(self, name, value, parent):
        pass


class PrimitiveListHandler(PrimitiveHandler):
    def process(self, name, value, parent=None):
        logger.debug(f'PrimitiveListHandler {name=} {value=} {parent=}')
        return ListParameter(name=name, parent=parent, value=value)


class PrimitiveFloatHandler(PrimitiveHandler):

    def process(self, name, value, parent=None):
        logger.debug(f'PrimitiveFloatHandler {name=} {value=} {parent=}')
        return FloatParameter(name=name, parent=parent, value=value)
