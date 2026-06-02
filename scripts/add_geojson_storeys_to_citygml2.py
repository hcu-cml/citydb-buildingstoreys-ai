import argparse
import getpass
import json
import logging
import os
import sys
import time
from datetime import datetime

import psycopg2


def _get_password() -> str:
    pw = os.environ.get("BFE_CITYDB_PASSWORD") or os.environ.get("PGPASSWORD")
    if pw:
        return pw
    return getpass.getpass("Enter database password: ")


def _build_dsn() -> str:
    if dsn := os.environ.get("BFE_CITYDB_DSN"):
        return dsn
    return (
        f"dbname={os.environ['PGDATABASE']} "
        f"user={os.environ.get('PGUSER', 'postgres')} "
        f"password={_get_password()} "
        f"host={os.environ.get('PGHOST', 'localhost')} "
        f"port={os.environ.get('PGPORT', '5432')}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="GeoJSON -> citydb storeysAboveGround")
    ap.add_argument("--input", required=True, help="Path to stage 3 GeoJSON")
    ap.add_argument("--log", default="logs/run.log", help="Path to log file")
    args = ap.parse_args()

    log_path = args.log
    geojson_path = args.input

    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    if os.path.exists(log_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.rename(log_path, f"{os.path.splitext(log_path)[0]}_{timestamp}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stdout),
        ],
    )
    start_time = time.time()

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])

    records = []
    for feature in features:
        props = feature.get("properties", {})
        objectid = props.get("id")
        predicted_floors = props.get("predicted_floors")
        if objectid is not None and predicted_floors is not None:
            records.append((objectid, predicted_floors))
    logging.info(
        "Loaded %d buildings with predicted floors out of %d total",
        len(records), len(features),
    )

    n_updates = 0
    n_inserts = 0
    with psycopg2.connect(_build_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS feature_objectid_inx
                    ON feature
                    USING btree (objectid)
                    WITH (fillfactor = 100, deduplicate_items = true);
                """
            )
            conn.commit()

            update_sql = """
            UPDATE citydb.property p
            SET val_int = %s
            FROM citydb.feature f
            WHERE p.feature_id = f.id
              AND f.objectid = %s
              AND p.name = 'storeysAboveGround'
              AND p.val_int IS NULL;
            """

            insert_sql = """
            INSERT INTO citydb.property (feature_id, datatype_id, namespace_id, name, val_int)
            SELECT f.id, 3, 10, 'storeysAboveGround', %s
            FROM citydb.feature f
            LEFT JOIN citydb.property p
              ON p.feature_id = f.id AND p.name = 'storeysAboveGround'
            WHERE f.objectid = %s
              AND p.feature_id IS NULL;
            """

            for objectid, predicted_floors in records:
                cur.execute(update_sql, (predicted_floors, objectid))
                n_updates += max(cur.rowcount, 0)

            for objectid, predicted_floors in records:
                cur.execute(insert_sql, (predicted_floors, objectid))
                n_inserts += max(cur.rowcount, 0)

            conn.commit()
            logging.info("Processed %d records in citydb.property", len(records))

    duration = time.time() - start_time
    logging.info("Finished in %.3f seconds", duration)
    logging.info(
        "STORE_RESULTS %s",
        json.dumps({
            "n_records": len(records),
            "n_updates": n_updates,
            "n_inserts": n_inserts,
            "duration_s": round(duration, 3),
        }),
    )


if __name__ == "__main__":
    main()
