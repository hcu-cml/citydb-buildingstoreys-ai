import xml.etree.ElementTree as ET
import json

# Load the CityGML file
tree = ET.parse("INPUT_CITYGML_FILE.gml")
root = tree.getroot()

ns = {
    "gml": "http://www.opengis.net/gml",
    "bldg": "http://www.opengis.net/citygml/building/2.0"
}

features = []

# Loop through each Building
for building in root.findall(".//bldg:Building", ns):
    envelope = building.find(".//gml:Envelope", ns)
    if envelope is None:
        continue

    lower = envelope.find("gml:lowerCorner", ns).text.split()
    upper = envelope.find("gml:upperCorner", ns).text.split()

    minx, miny = map(float, lower[:2])
    maxx, maxy = map(float, upper[:2])

    # Find storeysAboveGround (if available)
    storeys_elem = building.find("bldg:storeysAboveGround", ns)
    storeys = int(storeys_elem.text) if storeys_elem is not None else None

    # Create GeoJSON polygon (2D bounding box)
    coords = [
        [
            [minx, miny],
            [maxx, miny],
            [maxx, maxy],
            [minx, maxy],
            [minx, miny]
        ]
    ]

    feature = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": coords
        },
        "properties": {
            "id": building.get("{http://www.opengis.net/gml}id"),
            "storeysAboveGround": storeys
        }
    }
    features.append(feature)

# Create GeoJSON structure
geojson = {
    "type": "FeatureCollection",
    "features": features
}

# Save to file
with open("OUTPUT_GEOJSON_FILE.geojson", "w") as f:
    json.dump(geojson, f, indent=2)
