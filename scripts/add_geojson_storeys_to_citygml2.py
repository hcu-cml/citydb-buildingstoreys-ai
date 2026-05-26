import getpass
import json
import logging
import os
import sys
import time
from datetime import datetime

import psycopg2
from psycopg2.extras import execute_values

# Define paths
log_path = "logs/run.log"
geojson_path = "INPUT_GEOJSON_FROM_CITYGML.geojson"

# Init logging
# Check if run.log exists
if os.path.exists(log_path):
    # Rename it with a timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    os.rename(log_path, f'run_{timestamp}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler(sys.stdout)  # This prints to console too
    ]
)
start_time = time.time()

# Load GeoJSON
with open(geojson_path, "r", encoding="utf-8") as f:
    data = json.load(f)
features = data.get("features", [])

# Prepare list of (objectid, predicted_floors)
records = []
for feature in features:
    props = feature.get("properties", {})
    objectid = props.get("id")  # GeoJSON field "id"
    predicted_floors = props.get("predicted_floors")
    if objectid is not None and predicted_floors is not None:
        records.append((objectid, predicted_floors))
logging.info(f"Loaded {len(records)} buildings with predicted floors, from a total of {len(features)} buildings")

# Connect to an existing database
logging.info('Connect to database')
dbname = 'heidelberg_center_citygml2_lod2_2025_citydb5'
user = 'postgres'
password = input("Enter database password: ")
host = 'localhost'
port = '5432'
db_credentials = f"dbname={dbname} user={user} password={password} host={host} port={port}"
with psycopg2.connect(db_credentials) as conn:
    # Open a cursor to perform database operations
    with conn.cursor() as cur:

        # Create id index if not exists
        logging.info('Initialize id index (if not exists)')
        cur.execute("""
                    CREATE INDEX IF NOT EXISTS feature_objectid_inx
                        ON feature
                        USING btree (objectid)
                        WITH (fillfactor = 100, deduplicate_items = true);
                    """)
        conn.commit()

        # Prepare data
        params = [(predicted_floors, objectid, predicted_floors, objectid) for objectid, predicted_floors in records]

        # SQL statements
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

        # Execute updates first
        for predicted_floors, objectid, _, _ in params:
            cur.execute(update_sql, (predicted_floors, objectid))

        # Execute inserts for missing rows
        for _, _, predicted_floors, objectid in params:
            cur.execute(insert_sql, (predicted_floors, objectid))

        # Commit and report
        conn.commit()
        logging.info(f"Processed {len(records)} records in citydb.property")
        cur.close()

end_time = time.time()
duration = end_time - start_time
logging.info(f"Finished in {duration:.3f} seconds")
