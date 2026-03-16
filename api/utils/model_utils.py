import os
import glob

import boto3
import joblib
import pandas as pd
from botocore.client import Config


MODELS_DIR = os.environ.get("MODELS_DIR", "/app/models")
REPORT_PATH = os.path.join(MODELS_DIR, "model_metrics.csv")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minio_user")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minio1234")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "mlmodels")

COVER_TYPE_MAP = {
    1: "Spruce/Fir",
    2: "Lodgepole Pine",
    3: "Ponderosa Pine",
    4: "Cottonwood/Willow",
    5: "Aspen",
    6: "Douglas-fir",
    7: "Krummholz",
}


def _get_s3_client():
    """Crea un cliente S3 apuntando a MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def sync_from_minio():
    """Descarga todos los .pkl y el reporte CSV desde MinIO a MODELS_DIR."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    try:
        s3 = _get_s3_client()
        response = s3.list_objects_v2(Bucket=MINIO_BUCKET)
        for obj in response.get("Contents", []):
            key = obj["Key"]
            # Usar solo el nombre del archivo, ignorar subdirectorios en MinIO
            filename = os.path.basename(key)
            local_path = os.path.join(MODELS_DIR, filename)
            s3.download_file(MINIO_BUCKET, key, local_path)
            print(f"Descargado: {key} → {local_path}")
    except Exception as e:
        print(f"Error sincronizando desde MinIO: {e}")


def discover_models():
    """Descubre dinámicamente los modelos .pkl disponibles en disco."""
    models = {}
    for pattern in ["*_pipeline.pkl", "*_model.pkl"]:
        for path in glob.glob(os.path.join(MODELS_DIR, pattern)):
            filename = os.path.basename(path)
            name = filename.replace("_pipeline.pkl", "").replace("_model.pkl", "").lower()
            if name not in models:
                models[name] = path
    return models


def load_model(path):
    """Carga un modelo serializado desde disco."""
    return joblib.load(path)


def load_metrics() -> dict:
    """Carga el reporte CSV de métricas si existe."""
    if os.path.exists(REPORT_PATH):
        df = pd.read_csv(REPORT_PATH)
        return {
            row["model"]: {
                "train_accuracy": row["train_accuracy"],
                "test_accuracy": row["test_accuracy"],
                "test_precision": row["test_precision"],
                "test_recall": row["test_recall"],
                "test_f1": row["test_f1"],
            }
            for _, row in df.iterrows()
        }
    return {}


def is_pipeline(model):
    """Detecta si el modelo cargado es un Pipeline de sklearn."""
    return hasattr(model, "steps")
