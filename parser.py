# -*- coding: utf-8 -*-
"""
Text2Map Parser – QGIS 4 / Qt6 compatible.

Pure Python + PyQGIS core (no Qt widget imports).
QgsGeometry / QgsPointXY APIs are unchanged between QGIS 3 and 4.

Supported formats
-----------------
  Decimal lat/lon  – one pair per line, comma/space/semicolon separated
  DMS              – 28°36'50"N 77°12'32"E
  JSON             – single object or array with lat/lon key variants
  GeoJSON          – FeatureCollection, Feature, or bare geometry
  WKT              – POINT / LINESTRING / POLYGON and MULTI* variants

Critical fixes vs v1
--------------------
  - _geojson_geom() no longer silently swallows exceptions; errors propagate
  - MultiPoint WKT rendering corrected
  - All geometry types (Point, LineString, Polygon, Multi*) fully tested
  - Attribute extraction preserves all non-coordinate GeoJSON properties
"""

import re
import json

from qgis.core import QgsGeometry, QgsPointXY


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LAT_KEYS = frozenset({'lat', 'latitude', 'y', 'ylat', 'lat_y'})
_LON_KEYS = frozenset({'lon', 'lng', 'longitude', 'x', 'xlon', 'lon_x', 'long'})

# DMS: supports ° or d, ' or m, " or s, optional space between parts
_RE_DMS = re.compile(
    r'(\d+)\s*[°d]\s*(\d+)\s*[\'m]\s*(\d+(?:\.\d+)?)\s*[\"s]?\s*([NSns])'
    r'\s*[,;\s]+\s*'
    r'(\d+)\s*[°d]\s*(\d+)\s*[\'m]\s*(\d+(?:\.\d+)?)\s*[\"s]?\s*([EWew])',
    re.IGNORECASE
)

_RE_WKT_START = re.compile(
    r'^\s*(POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|'
    r'MULTIPOLYGON|GEOMETRYCOLLECTION)\s*[ZM]*\s*\(',
    re.IGNORECASE
)

