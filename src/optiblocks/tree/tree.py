import logging
import typing
from typing import Optional

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QSizePolicy
from pydantic import BaseModel, Field
from pyqtgraph.parametertree import Parameter, ParameterTree

from .parameters import BooleanHandler, DictFieldParameter, DictParameter, FieldParameter, \
    FloatHandler, \
    IntHandler, ListFieldParameter, ListParameter, ModelGroupParameter, PrimitiveFloatHandler, \
    PrimitiveListHandler, PydanticGroupParameter, StringHandler, \
    StringParameter

logger = logging.getLogger(__name__)
dbg = lambda x: logger.debug(x)

style = """
QTreeView {
    show-decoration-selected: 1;
}

QTreeView::item {
    selection-color: #ff0000;
    border: 1px solid #d9d9d9;
    border-top-color: transparent;
    border-bottom-color: transparent;
}

QTreeView::branch {
        background: palette(base);
}

QTreeView::branch:has-siblings:!adjoins-item {
        background: cyan;
}

QTreeView::branch:has-siblings:adjoins-item {
        background: red;
}

QTreeView::branch:!has-children:!has-siblings:adjoins-item {
        background: blue;
}

QTreeView::branch:closed:has-children:has-siblings {
        background: pink;
}

QTreeView::branch:has-children:!has-siblings:closed {
        background: gray;
}

QTreeView::branch:open:has-children:has-siblings {
        background: magenta;
}

QTreeView::branch:open:has-children:!has-siblings {
        background: green;
}
"""


class PydanticTree(ParameterTree):
    def __init__(self, parent=None, showHeader: bool = True, compact: bool = False,
                 selection_callbacks=None
                 ):
        ParameterTree.__init__(self, parent, showHeader)
        self.compact = compact
        self.setColumnCount(4)
        self.setHeaderLabels(["Parameter", "Value", "Type", "Description"])
        self.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.set_debug_style()
        self.setIndentation(10)
        self.selection_callbacks = selection_callbacks

    def set_debug_style(self):
        self.setStyleSheet(style)

    def selectionChanged(self, *args):
        logger.debug(f'Pydantic tree selection changed to {args=} {self.selectedItems()=}')
        sel = self.selectedItems()
        super().selectionChanged(*args)
        if len(sel) != 1:
            sel = None
        # if self.lastSel is not None and isinstance(self.lastSel, ParameterItem):
        #    self.lastSel.selected(False)
        if sel is None:
            self.lastSel = None
            return
        self.lastSel = sel[0]
        if hasattr(sel[0], 'selected'):
            sel[0].selected(True)

        if self.selection_callbacks is not None:
            for x in self.selection_callbacks:
                x(sel)
        # return super().selectionChanged(*args)


acceptable_types = {str: 'str', float: 'float', int: 'int', bool: 'bool'}


