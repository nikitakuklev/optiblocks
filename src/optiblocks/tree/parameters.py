import builtins
import copy
import logging
from abc import ABC, abstractmethod

import pyqtgraph.Qt
from PyQt5 import QtCore
from pydantic import BaseModel, validate_model
from pydantic.fields import FieldInfo
from pydantic.types import ConstrainedNumberMeta
from pydantic.utils import deep_update
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


def check_and_set_options(model: BaseModel, new_dict: dict):
    """
    Validates a dictionary against the model, and if so, sets new values
    Parameters
    ----------
    model: BaseModel
        The object to change
    new_dict: dict
        Dictionary of options
    See https://github.com/pydantic/pydantic/issues/1864
    """

    values, fields_set, validation_error = validate_model(
            model.__class__, new_dict
    )
    if validation_error:
        raise validation_error
    try:
        object.__setattr__(model, "__dict__", values)
    except TypeError as e:
        raise TypeError(
                "Model values must be a dict; you may not have returned "
                + "a dictionary from a root validator"
        ) from e
    object.__setattr__(model, "__fields_set__", fields_set)


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
        return (f'{self.__class__.__name__} for model {self.basemodel.__class__} with {self.desc=}'
                f' {self.typehint=}')

    def makeTreeItem(self, depth):
        logger.debug(f'Making Item for ModelGroupParameter {self.typehint=}')
        return PydanticGroupParameterItem(self, depth, self.value, self.desc, self.typehint)

    # def handle_change(self, param, change, data):
    #     logger.debug(f'Model group ({self}) received change data {data}')
    #     changes = {param.field.name: data}
    #     try:
    #         old_data = self.basemodel.dict()
    #         updated_dict = deep_update(old_data, changes)
    #         check_and_set_options(self.basemodel, updated_dict)
    #         # validation did not raise exceptions, proceed
    #         setattr(self.basemodel, param.field.name, data)
    #         logger.debug(f'Set {self.basemodel=} OK')
    #     except:
    #         logger.debug(f'Set {self.basemodel=} with {changes=} FAIL')
    #         logger.debug()

    def handle_change_fun(self, param, child, fun):
        assert isinstance(child, (FieldParameter, PydanticGroupParameter))
        logger.debug(f'Model group ({self}) received change function {fun} from {child.name()}')
        try:
            field_name = child.name()
            field_value = getattr(self.basemodel, field_name)
            new_value = copy.deepcopy(field_value)
            logger.debug(f'Old value ({new_value})')
            new_value = fun(new_value)

            d = self.basemodel.dict()
            d[field_name] = new_value
            logger.debug(f'New value ({new_value})')
            check_and_set_options(self.basemodel, d)

            # We won't actually use the new model to preserve non-field values
            setattr(self.basemodel, field_name, new_value)
            logger.debug(f'Set OK')
        except Exception as ex:
            logger.debug(f'Set FAIL')
            raise ex

    def propose_change(self, param, child, fun):
        assert isinstance(child, (FieldParameter, PydanticGroupParameter))
        logger.debug(f'Model group ({self}) received change function {fun} from {child.name()}')
        try:
            field_name = child.name()
            field_value = getattr(self.basemodel, field_name)
            new_value = copy.deepcopy(field_value)
            new_value = fun(new_value)

            d = self.basemodel.dict()
            d[field_name] = new_value
            check_and_set_options(self.basemodel, d)

            # We won't actually use the new model to preserve non-field values
            logger.debug(f'Validation {self.basemodel=} OK')
            # TODO: Propagate to parent models
            return True
        except Exception as ex:
            logger.debug(f'Set FAIL')
            logger.debug(f'Exception {ex=}')
            return ex

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


