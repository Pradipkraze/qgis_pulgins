# -*- coding: utf-8 -*-
"""
Text2Map – Main Plugin Class (QGIS 3 / Qt5)
"""

import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt

from .text2map_dockwidget import Text2MapDockWidget


class Text2Map:

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.dock_widget = None
        self.action = None

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icons', 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(icon, 'Text2Map', self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setToolTip('Text2Map – Convert pasted text to geometry layers')
        self.action.triggered.connect(self.toggle_panel)

        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu('&Text2Map', self.action)

    def toggle_panel(self, checked):
        if self.dock_widget is None:
            self.dock_widget = Text2MapDockWidget(self.iface)
            # Qt5: short enum form is valid
            self.dock_widget.setAllowedAreas(
                Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
            )
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
            self.dock_widget.visibilityChanged.connect(self._on_visibility_changed)

        if checked:
            self.dock_widget.show()
        else:
            self.dock_widget.hide()

    def _on_visibility_changed(self, visible):
        self.action.setChecked(visible)

    def unload(self):
        self.iface.removePluginMenu('&Text2Map', self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dock_widget is not None:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None
