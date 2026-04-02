# Changelog

## [1.1.0] – Bug fix release (QGIS 3.x / Qt5)

### Fixed
- **QgsField type** — was passing plain `'string'` which throws `TypeError`.
  Now correctly uses `QVariant.String`, `QVariant.Int`, `QVariant.Double`
- **Silent GeoJSON failures** — `_geojson_geom()` was swallowing all exceptions
  with a bare `except: return None`, hiding the real error. Now propagates full
  error detail to the user via message box and status label
- **bool vs int** — `bool` is a subclass of `int` in Python; `isinstance(True, int)`
  returns `True`. Fixed by checking `bool` first before `int`
- **Nested JSON values** — `dict`/`list` property values now safely stringified
  before being passed to `setAttributes()` to avoid QGIS type errors
- **MultiPoint WKT** — corrected coordinate rendering for MultiPoint geometries
- **Error visibility** — all parse errors now shown in both the status label
  and a critical message box with full detail

## [1.0.0] – Initial release
- Decimal lat/lon, DMS, JSON, GeoJSON, WKT support
- Auto format detection, memory layer creation
