import builtins
import logging

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QPlainTextEdit, \
    QSlider, QVBoxLayout, \
    QWidget
from pyqtgraph import SpinBox, functions as fn
from pyqtgraph.parametertree import Parameter, ParameterItem
from pyqtgraph.parametertree.parameterTypes import WidgetParameterItem
from pyqtgraph.parametertree.parameterTypes.basetypes import EventProxy

from apsopt.gui.utils import RM
from .numberbox import NumberBox

translate = QtCore.QCoreApplication.translate

logger = logging.getLogger(__name__)


class PydanticParameterItem(WidgetParameterItem):
    """ The visual item for pydantic parameter """

    def __init__(self, param, depth, description, typehint=''):
        ParameterItem.__init__(self, param, depth)

        self.asSubItem = False
        self.hideWidget = True

        # build widget with a display label and default button
        w = self.makeWidget()
        self.widget = w
        self.eventProxy = EventProxy(w, self.widgetEventFilter)

        if self.asSubItem:
            self.subItem = QtWidgets.QTreeWidgetItem()
            self.subItem.depth = self.depth + 1
            self.subItem.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            self.addChild(self.subItem)

        self.defaultBtn = self.makeDefaultButton()
        self.infoBtn = self.make_info_button()

        self.displayLabel = QtWidgets.QLabel()

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(3, 0, 3, 0)
        layout.setSpacing(2)
        if not self.asSubItem:
            layout.addWidget(w, 1)
        layout.addWidget(self.displayLabel, 1)
        layout.addStretch(0)
        layout.addWidget(self.defaultBtn)
        layout.addWidget(self.infoBtn)
        self.layoutWidget = QtWidgets.QWidget()
        self.layoutWidget.setLayout(layout)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(3, 0, 3, 0)
        layout.setSpacing(2)
        self.typeLabel = QtWidgets.QLabel()
        self.typeLabel.setText(f'{typehint}')
        layout.addWidget(self.typeLabel, 1)
        self.typeWidget = QtWidgets.QWidget()
        self.typeWidget.setLayout(layout)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(3, 0, 3, 0)
        layout.setSpacing(2)
        self.descLabel = QtWidgets.QLabel()
        self.descLabel.setText(description)
        layout.addWidget(self.descLabel, 1)
        self.descWidget = QtWidgets.QWidget()
        self.descWidget.setLayout(layout)

        if w.sigChanged is not None:
            w.sigChanged.connect(self.widgetValueChanged)

        if hasattr(w, 'sigChanging'):
            w.sigChanging.connect(self.widgetValueChanging)

        ## update value shown in widget.
        opts = self.param.opts
        if opts.get('value', None) is not None:
            self.valueChanged(self, opts['value'], force=True)
        else:
            ## no starting value was given; use whatever the widget has
            self.widgetValueChanged()

        self.updateDefaultBtn()
        self.optsChanged(self.param, self.param.opts)

        # set size hints
        sw = self.widget.sizeHint()
        sb = self.defaultBtn.sizeHint()
        # shrink row heights a bit for more compact look
        sw.setHeight(int(sw.height() * 0.9))
        sb.setHeight(int(sb.height() * 0.9))
        if self.asSubItem:
            self.setSizeHint(1, sb)
            self.subItem.setSizeHint(0, sw)
        else:
            w = sw.width() + sb.width()
            h = max(sw.height(), sb.height())
            self.setSizeHint(1, QtCore.QSize(w, h))

    def makeWidget(self):
        raise NotImplementedError

    def make_info_button(self):
        b = QtWidgets.QPushButton()
        b.setAutoDefault(False)
        b.setFixedWidth(20)
        b.setFixedHeight(20)
        b.setIcon(RM.icons['info'])
        b.clicked.connect(self.slot_info_button)
        desc = self.param.desc if hasattr(self.param, 'desc') else '<not available>'
        if desc is None:
            desc = '<not available>'
        b.setToolTip(desc)
        return b

    def slot_info_button(self):
        desc = self.param.desc if hasattr(self.param, 'desc') else '<not available>'
        if desc is None:
            desc = '<not available>'

        # desktop = QApplication.desktop()
        desktop = QApplication.instance().desktop()
        pos = QCursor.pos()
        screen_num = desktop.screenNumber(pos)
        screen_rect = desktop.screenGeometry(screen_num)
        logger.debug(f'Showing tooltip at {screen_num=} {screen_rect=} {pos=}')
        lb = QLabel()
        lb.setWindowFlags(QtCore.Qt.ToolTip)
        lb.setText(desc)
        pos.setY(pos.y() - 20)
        lb.move(pos)
        lb.show()
        t = QTimer()
        t.timeout.connect(lb.hide)
        t.start(50000)
        # QtCore.QTimer.singleShot(t)

        # msgBox = QMessageBox()
        # msgBox.setIcon(QMessageBox.Information)

        # msgBox.setText("Description: " + desc)
        # msgBox.setWindowTitle("Description detail")
        # msgBox.setStandardButtons(QMessageBox.Ok)
        # returnValue = msgBox.exec()

    def treeWidgetChanged(self):
        """Called when this item is added or removed from a tree."""
        ParameterItem.treeWidgetChanged(self)

        if self.widget is not None:
            tree = self.treeWidget()
            if tree is None:
                return
            if self.asSubItem:
                self.subItem.setFirstColumnSpanned(True)
                tree.setItemWidget(self.subItem, 0, self.widget)
            else:
                tree.setItemWidget(self, 1, self.layoutWidget)
                tree.setItemWidget(self, 2, self.typeWidget)
                tree.setItemWidget(self, 3, self.descWidget)
            self.displayLabel.hide()
            self.selected(False)

    def valueChanged(self, param, val, force=False):
        ## called when the parameter's value has changed
        # val = str(val)
        ParameterItem.valueChanged(self, param, val)
        if force or not fn.eq(val, self.widget.value()):
            try:
                if self.widget.sigChanged is not None:
                    self.widget.sigChanged.disconnect(self.widgetValueChanged)
                self.param.sigValueChanged.disconnect(self.valueChanged)
                self.widget.setValue(val)
                self.param.setValue(self.widget.value())
            finally:
                if self.widget.sigChanged is not None:
                    self.widget.sigChanged.connect(self.widgetValueChanged)
                self.param.sigValueChanged.connect(self.valueChanged)
        self.updateDisplayLabel()  ## always make sure label is updated, even if values match!
        self.updateDefaultBtn()

    def showInfo(self):
        self.dialog = dialog = PydanticInfoDialog(self)
        dialog.exec()

    def contextMenuEvent(self, ev):
        opts = self.param.opts

        self.contextMenu = QtWidgets.QMenu()
        self.contextMenu.addSeparator()
        self.contextMenu.addAction(translate("ParameterItem",
                                             "Show Pydantic info")).triggered.connect(
                self.showInfo)
        if opts.get('removable', False):
            self.contextMenu.addAction(translate("ParameterItem", "Remove")).triggered.connect(
                    self.requestRemove)

        # context menu
        context = opts.get('context', None)
        if isinstance(context, list):
            for name in context:
                self.contextMenu.addAction(name).triggered.connect(
                        self.contextMenuTriggered(name))
        elif isinstance(context, dict):
            for name, title in context.items():
                self.contextMenu.addAction(title).triggered.connect(
                        self.contextMenuTriggered(name))

        self.contextMenu.popup(ev.globalPos())


