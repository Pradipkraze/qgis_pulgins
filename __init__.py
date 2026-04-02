# -*- coding: utf-8 -*-
"""
Text2Map QGIS Plugin
Convert text-based spatial data (lat/lon, JSON, GeoJSON, WKT) to map layers.
Requires QGIS 3.16+
"""

def classFactory(iface):
    from .text2map import Text2Map
    return Text2Map(iface)