class FieldParameter(Parameter):
    """ Represents a pydantic field parameter """

    def __init__(self, **opts):
        super().__init__(**opts)
        self.desc = opts.get('desc', "<no field description>")
        self.typehint = opts.get('typehint', '')
        self.field: FieldInfo = opts.get('field', None)

    @abstractmethod
    def makeTreeItem(self, depth):
        pass

    def handle_change(self, param, change, data):
        logger.debug(f'Parameter ({self.name()}) received change ({data}), fwd to'
                     f' ({self.parent()})')

        def change_fun(x):
            return data

        self.parent().handle_change_fun(param, self, change_fun)

    def handle_self_change(self, data):
        logger.debug(f'Field parameter ({self.name()}) received ({data}), fwd to'
                     f' ({self.parent()})')

        def change_fun(x):
            return data

        self.parent().handle_change_fun(self, self, change_fun)

    def propose_change(self, param, child, fun):
        raise Exception

    def propose_self_change(self, data):
        logger.debug(f'Field ({self.name()}) self-change {data}')

        def change_fun(x):
            return data

        self.parent().propose_change(self, self, change_fun)

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


class RegularPydanticGroupParameter(PydanticGroupParameter):
    pass


class ListFieldParameter(RegularPydanticGroupParameter):
    def handle_change(self, param, change, data):
        if param not in self.children():
            raise Exception
        idx = self.children().index(param)
        logger.debug(f'List field parameter ({self.name()}) creating change fun for '
                     f'({param.name()}) at index ({idx}), fwd to ({self.parent()})')
        self.field[idx] = data

    def handle_change_fun(self, param, child, fun):
        logger.debug(f'List field ({self.name()}) forwarding proxy from ({child.name()})')
        # key = param.name()
        # model = self.parent().basemodel
        # field_value = getattr(self.basemodel, key)
        # new_value = copy.deepcopy(field_value)
        # model[key] = fun(model[key])
        idx = self.children().index(child)

        def change_fun(x):
            x[idx] = fun(x[idx])
            return x

        self.parent().handle_change_fun(param, self, change_fun)

    def propose_change(self, param, child, fun):
        logger.debug(f'List field parameter ({self.name()}) forwarding proxy from ({child.name()})')
        idx = self.children().index(child)

        def change_fun(x):
            x[idx] = fun(x[idx])
            return x

        self.parent().propose_change(param, self, change_fun)

    def get_change_fun(self, child, data):
        idx = self.children().index(child)

        def change_fun(x):
            x[idx] = data

        return change_fun

    def find_change_handler(self):
        return self.parent().find_change_handler()

    def find_validator(self):
        return self.parent().find_validator()


class DictFieldParameter(PydanticGroupParameter):
    # def handle_change(self, param, change, data):
    #     if param not in self.children():
    #         raise Exception
    #     key = param.name()
    #     logger.debug(f'Dict field parameter ({self.name()}) creating change fun for '
    #                  f'({param.name()}) at key ({key}), fwd to ({self.parent()})')
    #
    #     self.field[key] = data
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
            return fun(x[key])

        self.parent().handle_change_fun(param, self, change_fun)

    def propose_change(self, param, child, fun):
        logger.debug(f'Dict field ({self.name()}) forwarding proxy from ({child.name()})')
        key = param.name()

        def change_fun(x):
            return fun(x[key])

        return self.parent().propose_change(param, self, change_fun)

    def get_change_fun(self, child, data):
        assert child in self.children()
        key = child.name()

        def change_fun(x):
            x[key] = data

        return change_fun

    def find_change_handler(self):
        return self

    def find_validator(self):
        return self.parent().find_validator()


class FloatFieldParameter(FieldParameter):
    def __init__(self, **opts):
        super().__init__(**opts, type='float')

    def makeTreeItem(self, depth):
        return NumericParameterItem(self, depth, self.desc, self.typehint)

    def _interpretValue(self, v):
        return float(v)


class SliderFloatFieldParameter(FloatFieldParameter):
    def makeTreeItem(self, depth):
        return SliderParameterItem(self, depth, self.desc, self.typehint)


class IntegerFieldParameter(FieldParameter):
    def __init__(self, **opts):
        super().__init__(**opts, type='int')

    def makeTreeItem(self, depth):
        return NumericParameterItem(self, depth, self.desc, self.typehint)

    def _interpretValue(self, v):
        return int(v)