class PydanticInfoDialog(QDialog):
    def __init__(self, parameter):
        super().__init__()
        self.setWindowTitle("Pydantic model information")
        self.setMinimumWidth(500)
        self.setMinimumHeight(500)
        self.fields = {}
        self.widgets = {}
        l = QVBoxLayout()
        self.setLayout(l)

        box = QWidget(self)
        l.addWidget(box)

        self.text = ta = QPlainTextEdit()
        self.text.setReadOnly(True)
        # self.text.setLineWrapMode(QPlainTextEdit.)
        font = self.text.font()
        font.setFamily("Courier")
        font.setPointSize(10)
        l.addWidget(self.text)

        ta.clear()
        ta.appendPlainText('Details:')
        ta.appendPlainText(f'----------------------')
        ta.appendPlainText(f'Parameter: {parameter.param.__class__}')
        for x in ['desc', 'typehint']:
            ta.appendPlainText(f'  {x}: {getattr(parameter.param, x)}')
        ta.appendPlainText(f'  V: {parameter.param.value()}')
        ta.appendPlainText(f'----------------------')
        chain = []
        p = parameter.param
        while p.parent() is not None:
            p = p.parent()
            chain.append(p)

        ta.appendPlainText(f'Parents:')
        for c in chain:
            ta.appendPlainText(f'>>: {c.name()}')

        ta.appendPlainText(f'----------------------')
        h1 = parameter.param.find_change_handler()
        ta.appendPlainText(f'Change handler: {h1}\n')
        h2 = parameter.param.find_validator()
        ta.appendPlainText(f'Validation handler: {h2}\n')

        QBtn = QDialogButtonBox.Ok
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        l.addWidget(self.buttonBox)


