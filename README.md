

## Repository layout

```
citydb-buildingstoreys-ai/
  configs/           YAML configurations (heidelberg.yaml, osm_example.yaml)
  src/bfe/           Python package
  scripts/           Helper shell scripts
  data/              User-supplied inputs (gitignored)
  models/            User-supplied YOLO weights (gitignored)
  outputs/           Pipeline outputs (gitignored)
  Dockerfile
  docker-compose.yml
  pyproject.toml
```

## Inputs

### Building footprints

Configure `footprint.kind` to `file` or `osm`.

- **LoD2/LoD3 CityGML-derived GeoJSON (Germany).** Many German state
  geoportals publish CityGML building models that can be exported to
  GeoJSON. These exports commonly use `EPSG:25832` (ETRS89 / UTM zone 32N)
  and carry a `storeysAboveGround` attribute that is used as ground truth
  for comparison. Place the file under `data/` and point `footprint.path`
  to it.
- **OpenStreetMap.** With `footprint.kind: osm`, building polygons inside
  the configured bounding box are downloaded via `osmnx`. Where available,
  the OSM tag `building:levels` is used as the ground-truth column.

### Street-level imagery

Mapillary images are retrieved via the Graph API. You must supply your own
access token (see below). No credentials are stored in the repository.

### Window detector

The pipeline uses a YOLOv3 checkpoint loaded through Ultralytics
(`ultralytics.YOLO("best.pt")`). Drop the `.pt` file into `models/` or
point `detector.weights` in the config at its absolute path. Weights are
not committed to the repository.

The trained weights from the paper are hosted on Google Drive:

- **Download (Google Drive folder):**
  <https://drive.google.com/drive/folders/17BlwpqpKUwgf6vGese7AdXQs4w4OxE6v?usp=sharing>

Open the link in a browser, download `best.pt`, and place it at
`models/best.pt` (or point `detector.weights` in your config to its path).


```

## Installation

### Local (Python 3.10+)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

### Docker

```bash
cp .env.example .env             # then edit .env and set MAPILLARY_ACCESS_TOKEN
docker compose build
```

The image bind-mounts `./configs`, `./data`, `./models` (read-only) and
`./outputs` (read-write). GPU inference is possible by switching the base
image to an `nvidia/cuda` runtime; see comments in the `Dockerfile`.

## Configuration

A minimal YAML config looks like:

```yaml
project: heidelberg

footprint:
  kind: file
  path: ../data/Heidelberg_Center_Buildings_Storeys_CityGML_2025.geojson
  crs: EPSG:25832
  id_field: id
  height_field: storeysAboveGround

mapillary:
  bbox:
    min_lon: 8.627700
    min_lat: 49.310153
    max_lon: 8.738668
    max_lat: 49.437231
  grid_divisions: 4
  search_radius_m: 150.0
  bearing_tolerance_deg: 90.0

detector:
  weights: ../models/best.pt

floor_estimator:
  min_windows: 8
  max_floors: 5
  avg_floor_height_m: 2.5

outputs:
  root: ../outputs
```

Full reference: `configs/heidelberg.yaml`, `configs/osm_example.yaml`, and
the pydantic models in `src/bfe/config.py`.

## Running

Export your Mapillary token:

```bash
export MAPILLARY_ACCESS_TOKEN=...    # or put it in .env for Docker
```

### Local

```bash
bfe pipeline --config configs/heidelberg.yaml
# or stage by stage:
bfe fetch   --config configs/heidelberg.yaml
bfe detect  --config configs/heidelberg.yaml
bfe merge   --config configs/heidelberg.yaml
```

### Docker

```bash
./scripts/run_pipeline.sh configs/heidelberg.yaml
# or:
docker compose run --rm pipeline bfe pipeline --config /app/configs/heidelberg.yaml
```

## Outputs

Each run writes a timestamped directory:

```
outputs/<project>/<run_id>/
  manifest.json
  stage1_fetch/
    mapillary_metadata.parquet
    images/<building_id>_<idx>.jpg
  stage2_detect/
    predictions.parquet
    annotated/<building_id>_<idx>.jpg
  stage3_merge/
    buildings_with_predictions.geojson
    buildings_with_predictions.csv
    summary.json
    predicted_floors_distribution.png
```

`summary.json` reports total and matched building counts, the predicted
storey distribution, truncation counts at `max_floors`, and (when a
ground-truth height field exists) mean/median absolute error and RMSE
against it.

## Limitations

- Floor estimation assumes a facade with reasonably regular window rows.
  The published method caps predictions at `max_floors` (default 5);
  truncated buildings are flagged in `summary.json` but reported at the
  cap. Raise `max_floors` for mid- and high-rise neighborhoods.
- Mapillary coverage is uneven. Buildings without a matching image are
  returned with null predictions rather than being dropped.
- Distances are computed on a spherical Earth. This is adequate at city
  scale but not for high-precision geodesy.

## Troubleshooting

If the code is not working for you or you run into problems, please
[open an issue](https://github.com/hcu-cml/citydb-buildingstoreys-ai/issues)
with your config, the command you ran, and the tail of the log.

## License

MIT. See `LICENSE`.

## Citation

If you use this code, please cite:

```bibtex
@Article{isprs-annals-X-,
  AUTHOR  = {Arzoumanidis, L. and As Samee, A.M. and Kanna, E. and Nguyen, S. H. and Dehbi, Y.},
  TITLE   = {Domain-Adaptive Object Detection for Enriching Semantic 3D City Models with Building Storeys from Street-View Images},
  JOURNAL = {ISPRS Annals of the Photogrammetry, Remote Sensing and Spatial Information Sciences},
  VOLUME  = {},
  YEAR    = {2026},
  PAGES   = {},
  DOI     = {}
}
```
