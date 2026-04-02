# -*- coding: utf-8 -*-
"""
Text2Map Dock Widget – QGIS 3 / Qt5

Uses QVariant (still present in Qt5) for QgsField type declarations.
All bug fixes from v2 applied:
  - No silent exception swallowing in GeoJSON parsing
  - Correct QgsField construction with QVariant types
  - bool checked before int (bool is subclass of int in Python)
  - Nested JSON values (dict/list) stringified safely
  - Full error messages surfaced to the user
"""

from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPlainTextEdit, QPushButton, QLineEdit,
    QMessageBox, QSizePolicy, QFrame
)
from qgis.PyQt.QtCore import Qt, QVariant   # QVariant still present in Qt5
from qgis.PyQt.QtGui import QFont

from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY,
    QgsProject, QgsWkbTypes, QgsField
)

from .parser import Text2MapParser

# ---------------------------------------------------------------------------
# Safe QgsField factory – QGIS 3 / Qt5 uses QVariant
# ---------------------------------------------------------------------------

def _make_field(name, value):
    """
    Return a QgsField whose type matches the Python value.
    QGIS 3 / Qt5: QgsField(name, QVariant.Type)
    bool must be checked before int (bool subclasses int in Python).
    """
    col = str(name)
    if isinstance(value, bool):
        return QgsField(col, QVariant.String)
    if isinstance(value, int):
        return QgsField(col, QVariant.Int)
    if isinstance(value, float):
        return QgsField(col, QVariant.Double)
    # str, None, list, dict → store as text
    return QgsField(col, QVariant.String)


class Text2MapDockWidget(QDockWidget):
    """Side-panel dock widget – QGIS 3 / Qt5."""

    def __init__(self, iface, parent=None):
        super().__init__('Text2Map', parent)
        self.iface = iface
        self.parser = Text2MapParser()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel('Text2Map')
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignCenter)   # Qt5: short form OK
        layout.addWidget(title)

        subtitle = QLabel('Paste coordinates, JSON, GeoJSON or WKT below')
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet('color: gray; font-size: 10px;')
        layout.addWidget(subtitle)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)      # Qt5: short form OK
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        input_lbl = QLabel('Input Data:')
        input_lbl.setStyleSheet('font-weight: bold;')
        layout.addWidget(input_lbl)

        self.text_input = QPlainTextEdit()
        self.text_input.setPlaceholderText(
            'Paste any supported format:\n\n'
            '• Decimal lat/lon (one pair per line):\n'
            '    28.6139, 77.2090\n'
            '    12.9716, 77.5946\n\n'
            '• DMS:  28°36\'50"N 77°12\'32"E\n\n'
            '• JSON: {"lat":28.61,"lon":77.20,"name":"Delhi"}\n\n'
            '• GeoJSON (FeatureCollection / Feature)\n\n'
            '• WKT:\n'
            '    POINT(77.209 28.613)\n'
            '    LINESTRING(77.2 28.6, 77.3 28.7)\n'
            '    POLYGON((lon lat, ...))'
        )
        self.text_input.setSizePolicy(
            QSizePolicy.Expanding,   # Qt5: short form OK
            QSizePolicy.Expanding
        )
        layout.addWidget(self.text_input, stretch=1)

        name_row = QHBoxLayout()
        name_lbl = QLabel('Layer name:')
        name_lbl.setFixedWidth(80)
        self.layer_name_input = QLineEdit('text2map_layer')
        name_row.addWidget(name_lbl)
        name_row.addWidget(self.layer_name_input)
        layout.addLayout(name_row)

        self.format_label = QLabel('Detected format: —')
        self.format_label.setStyleSheet('color: #555; font-size: 10px;')
        layout.addWidget(self.format_label)

        btn_row = QHBoxLayout()

        self.create_btn = QPushButton('Create Layer')
        self.create_btn.setStyleSheet(
            'QPushButton{background:#4CAF50;color:white;font-weight:bold;'
            'padding:6px;border-radius:4px;}'
            'QPushButton:hover{background:#45a049;}'
            'QPushButton:pressed{background:#3d8b40;}'
        )
        self.create_btn.clicked.connect(self.on_create)

        self.clear_btn = QPushButton('Clear')
        self.clear_btn.setStyleSheet(
            'QPushButton{background:#e53935;color:white;font-weight:bold;'
            'padding:6px;border-radius:4px;}'
            'QPushButton:hover{background:#c62828;}'
        )
        self.clear_btn.clicked.connect(self.on_clear)

        btn_row.addWidget(self.create_btn)
        btn_row.addWidget(self.clear_btn)
        layout.addLayout(btn_row)

        self.status_label = QLabel('')
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet('font-size: 10px;')
        layout.addWidget(self.status_label)

        self.setWidget(container)
        self.setMinimumWidth(270)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def on_create(self):
        raw = self.text_input.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, 'Text2Map', 'Please paste some spatial data first.')
            return

        try:
            fmt, geometries, attributes = self.parser.parse(raw)
        except Exception as exc:
            QMessageBox.critical(self, 'Text2Map – Parse Error', str(exc))
            self.format_label.setText('Detected format: ERROR')
            self.status_label.setText('Error: ' + str(exc))
            self.status_label.setStyleSheet('color:red;font-size:10px;')
            return

        self.format_label.setText('Detected format: ' + fmt)

        if not geometries:
            QMessageBox.warning(self, 'Text2Map', 'No valid geometries found.')
            return

        layer = self._create_layer(geometries, attributes)
        if layer:
            self.status_label.setText(
                'Created "' + layer.name() + '" – '
                + str(layer.featureCount()) + ' feature(s).'
            )
            self.status_label.setStyleSheet('color:green;font-size:10px;')

    def on_clear(self):
        self.text_input.clear()
        self.format_label.setText('Detected format: —')
        self.status_label.setText('')

    # ------------------------------------------------------------------
    # Layer creation
    # ------------------------------------------------------------------

    def _create_layer(self, geometries, attributes):
        geom_type = QgsWkbTypes.geometryType(geometries[0].wkbType())

        # Qt5 / QGIS 3: short enum form is fine
        type_map = {
            QgsWkbTypes.PointGeometry:   'Point',
            QgsWkbTypes.LineGeometry:    'LineString',
            QgsWkbTypes.PolygonGeometry: 'Polygon',
        }
        geom_str = type_map.get(geom_type, 'Point')

        layer_name = self.layer_name_input.text().strip() or 'text2map_layer'
        layer = QgsVectorLayer(geom_str + '?crs=EPSG:4326', layer_name, 'memory')

        if not layer.isValid():
            QMessageBox.critical(self, 'Text2Map', 'Failed to create memory layer.')
            return None

        provider = layer.dataProvider()

        # Build fields with QVariant (QGIS 3 / Qt5 API)
        if attributes and attributes[0]:
            fields = [_make_field(k, v) for k, v in attributes[0].items()]
            provider.addAttributes(fields)
            layer.updateFields()

        # Add features
        features = []
        for i, geom in enumerate(geometries):
            feat = QgsFeature()
            feat.setGeometry(geom)
            if attributes and i < len(attributes):
                vals = [
                    str(v) if isinstance(v, (dict, list)) else v
                    for v in attributes[i].values()
                ]
                feat.setAttributes(vals)
            features.append(feat)

        provider.addFeatures(features)
        layer.updateExtents()

        QgsProject.instance().addMapLayer(layer)
        self.iface.mapCanvas().setExtent(layer.extent())
        self.iface.mapCanvas().refresh()

        return layer