class ModelContainer:
    """
    This class wraps a pydantic model in a configuration tree

    General architecture:
    We use pyqtgraph Parameter item subclasses to build a hierarchy customized for the
    various field types. ParameterItem subclasses are then responsible for
    displaying the elements inside a PydanticTree main widget. Appearance of the tree
    can be changed without changing any parameters.

    """
    options_whitelist = ['']

    def __init__(self, window, trace: bool = True):
        self.window = window
        self.trace = trace
        self.rp = Parameter.create(name='params', type='group')
        self.tree = t = PydanticTree()
        self.block = False
        self.model = None
        t.setParameters(self.rp, showTop=False)
        t.setWindowTitle('Parameter tree:')

        self.handler_map = hm = {}

        hm[BaseModel] = self.assemble_model_group
        hm[float] = FloatHandler()
        hm[str] = StringHandler()
        hm[int] = IntHandler()
        hm[bool] = BooleanHandler()
        # hm[dict] = lambda field, value: Parameter.create(name=field.name, type='str', value=value)

        # Primitive map contains handlers for simple types that might be encountered inside fields
        self.primitive_map = pm = {}
        pm[dict] = lambda a, v: Parameter.create(name=a, type='str', value=v)
        pm[str] = lambda a, v: Parameter.create(name=a, type='str', value=v)
        pm[float] = PrimitiveFloatHandler()
        pm[bool] = lambda a, v: Parameter.create(name=a, type='bool', value=v)
        pm[int] = lambda a, v: Parameter.create(name=a, type='int', value=v)
        pm[list] = PrimitiveListHandler()

        self.callbacks = []

    def add_callback(self, f):
        self.callbacks.append(f)

    def set_model(self, model: BaseModel = None):
        """
        Set the active model. Tree will be recreated, discarding previous state.
        """
        self.rp.clearChildren()
        root_group = self.dispatch(model, root_name='Root')
        self.rp.addChild(root_group)
        self.rp.sigTreeStateChanged.connect(self.change)
        self.rp.sigValueChanging.connect(self.valueChanging)
        self.rp.sigValueChanged.connect(self.valueChanged)
        self.model = model

    def dispatch(self, obj, root_name: str):
        """
        Main method to dispatch top-level fields to their handlers. We avoid registration
        in pyqtgraph because it can't handle the variety of cases we have
        """
        if isinstance(obj, BaseModel):
            return self.assemble_model_group(obj, root_name=root_name)
        elif isinstance(obj, list):
            return self.assemble_list_group(obj, root_name=root_name)
        elif isinstance(obj, dict):
            return self.assemble_dict_group(obj, root_name=root_name)
        elif isinstance(obj, (str, float, int, bool)):
            param = self.find_primitive_delegate(root_name, obj)
            if self.trace:
                logger.debug(f'Resolved primitive {obj=} to {param} {param.__class__.__name__}')
            return param
        elif isinstance(obj, Field):
            raise ValueError(f'Raw fields should never be dispatched directly')
        else:
            return None

    def find_field_delegate(self, field: Field, field_name: str, value: typing.Any,
                            root_name: str, parent: Parameter
                            ) -> Optional[Parameter]:
        """ Find method to handle the field """
        t = type(value)
        handler = self.handler_map.get(t, None)
        if handler is not None:
            if self.trace:
                dbg(f'Type delegate of field {field_name=} {value=} {t=} resolved to {handler}')
            p = handler(field, value, parent)
            dbg(f'Field {field_name} parameter result: {p}')
            return p
        return None

    def find_primitive_delegate(self, name, value):
        """ Find method to handle the primitive type """
        t = type(value)
        if t in self.primitive_map:
            return self.primitive_map[t](name, value)
        raise NotImplementedError(f'{name=} {value=}')

    # def assemble_par_group(self, obj, rt_name=None):
    #     children = []
    #     try:
    #         field_to_type = typing.get_type_hints(obj)
    #         for aname, atype in field_to_type.items():
    #             value = getattr(obj, aname)
    #             if self.trace:
    #                 logger.debug(f'{aname=} | {atype=} | {value=} {value.__class__} ')
    #             try:
    #                 param = self.find_field_delegate(aname, value)
    #             except NotImplementedError:
    #                 logger.debug(f'Delegate resolution failed, trying advanced types')
    #                 if isinstance(value, list):
    #                     param = self.assemble_field_list_group(value, root_name=aname)
    #                 elif isinstance(value, dict):
    #                     param = Parameter.create(name=aname, type='str', value=value)
    #                 elif isinstance(value, BaseModel):
    #                     param = self.assemble_par_basemodel_group(value, rt_name=aname)
    #                 elif isinstance(value, str):
    #                     param = Parameter.create(name=aname, type='str', value=value)
    #                 else:
    #                     raise NotImplementedError
    #             if self.trace:
    #                 logger.debug(f'Resolved to param {param} {param.__class__.__name__}')
    #             children.append(param)
    #         # logger.info(f'{len(children)} children for {options.__class__.__name__}')
    #         name = rt_name if rt_name is not None else obj.__class__.__name__
    #         grp = Parameter.create(name=name, type='group', children=children)
    #         grp.setOpts(expanded=True)
    #         return grp
    #     except TypeError as ex:
    #         # won't have type hints for primitives
    #         if isinstance(obj, (str, float, int, bool)):
    #             param = self.find_field_delegate(rt_name, obj.__class__, obj)
    #             if self.trace:
    #                 logger.debug(f'Resolved primitive {obj=} to {param} {param.__class__.__name__}')
    #             children.append(param)
    #         else:
    #             raise NotImplementedError
    #
    #         grp = param
    #         grp.setOpts(expanded=True)
    #         return grp

    def assemble_model_group(self, model: BaseModel, root_name: str, field=None):
        fields = model.__fields__
        children = []
        grp = ModelGroupParameter(name=root_name,
                                  basemodel=model)
        for field_name, field in fields.items():
            value = getattr(model, field_name)
            actual_type = type(value)
            if self.trace:
                dbg(f'Field ({field_name}): {actual_type=} | {value=} {value.__class__} '
                    f'| {root_name=} ')
            param = self.find_field_delegate(field, field_name, value, root_name, grp)
            if param is None:
                dbg(f'Delegate resolution failed, trying advanced types')
                if isinstance(value, list):
                    param = self.assemble_field_list_group(field, value, root_name=field_name)
                    param.path = f'{root_name}.{field_name}'
                elif isinstance(value, dict):
                    param = self.assemble_field_dict_group(field, value, root_name=field_name)
                    param.path = f'{root_name}.{field_name}'
                else:
                    logger.warning(f'No delegate match, skipping {field_name}')
                    continue
            children.append(param)
        grp.addChildren(children)
        grp.setOpts(expanded=True)
        return grp

    def assemble_field_dict_group(self, field: Field, d, root_name):
        children = []
        for i, (k, v) in enumerate(d.items()):
            # param = self.find_primitive_delegate(k, v)
            param = self.dispatch(v, root_name=f'{root_name}[{k}]')
            children.append(param)
        grp = DictFieldParameter(name=root_name, field=field, children=children,
                                 typehint='<dict>', desc=field.field_info.description)
        grp.setOpts(expanded=True)
        return grp

    def assemble_dict_group(self, data: dict, root_name):
        children = []
        for i, (k, v) in enumerate(data.items()):
            param = self.dispatch(v, root_name=f'{root_name}[{k}]')
            children.append(param)
        grp = DictParameter(name=root_name, children=children,
                            typehint='<dict>')
        grp.setOpts(expanded=True)
        return grp

    def assemble_field_list_group(self, field: Field, items: list, root_name: str):
        """
        Make group for model field with list type
        """
        children = []
        for i, value in enumerate(items):
            param = self.dispatch(value, root_name=f'{root_name}[{i}]')
            children.append(param)
        grp = ListFieldParameter(name=root_name, field=field, type='group', children=children,
                                 typehint='<list>', desc=field.field_info.description)
        grp.setOpts(expanded=True)
        dbg(f'Made group for list {field.name=}')
        return grp

    def assemble_list_group(self, items: list, root_name: str):
        """
        Make group for list that is not a field
        """
        children = []
        for i, value in enumerate(items):
            param = self.dispatch(value, root_name=f'{root_name}[{i}]')
            children.append(param)
        grp = ListParameter(name=root_name, type='group', children=children,
                            typehint='<list>')
        grp.setOpts(expanded=True)
        return grp

    # def set_model(self, options=None):
    #     self.p.clearChildren()
    #     #
    #     if options is None:
    #         opt: Optimizer = self.window.o
    #         if opt is None:
    #             return
    #         options = opt.options
    #         self.p.addChild(self.assemble_par_group(options, rt_name='Optimizer options'))
    #         # children = []
    #         # field_to_type = typing.get_type_hints(options)
    #         # for k, v in field_to_type.items():
    #         #     value = getattr(options, k)
    #         #     if v in acceptable_types:
    #         #         param = Parameter.create(name=k, type=acceptable_types[v], value=value)
    #         #         children.append(param)
    #         # grp = Parameter.create(name=f'Optimizer options', type='group', children=children)
    #         # grp.setOpts(expanded=True)
    #         # self.p.addChild(grp)
    #         #
    #         options = opt.generator.options
    #         self.p.addChild(self.assemble_par_group(options, rt_name='Generator options'))
    #
    #         options = opt.evaluator.options
    #         self.p.addChild(self.assemble_par_group(options, rt_name='Evaluator options'))
    #
    #         options = opt.gvocs
    #         self.p.addChild(self.assemble_par_group(options, rt_name='VOCS'))
    #         # self.p.clearChildren()
    #         # p_name = Parameter.create(name='Device name', type='str', value=device.name, readonly=True)
    #         # self.p.addChild(p_name)
    #         # self.p.addChild(grp)
    #         self.p.sigTreeStateChanged.connect(self.change)
    #
    #         # Only listen for changes of the 'widget' child:
    #         # for child in self.p.child('Optimizer options'):
    #         #     if 'widget' in child.names:
    #         #         child.child('widget').sigValueChanging.connect(self.valueChanging)
    #     else:
    #         options = options
    #         self.p.addChild(self.assemble_par_group(options, rt_name='Optimizer options'))

    def valueChanging(self, param, value):
        dbg("Value changing (not finalized): %s %s" % (param, value))

    def valueChanged(self, param, value):
        dbg("Value changed: %s %s" % (param, value))

    def change(self, param, changes):
        dbg(f'Tree change callback: {len(changes)} changes')

        for param, change, data in changes:
            path = self.rp.childPath(param)
            if path is not None:
                childName = '.'.join(path)
            else:
                childName = param.name()

            if change != 'value':
                continue

            if self.block:
                # print('blocked due to skip')
                continue

            dbg(f'  Parameter: {param} ')
            dbg(f'  Path: {childName}')
            dbg(f'  New value: {data} {type(data)=}')
            dbg('----------------------------')

            param.propose_self_change(data)
            param.handle_self_change(data)

        for f in self.callbacks:
            f(self)


