import argparse
import json
import os
import xml.etree.ElementTree as ET


def main() -> None:
    ap = argparse.ArgumentParser(description="CityGML 2.0 -> GeoJSON")
    ap.add_argument("--input", required=True, help="Path to CityGML 2.0 .gml")
    ap.add_argument("--output", required=True, help="Path to output .geojson")
    ap.add_argument(
        "--crs-fallback",
        default=os.environ.get("BFE_CITYGML_CRS"),
        help="CRS to record when srsName is missing on envelopes (e.g. EPSG:25832)",
    )
    args = ap.parse_args()

    tree = ET.parse(args.input)
    root = tree.getroot()

    ns = {
        "gml": "http://www.opengis.net/gml",
        "bldg": "http://www.opengis.net/citygml/building/2.0",
    }

    detected_crs: str | None = None
    features = []

    for building in root.findall(".//bldg:Building", ns):
        envelope = building.find(".//gml:Envelope", ns)
        if envelope is None:
            continue

        if detected_crs is None:
            detected_crs = envelope.get("srsName")

        lower = envelope.find("gml:lowerCorner", ns).text.split()
        upper = envelope.find("gml:upperCorner", ns).text.split()

        minx, miny = map(float, lower[:2])
        maxx, maxy = map(float, upper[:2])

        storeys_elem = building.find("bldg:storeysAboveGround", ns)
        storeys = int(storeys_elem.text) if storeys_elem is not None else None

        coords = [
            [
                [minx, miny],
                [maxx, miny],
                [maxx, maxy],
                [minx, maxy],
                [minx, miny],
            ]
        ]

        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": coords},
            "properties": {
                "id": building.get("{http://www.opengis.net/gml}id"),
                "storeysAboveGround": storeys,
            },
        })

    crs = detected_crs or args.crs_fallback
    geojson: dict = {"type": "FeatureCollection", "features": features}
    if crs:
        geojson["crs"] = {"type": "name", "properties": {"name": crs}}

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    print(f"Wrote {len(features)} features to {args.output}")


if __name__ == "__main__":
    main()
