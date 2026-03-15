MYSQL_CONN_ID = "mysql_default"

RAW_TABLE = "raw_forest_cover"
PROCESSED_TABLE = "processed_forest_cover"
TRAINING_TABLE = "training_ready_forest_cover"
MODEL_REGISTRY_TABLE = "model_registry"

API_BASE_URL = "http://10.43.101.94:8080"
GROUP_ID = "5"

MINIO_ENDPOINT = "minio:9000"
MINIO_ACCESS_KEY = "minio_user"
MINIO_SECRET_KEY = "minio_password"
MINIO_BUCKET = "mlmodels"

LOCAL_MODEL_DIR = "/opt/airflow/models"

TARGET_COLUMN = "cover_type"

USE_API_SOURCE = False
API_TIMEOUT = 30