class BooleanFieldParameter(FieldParameter):
    def __init__(self, **opts):
        super().__init__(**opts, type='bool')

    def makeTreeItem(self, depth):
        return BooleanParameterItem(self, depth, self.desc, self.typehint)

    def _interpretValue(self, v):
        return bool(v)


class StringFieldParameter(FieldParameter):
    def __init__(self, **opts):
        super().__init__(**opts, type='str')

    def makeTreeItem(self, depth):
        return SimplePydanticParameterItem(self, depth, self.desc, self.typehint)


##############


class PrimitiveParameter(Parameter):
    def __init__(self, **opts):
        assert isinstance(opts['name'], str), f'{opts}'
        super().__init__(**opts)
        self.desc = opts.get('desc', "")
        self.typehint = opts.get('typehint', '')

    def handle_self_change(self, data):
        logger.debug(f'Primitive parameter ({self.name()}) received ({data}), fwd to'
                     f' ({self.parent()})')

        def change_fun(x):
            return data

        self.parent().handle_change_fun(self, self, change_fun)

    def propose_self_change(self, data):
        logger.debug(f'Primitive ({self.name()}) self-change {data}')

        def change_fun(x):
            return data

        self.parent().propose_change(self, self, change_fun)

    def propose_change(self, param, change, data):
        raise Exception


class ListParameter(PydanticGroupParameter):
    def __init__(self, **opts):
        super().__init__(**opts)
        self.desc = opts.get('desc', "")

    # def handle_change(self, param, change, data):
    #     logger.debug(f'List parameter ({self.name()}) creating change fun for ({param.name()})')
    #     if param not in self.children():
    #         raise Exception
    #     idx = self.children().index(param)
    #
    #     def change_fun(x):
    #         x[idx] = data
    #
    #     self.parent().handle_change(param, self, change_fun)
    def propose_change(self, param, child, fun):
        logger.debug(f'List parameter ({self.name()}) fwd from ({child.name()})')
        idx = self.children().index(child)

        def change_fun(x):
            x[idx] = fun(x[idx])
            return x

        self.parent().propose_change(param, self, change_fun)

    def handle_change_fun(self, param, child, fun):
        logger.debug(f'List parameter ({self.name()}) forwarding proxy from ({child.name()})')
        idx = self.children().index(child)

        def change_fun(x):
            x[idx] = fun(x[idx])
            return x

        self.parent().handle_change_fun(param, self, change_fun)

    def find_change_handler(self):
        return self


class DictParameter(PydanticGroupParameter):
    def handle_change(self, param, change, data):
        if param not in self.children():
            raise Exception
        key = param.name()
        logger.debug(f'Dict parameter ({self.name()}) creating change fun for '
                     f'({param.name()}) at key ({key}), fwd to ({self.parent()})')

        self.field[key] = data

    def propose_change(self, param, child, fun):
        logger.debug(f'Dict ({self.name()}) fwd proxy from ({child.name()})')
        key = param.name()

        def change_fun(x):
            return fun(x[key])

        return self.parent().propose_change(param, self, change_fun)

    def get_change_fun(self, child, data):
        assert child in self.children()
        key = child.name()

        def change_fun(x):
            x[key] = data

        return change_fun

    def find_change_handler(self):
        return self

    def find_validator(self):
        return self.parent().find_validator()


class FloatParameter(PrimitiveParameter):
    def __init__(self, **opts):
        super().__init__(**opts, type='float')

    def makeTreeItem(self, depth):
        return NumericParameterItem(self, depth, self.desc, self.typehint)

    def _interpretValue(self, v):
        return float(v)

    def handle_change(self, param, change, data):
        logger.debug(f'Float parameter {self.name()} passing {change} {data}')
        self.parent().handle_change(param, change, data)


class StringParameter(PrimitiveParameter):
    def __init__(self, **opts):
        super().__init__(**opts)

    def makeTreeItem(self, depth):
        return StringParameterItem(self, depth, self.desc, self.typehint)

    def _interpretValue(self, v):
        return str(v)


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
    pass


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
