## Domain-Adaptive Object Detection for Enriching Semantic 3D City Models with Building Storeys from Street-View Images

This repository contains the source code, links to the datasets used and generated, and additional technical details related to our work. We present an end-to-end pipeline for the automatic estimation of building storeys to semantically enrich 3D city models. Our approach uses volunteered geographic information in the form of street-view imagery from Mapillary and applies a COCO-pretrained object detection model to identify windows in façade images as key visual indicators for estimating building storey counts. The detection pipeline is based on the YOLOv3 architecture and combines clustering methods such as Gaussian Mixtures and DBSCAN to infer the number of storeys. The resulting estimates enable the automatic augmentation of CityGML-based 3D city models by filling in missing semantic attributes.

<img width="3840" height="2160" alt="Son_3DModels_3" src="https://github.com/user-attachments/assets/19b2af69-3023-4574-8c11-6fe6c48fd60a" />


## Inputs to run or retrain the pipeline:

The following sections describe the input data required to run the end-to-end pipeline for estimating the number of storeys from street-view imagery.

### Building footprints

- **LoD2 CityGML-derived GeoJSON (Germany).** Many German state
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

## Window detector

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

The stack is split across two compose profiles so the lightweight pipeline
doesn't pull the citydb images unless you need them:

- `pipeline`  - the bfe container running stages 0–5 (volumes:
  `./configs`, `./data`, `./models` read-only, `./outputs` read-write).
- `citydb`    - 3DCityDB v5 Postgres + citydb-tool + a 3DCityDB Web Map
  Client viewer + nginx for serving the 3D Tiles. Required for stages 4
  and 5 (citydb enrichment + tile export).

End-to-end, including building image, citydb import, enrichment, tile
export, and viewer:

```bash
./scripts/run_pipeline.sh heidelberg
```

Then open:
- Cesium viewer: <http://localhost:8000>
- 3D Tiles:      <http://localhost:8080/tiles/tileset.json>
- Run browser:   <http://localhost:8080/outputs/>

GPU inference is possible by switching the base image to an `nvidia/cuda`
runtime; see comments in the `Dockerfile`.



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
bfe extract   --config configs/heidelberg.yaml   # CityGML -> footprints.geojson
bfe fetch     --config configs/heidelberg.yaml   # Mapillary
bfe detect    --config configs/heidelberg.yaml   # YOLO
bfe merge     --config configs/heidelberg.yaml   # join predictions onto footprints
bfe enrich    --config configs/heidelberg.yaml   # write storeys into citydb
bfe visualize --config configs/heidelberg.yaml   # 3D Tiles + viewer config
```

### Docker

```bash
./scripts/run_pipeline.sh configs/heidelberg.yaml
# or:
docker compose run --rm pipeline bfe pipeline --config /app/configs/heidelberg.yaml
```

## Troubleshooting

If the code is not working for you or you run into problems, please
[open an issue](https://github.com/hcu-cml/citydb-buildingstoreys-ai/issues)
with your config, the command you ran, and the tail of the log.



## Citation

If you use this code, please cite:

```bibtex
@Article{citydb-buildingstoreys-ai,
	author = {Lukas Arzoumanidis and Al Maimun As Samee and Elmehdi Kanna and Son Nguyen and Youness Dehbi},
	title = {Domain-Adaptive Object Detection for Enriching Semantic 3D City Models with Building Storeys from Street-View Images},
	year = {2026},
  journal = {ISPRS Annals of the Photogrammetry, Remote Sensing and Spatial Information Sciences},
	booktitle = {ISPRS Congress 2026 Toronto, Canada},
	url = {https://repos.hcu-hamburg.de/handle/hcu/1248},
}
```