class WalkingParameterTree(ModelContainer):
    def change(self, param, changes):
        dbg = lambda x: logger.debug(x)
        dbg(f'Tree change callback: {len(changes)} changes')

        for param, change, data in changes:
            path = self.rp.childPath(param)
            if path is not None:
                childName = '.'.join(path)
            else:
                childName = param.name()

            if change != 'value':
                continue

            if self.block:
                # print('blocked due to skip')
                continue

            dbg(f'  Parameter: {param} ')
            dbg(f'  Path: {childName}')
            dbg(f'  New value: {data}')
            dbg('----------------------------')

            splits = childName.split('.')
            root = splits[0]
            intermediates = splits[1:-1]
            attribute: list = [splits[-1]]

            list_mode = False
            try:
                int_attr = [int(attribute[0])]
                attribute = [intermediates[:-1]] + int_attr
                intermediates = intermediates[:-1]
                list_mode = True
            except:
                pass

            dbg(f'Setting: {root=} {intermediates=} {attribute=}')

            node: BaseModel = self.model
            for depth, i in enumerate(intermediates):
                if '[' in i:
                    var, key = i.split('[')
                    key = key[:-1]
                    if hasattr(node, var):
                        if isinstance(node, list):
                            try:
                                intkey = int(key)
                                if len(node) > intkey:
                                    node = node[intkey]
                                    dbg(f'Went down 1 level -> {i} [LIST]')
                                else:
                                    raise AttributeError(f'List {node} too short for {intkey}')
                            except:
                                raise
                        elif isinstance(node, dict):
                            if hasattr(node, key):
                                node = node[key]
                                dbg(f'Went down 1 level -> {i} [LIST]')
                            else:
                                raise AttributeError(f'Missing key {key} in dict {node}')

                elif hasattr(node, i):
                    node = getattr(node, i)
                    dbg(f'Went down 1 level -> {i}')
                else:
                    raise AttributeError(f'Node {node} has no attribute {i}, write abort')

            dbg(f'At final node {node}')

            if hasattr(node, attribute[0]):
                old_value = getattr(node, attribute[0])
                if list_mode:
                    # we need to set right element of list
                    assert isinstance(old_value, list)
                    logger.debug(f'Reached list, changing item ')
                    idx = attribute[1]
                    logger.debug(f'List {idx=} -> {data}')
                    assert type(data) == type(old_value[idx])
                    old_value[idx] = data
                else:
                    # final attribute is not list
                    if isinstance(old_value, (str, float, int, bool)):
                        setattr(node, attribute[0], data)
                    else:
                        raise AttributeError(f'Attempted on non-basic type {old_value=}')
                    dbg(f'setattr succeeded {splits=} {data=}')
            else:
                dbg(f'Final node {node} missing {attribute=}')


