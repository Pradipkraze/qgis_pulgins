# Text2Map – QGIS 3 Plugin (v1.1.0)

**Convert pasted text into map geometry layers — instantly.**

> **QGIS 3.16+ / Qt5.** For QGIS 4.x, use the v2.x release.

## Supported Input Formats

| Format | Example |
|---|---|
| Decimal lat/lon | `28.6139, 77.2090` (one pair per line) |
| DMS | `28°36'50"N 77°12'32"E` |
| JSON / JSON array | `{"lat": 28.61, "lon": 77.20, "name": "Delhi"}` |
| GeoJSON | FeatureCollection, Feature, or bare geometry |
| WKT | `POINT(77.209 28.613)`, `LINESTRING(...)`, `POLYGON(...)` |

## Installation

**Plugins → Manage and Install Plugins → Install from ZIP**

## Usage

1. Click the **Text2Map** toolbar button
2. Paste spatial data into the text area
3. Optionally set a layer name
4. Click **Create Layer**

## Requirements

- QGIS **3.16** or later
- No additional Python packages required
