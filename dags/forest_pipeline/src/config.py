MYSQL_CONN_ID = "mysql_default"

RAW_TABLE = "raw_forest_cover"
PROCESSED_TABLE = "processed_forest_cover"
BATCH_LOG_TABLE = "batch_log"

# Columnas numéricas continuas (índices 0-9)
CONTINUOUS_COLUMNS = [
    "elevation",
    "aspect",
    "slope",
    "horizontal_distance_to_hydrology",
    "vertical_distance_to_hydrology",
    "horizontal_distance_to_roadways",
    "hillshade_9am",
    "hillshade_noon",
    "hillshade_3pm",
    "horizontal_distance_to_fire_points",
]

# Nombres de las áreas wilderness (one-hot, índices 10-13)
WILDERNESS_AREAS = ["Rawah", "Neota", "Comanche Peak", "Cache la Poudre"]

# Nombres de los tipos de suelo (one-hot, índices 14-53)
SOIL_TYPES = [f"C{i}" for i in range(1, 41)]

# Columnas raw tal como vienen de la API (55 columnas one-hot)
RAW_COLUMNS = (
    CONTINUOUS_COLUMNS
    + [f"wilderness_area_{w.lower().replace(' ', '_')}" for w in WILDERNESS_AREAS]
    + [f"soil_type_{s.lower()}" for s in SOIL_TYPES]
    + ["cover_type"]
)

API_BASE_URL = "http://host.docker.internal:8090"
GROUP_ID = "5"

API_TIMEOUT = 30