class AOParameterTree(ModelContainer):
    def change(self, param, changes):
        for param, change, data in changes:
            path = self.rp.childPath(param)
            if path is not None:
                childName = '.'.join(path)
            else:
                childName = param.name()

            if change != 'value':
                continue

            if self.block:
                # print('blocked due to skip')
                continue

            print('  parameter: %s' % childName)
            print('  change:    %s' % change)
            print('  data:      %s' % str(data))
            print('  ----------')

            splits = childName.split('.')
            root = splits[0]
            intermediates = splits[1:-1]
            attribute = splits[-1]

            roots = {'Generator options': self.window.o.generator.options,
                     'Evaluator options': self.window.o.evaluator.options,
                     'Optimizer options': self.window.o.options
                     }

            logger.debug(f'Have root {root} and attribute {attribute}')
            if root in roots:
                logger.debug(f'Resolve to {roots[root]}, trying to to set to {data}')
                opt = roots[root]
                try:
                    final_list = False
                    for i in intermediates:
                        assert not final_list
                        opt = getattr(opt, i)
                        logger.debug(f'Went down 1 level to {i}')
                        if isinstance(opt, list):
                            logger.debug(f'Reached list item')
                            final_list = True
                    if final_list:
                        idx = int(attribute)
                        logger.debug(f'List {idx=} -> {data}')
                        assert type(data) == type(opt[idx])
                        opt[idx] = data
                    else:
                        current_attr = getattr(opt, attribute)
                        if isinstance(current_attr, (str, float, int, bool)):
                            setattr(opt, attribute, data)
                        else:
                            raise Exception(f'setattr attempted on non-basic type')
                    logger.info(f'setattr succeeded')
                except Exception as ex:
                    logger.error(f'setattr failed with: {ex}')