_GEOJSON_TYPES = frozenset({
    'FeatureCollection', 'Feature',
    'Point', 'LineString', 'Polygon',
    'MultiPoint', 'MultiLineString', 'MultiPolygon',
    'GeometryCollection',
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class Text2MapParser:
    """
    Detect input format and return:
        (format_name: str, geometries: list[QgsGeometry], attributes: list[dict])

    Raises ValueError with a human-readable message on failure.
    """

    def parse(self, text: str):
        text = text.strip()
        if not text:
            raise ValueError('Input is empty.')

        # Detection order matters:
        # GeoJSON before generic JSON (both start with { or [)
        # WKT before lat/lon (WKT starts with a keyword)
        if self._is_geojson(text):
            return self._parse_geojson(text)

        if _RE_WKT_START.match(text):
            return self._parse_wkt(text)

        if text.startswith(('{', '[')):
            return self._parse_json(text)

        if _RE_DMS.search(text):
            return self._parse_dms(text)

        return self._parse_latlon(text)

    # ------------------------------------------------------------------
    # GeoJSON detection
    # ------------------------------------------------------------------

    def _is_geojson(self, text: str) -> bool:
        if not text.startswith(('{', '[')):
            return False
        try:
            obj = json.loads(text)
        except Exception:
            return False
        return isinstance(obj, dict) and obj.get('type') in _GEOJSON_TYPES

    # ------------------------------------------------------------------
    # GeoJSON parser
    # ------------------------------------------------------------------

    def _parse_geojson(self, text: str):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError('Invalid GeoJSON: ' + str(e))

        geometries, attributes = [], []
        t = obj.get('type', '')

        if t == 'FeatureCollection':
            features = obj.get('features') or []
            if not features:
                raise ValueError('GeoJSON FeatureCollection has no features.')
            for idx, feat in enumerate(features):
                geom_dict = feat.get('geometry')
                if not geom_dict:
                    raise ValueError(
                        'Feature #%d has no "geometry" key.' % (idx + 1)
                    )
                # Let conversion errors propagate with full detail
                wkt = self._geojson_to_wkt(geom_dict)
                g = QgsGeometry.fromWkt(wkt)
                if g is None or g.isEmpty():
                    raise ValueError(
                        'Feature #%d: WKT could not be parsed by QGIS.\nWKT was: %s'
                        % (idx + 1, wkt)
                    )
                geometries.append(g)
                attributes.append(dict(feat.get('properties') or {}))

        elif t == 'Feature':
            geom_dict = obj.get('geometry')
            if not geom_dict:
                raise ValueError('GeoJSON Feature has no "geometry" key.')
            wkt = self._geojson_to_wkt(geom_dict)
            g = QgsGeometry.fromWkt(wkt)
            if g is None or g.isEmpty():
                raise ValueError('Feature geometry could not be parsed.\nWKT was: ' + wkt)
            geometries.append(g)
            attributes.append(dict(obj.get('properties') or {}))

        else:
            # Bare geometry object
            wkt = self._geojson_to_wkt(obj)
            g = QgsGeometry.fromWkt(wkt)
            if g is None or g.isEmpty():
                raise ValueError('Geometry could not be parsed.\nWKT was: ' + wkt)
            geometries.append(g)
            attributes.append({})

        return 'GeoJSON', geometries, attributes

    def _geojson_to_wkt(self, g: dict) -> str:
        """
        Convert a GeoJSON geometry dict to a WKT string.
        Raises ValueError with a descriptive message on any problem.
        """
        if not isinstance(g, dict):
            raise ValueError('Expected a GeoJSON geometry object (dict), got: ' + type(g).__name__)

        gtype = g.get('type')
        if not gtype:
            raise ValueError('GeoJSON geometry is missing "type" field.')

        coords = g.get('coordinates')
        if coords is None:
            raise ValueError('GeoJSON geometry "%s" is missing "coordinates".' % gtype)

        def pt(xy):
            """lon lat pair → WKT token."""
            if len(xy) < 2:
                raise ValueError('Coordinate pair has fewer than 2 values: %s' % xy)
            return '%s %s' % (xy[0], xy[1])

        def ring(coord_list):
            return '(%s)' % ', '.join(pt(p) for p in coord_list)

        try:
            if gtype == 'Point':
                return 'POINT(%s %s)' % (coords[0], coords[1])

            if gtype == 'MultiPoint':
                # Each element is a [lon, lat] pair
                return 'MULTIPOINT(%s)' % ', '.join(
                    '(%s %s)' % (c[0], c[1]) for c in coords
                )

            if gtype == 'LineString':
                return 'LINESTRING(%s)' % ', '.join(pt(p) for p in coords)

            if gtype == 'MultiLineString':
                return 'MULTILINESTRING(%s)' % ', '.join(ring(r) for r in coords)

            if gtype == 'Polygon':
                return 'POLYGON(%s)' % ', '.join(ring(r) for r in coords)

            if gtype == 'MultiPolygon':
                polys = [
                    '(%s)' % ', '.join(ring(r) for r in poly)
                    for poly in coords
                ]
                return 'MULTIPOLYGON(%s)' % ', '.join(polys)

        except (IndexError, TypeError) as e:
            raise ValueError(
                'Error reading coordinates for "%s": %s\nCoordinates were: %s'
                % (gtype, e, coords)
            )

        raise ValueError(
            'Unsupported GeoJSON geometry type: "%s".\n'
            'Supported: Point, MultiPoint, LineString, MultiLineString, '
            'Polygon, MultiPolygon.' % gtype
        )

    # ------------------------------------------------------------------
    # WKT parser
    # ------------------------------------------------------------------

    def _parse_wkt(self, text: str):
        geometries, attributes = [], []
        errors = []

        for lineno, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            if not _RE_WKT_START.match(line):
                continue
            g = QgsGeometry.fromWkt(line)
            if g is None or g.isEmpty():
                errors.append('Line %d: invalid WKT: "%s"' % (lineno, line[:80]))
            else:
                geometries.append(g)
                attributes.append({})

        if not geometries:
            msg = 'Could not parse any WKT geometry.'
            if errors:
                msg += '\n\nDetails:\n' + '\n'.join(errors[:5])
            raise ValueError(msg)

        return 'WKT', geometries, attributes

    # ------------------------------------------------------------------
    # JSON / JSON array parser
    # ------------------------------------------------------------------

    def _parse_json(self, text: str):
        try:
            obj = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError('Invalid JSON: ' + str(e))

        items = obj if isinstance(obj, list) else [obj]
        geometries, attributes = [], []

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            lat, lon = self._lat_lon_from_dict(item)
            if lat is not None and lon is not None:
                g = QgsGeometry.fromPointXY(QgsPointXY(lon, lat))
                geometries.append(g)
                attrs = {
                    k: v for k, v in item.items()
                    if k.lower() not in (_LAT_KEYS | _LON_KEYS)
                }
                attributes.append(attrs)

        if not geometries:
            raise ValueError(
                'No lat/lon keys found in JSON.\n'
                'Supported key names: lat, latitude, y  /  lon, lng, longitude, x'
            )
        return 'JSON', geometries, attributes

    def _lat_lon_from_dict(self, d: dict):
        lower_map = {k.lower(): k for k in d}
        lat_key = next((lower_map[k] for k in lower_map if k in _LAT_KEYS), None)
        lon_key = next((lower_map[k] for k in lower_map if k in _LON_KEYS), None)
        if lat_key and lon_key:
            try:
                return float(d[lat_key]), float(d[lon_key])
            except (ValueError, TypeError):
                pass
        return None, None

    # ------------------------------------------------------------------
    # Decimal lat/lon lines
    # ------------------------------------------------------------------

    def _parse_latlon(self, text: str):
        geometries, attributes, errors = [], [], []

        for lineno, raw_line in enumerate(text.splitlines(), 1):
            line = raw_line.strip()
            if not line:
                continue
            parts = re.split(r'[,;\s]+', line)
            parts = [p for p in parts if p]

            if len(parts) < 2:
                errors.append('Line %d: need ≥2 values, got: "%s"' % (lineno, line))
                continue

            try:
                lat, lon = float(parts[0]), float(parts[1])
            except ValueError:
                errors.append('Line %d: cannot parse numbers from "%s"' % (lineno, line))
                continue

            if not (-90 <= lat <= 90):
                errors.append('Line %d: latitude %.6f out of range [-90, 90]' % (lineno, lat))
                continue
            if not (-180 <= lon <= 180):
                errors.append('Line %d: longitude %.6f out of range [-180, 180]' % (lineno, lon))
                continue

            geometries.append(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
            attributes.append({'lat': lat, 'lon': lon})

        if not geometries:
            msg = 'No valid lat/lon pairs found.'
            if errors:
                msg += '\n\nDetails:\n' + '\n'.join(errors[:8])
            raise ValueError(msg)

        return 'Lat/Lon (decimal)', geometries, attributes

    # ------------------------------------------------------------------
    # DMS
    # ------------------------------------------------------------------

    def _parse_dms(self, text: str):
        geometries, attributes = [], []

        for m in _RE_DMS.finditer(text):
            ld, lm, ls, lh, od, om, os_, oh = m.groups()
            lat = self._dms_to_dd(int(ld), int(lm), float(ls), lh)
            lon = self._dms_to_dd(int(od), int(om), float(os_), oh)
            geometries.append(QgsGeometry.fromPointXY(QgsPointXY(lon, lat)))
            attributes.append({'lat': round(lat, 8), 'lon': round(lon, 8)})

        if not geometries:
            raise ValueError('Could not parse any DMS coordinates from the input.')

        return 'Lat/Lon (DMS)', geometries, attributes

    @staticmethod
    def _dms_to_dd(deg: int, mins: int, secs: float, hemisphere: str) -> float:
        dd = deg + mins / 60.0 + secs / 3600.0
        if hemisphere.upper() in ('S', 'W'):
            dd = -dd
        return dd
