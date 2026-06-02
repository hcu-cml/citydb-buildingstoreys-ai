-- Build the materialized view consumed by pg2b3dm:
--   one row per Building/BuildingPart, geometry as MultiPolygon (Z),
--   floors as the most recent storeysAboveGround value (or 0 when unknown),
--   each building grounded so its lowest vertex sits at z=0 (so a viewer
--   without world terrain can render the buildings flush on the ellipsoid).
DROP MATERIALIZED VIEW IF EXISTS citydb.bfe_buildings CASCADE;
CREATE MATERIALIZED VIEW citydb.bfe_buildings AS
WITH props AS (
  SELECT feature_id,
         MAX(CASE WHEN name='storeysAboveGround' THEN val_int END) AS storeys
    FROM citydb.property
   GROUP BY feature_id
),
exploded AS (
  SELECT feature_id, (ST_Dump(geometry)).geom AS poly
    FROM citydb.geometry_data
   WHERE GeometryType(geometry) IN ('POLYHEDRALSURFACE','TIN','POLYGON','MULTIPOLYGON')
),
agg AS (
  SELECT feature_id,
         ST_SetSRID(ST_Multi(ST_Collect(poly)), 25832) AS geom
    FROM exploded
   WHERE GeometryType(poly) = 'POLYGON'
   GROUP BY feature_id
),
grounded AS (
  SELECT feature_id,
         ST_Translate(geom, 0, 0, -ST_ZMin(geom)) AS geom
    FROM agg
)
SELECT f.id,
       f.objectid AS gml_id,
       COALESCE(p.storeys, 0) AS floors,
       g.geom
  FROM citydb.feature f
  JOIN grounded g ON g.feature_id = f.id
  LEFT JOIN props p ON p.feature_id = f.id
 WHERE f.objectclass_id IN (901, 902);
CREATE INDEX bfe_buildings_geom_gix ON citydb.bfe_buildings USING gist(geom);
ANALYZE citydb.bfe_buildings;