class PydanticGroupParameterItem(ParameterItem):
    """
    DERIVED FROM GroupParameterItem
    """

    def __init__(self, param: Parameter, depth: int, value, desc: str, typehint: str):
        super().__init__(param, depth)
        self._initialFontPointSize = self.font(0).pointSize()
        self.updateDepth(depth)

        self.addItem = None
        if 'addText' in param.opts:
            addText = param.opts['addText']
            if 'addList' in param.opts:
                self.addWidget = QtWidgets.QComboBox()
                self.addWidget.setSizeAdjustPolicy(
                        QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
                self.updateAddList()
                self.addWidget.currentIndexChanged.connect(self.addChanged)
            else:
                self.addWidget = QtWidgets.QPushButton(addText)
                self.addWidget.clicked.connect(self.addClicked)
            w = QtWidgets.QWidget()
            l = QtWidgets.QHBoxLayout()
            l.setContentsMargins(0, 0, 0, 0)
            w.setLayout(l)
            l.addWidget(self.addWidget)
            l.addStretch()
            self.addWidgetBox = w
            self.addItem = QtWidgets.QTreeWidgetItem([])
            self.addItem.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.addItem.depth = self.depth + 1
            ParameterItem.addChild(self, self.addItem)
            self.addItem.setSizeHint(0, self.addWidgetBox.sizeHint())

        self.valueLabel, self.valueWidget = self.makeValueWidget(value)
        self.typeLabel, self.typeWidget = self.makeDescWidget(typehint)
        self.descLabel, self.descWidget = self.makeDescWidget(desc)

        self.optsChanged(self.param, self.param.opts)

    def showInfo(self):
        self.dialog = dialog = PydanticInfoDialog(self)
        dialog.exec()

    def contextMenuEvent(self, ev):
        opts = self.param.opts

        self.contextMenu = QtWidgets.QMenu()
        self.contextMenu.addSeparator()
        aa = self.contextMenu.addAction
        aa(translate("ParameterItem", "Show Pydantic info")).triggered.connect(self.showInfo)
        if opts.get('removable', False):
            self.contextMenu.addAction(translate("ParameterItem", "Remove")).triggered.connect(
                    self.requestRemove)
        self.contextMenu.popup(ev.globalPos())

    def makeValueWidget(self, value):
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(3, 0, 3, 0)
        layout.setSpacing(2)
        l = QtWidgets.QLabel()
        l.setText(f'{value}')
        layout.addWidget(l, 1)
        w = QtWidgets.QWidget()
        w.setLayout(layout)
        return l, w

    def makeTypeWidget(self, value):
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(3, 0, 3, 0)
        layout.setSpacing(2)
        l = QtWidgets.QLabel()
        l.setText(f'{value}')
        layout.addWidget(l, 1)
        w = QtWidgets.QWidget()
        w.setLayout(layout)
        return l, w

    def makeDescWidget(self, value):
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(3, 0, 3, 0)
        layout.setSpacing(2)
        l = QtWidgets.QLabel()
        l.setText(f'{value}')
        layout.addWidget(l, 1)
        w = QtWidgets.QWidget()
        w.setLayout(layout)
        return l, w

    def pointSize(self):
        return self._initialFontPointSize

    def updateDepth(self, depth):
        """
        Change set the item font to bold and increase the font size on outermost groups.
        """
        for c in [0, 1]:
            font = self.font(c)
            font.setBold(True)
            if depth == 0:
                font.setPointSize(self.pointSize() + 1)
            self.setFont(c, font)
        self.titleChanged()  # sets the size hint for column 0 which is based on the new font

    def treeWidgetChanged(self):
        ParameterItem.treeWidgetChanged(self)
        tw = self.treeWidget()
        if tw is None:
            return
        self.setFirstColumnSpanned(False)
        # if self.addItem is not None:
        #     tw.setItemWidget(self.addItem, 0, self.addWidgetBox)
        #    self.addItem.setFirstColumnSpanned(True)
        logger.debug(f'Adding items to model group widget {self.typeLabel.text()=}')
        tw.setItemWidget(self, 1, self.valueWidget)
        tw.setItemWidget(self, 2, self.typeWidget)
        tw.setItemWidget(self, 3, self.descWidget)

    def addChild(self, child):  ## make sure added childs are actually inserted before add btn
        if self.addItem is not None:
            ParameterItem.insertChild(self, self.childCount() - 1, child)
        else:
            ParameterItem.addChild(self, child)

    def optsChanged(self, param, opts):
        ParameterItem.optsChanged(self, param, opts)

        if 'addList' in opts:
            self.updateAddList()

        if hasattr(self, 'addWidget'):
            if 'enabled' in opts:
                self.addWidget.setEnabled(opts['enabled'])

            if 'tip' in opts:
                self.addWidget.setToolTip(opts['tip'])

    def updateAddList(self):
        self.addWidget.blockSignals(True)
        try:
            self.addWidget.clear()
            self.addWidget.addItem(self.param.opts['addText'])
            for t in self.param.opts['addList']:
                self.addWidget.addItem(t)
        finally:
            self.addWidget.blockSignals(False)


class StringParameterItem(PydanticParameterItem):
    def __init__(self, param, depth, desc, thint):
        self.targetValue = None
        PydanticParameterItem.__init__(self, param, depth, desc, thint)

    def makeWidget(self):
        w = QtWidgets.QLineEdit()
        w.setStyleSheet('border: 0px')
        w.sigChanged = w.editingFinished
        w.value = w.text
        w.setValue = w.setText
        w.sigChanging = w.textChanged
        self.widget = w
        # if len(self.forward) > 0:
        #    self.setValue(self.param.value())
        return w

    def value(self):
        key = self.widget.currentText()
        return self.forward.get(key, None)


class SimplePydanticParameterItem(PydanticParameterItem):
    def __init__(self, param, depth, desc, thint):
        self.targetValue = None
        super().__init__(param, depth, desc, thint)

    def makeWidget(self):
        w = QtWidgets.QLineEdit()
        w.setStyleSheet('border: 0px')
        w.sigChanged = w.editingFinished
        w.value = w.text
        w.setValue = w.setText
        w.sigChanging = w.textChanged
        self.widget = w
        return w

    def value(self):
        key = self.widget.currentText()
        return self.forward.get(key, None)

    def _interpretValue(self, v):
        typ = self.opts['type']

        def _missing_interp(v):
            raise TypeError(f'No interpreter found for type {typ}')

        interpreter = getattr(builtins, typ, _missing_interp)
        return interpreter(v)


class NumericParameterItem(PydanticParameterItem):
    def makeWidget(self):
        opts = self.param.opts
        t = opts['type']
        defs = {
            'value': 0, 'min': None, 'max': None,
            'step': 1.0, 'dec': False,
            'siPrefix': False, 'suffix': '', 'decimals': 3,
        }
        if t == 'int':
            defs['int'] = True
            defs['minStep'] = 1.0
        for k in defs:
            if k in opts:
                defs[k] = opts[k]
        if 'limits' in opts:
            defs['min'], defs['max'] = opts['limits']
        w = NumberBox()
        w.setOpts(**defs)
        w.sigChanged = w.sigValueChanged
        w.sigChanging = w.sigValueChanging
        return w

    def updateDisplayLabel(self, value=None):
        if value is None:
            value = self.widget.lineEdit().text()
        super().updateDisplayLabel(value)

    def showEditor(self):
        super().showEditor()
        self.widget.selectNumber()  # select the numerical portion of the text for quick editing

    def limitsChanged(self, param, limits):
        self.widget.setOpts(bounds=limits)

    def optsChanged(self, param, opts):
        super().optsChanged(param, opts)
        sbOpts = {}
        if 'units' in opts and 'suffix' not in opts:
            sbOpts['suffix'] = opts['units']
        for k, v in opts.items():
            if k in self.widget.opts:
                sbOpts[k] = v
        self.widget.setOpts(**sbOpts)
        self.updateDisplayLabel()


class BasicNumericParameterItem(PydanticParameterItem):
    def makeWidget(self):
        opts = self.param.opts
        t = opts['type']
        defs = {
            'value': 0, 'min': None, 'max': None,
            'step': 1.0, 'dec': False,
            'siPrefix': False, 'suffix': '', 'decimals': 3,
        }
        if t == 'int':
            defs['int'] = True
            defs['minStep'] = 1.0
        for k in defs:
            if k in opts:
                defs[k] = opts[k]
        if 'limits' in opts:
            defs['min'], defs['max'] = opts['limits']
        w = NumberBox()
        w.setOpts(**defs)
        w.sigChanged = w.sigValueChanged
        w.sigChanging = w.sigValueChanging
        return w

    def updateDisplayLabel(self, value=None):
        if value is None:
            value = self.widget.lineEdit().text()
        super().updateDisplayLabel(value)

    def showEditor(self):
        super().showEditor()
        self.widget.selectNumber()  # select the numerical portion of the text for quick editing

    def limitsChanged(self, param, limits):
        self.widget.setOpts(bounds=limits)

    def optsChanged(self, param, opts):
        super().optsChanged(param, opts)
        sbOpts = {}
        if 'units' in opts and 'suffix' not in opts:
            sbOpts['suffix'] = opts['units']
        for k, v in opts.items():
            if k in self.widget.opts:
                sbOpts[k] = v
        self.widget.setOpts(**sbOpts)
        self.updateDisplayLabel()


class BooleanParameterItem(PydanticParameterItem):
    def makeWidget(self):
        w = QtWidgets.QCheckBox()
        w.sigChanged = w.toggled
        w.value = w.isChecked
        w.setValue = w.setChecked
        self.hideWidget = False
        return w


class SliderParameterItem(PydanticParameterItem):
    def makeWidget(self):
        w = QSlider(Qt.Horizontal, self.parent())
        w.sigChanged = w.valueChanged
        w.sigChanged.connect(self._set_tooltip)
        self.widget = w
        return w

    def _set_tooltip(self):
        self.widget.setToolTip(str(self.widget.value()))
