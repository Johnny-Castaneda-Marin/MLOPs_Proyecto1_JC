import io
import os

import boto3
import joblib
import pandas as pd
from botocore.client import Config


MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minio_user")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minio1234")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "mlmodels")
REPORT_KEY = "model_metrics.csv"

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


def discover_models() -> dict:
    """Lista los modelos .pkl disponibles directamente en MinIO."""
    models = {}
    try:
        s3 = _get_s3_client()
        response = s3.list_objects_v2(Bucket=MINIO_BUCKET)
        for obj in response.get("Contents", []):
            key = obj["Key"]
            if key.endswith("_model.pkl") or key.endswith("_pipeline.pkl"):
                name = key.replace("_pipeline.pkl", "").replace("_model.pkl", "").lower()
                models[name] = key  # guardamos la key de MinIO, no una ruta local
    except Exception as e:
        print(f"Error listando modelos en MinIO: {e}")
    return models


def load_model(minio_key: str):
    """Descarga y deserializa un modelo desde MinIO en memoria."""
    s3 = _get_s3_client()
    response = s3.get_object(Bucket=MINIO_BUCKET, Key=minio_key)
    buffer = io.BytesIO(response["Body"].read())
    return joblib.load(buffer)


def load_metrics() -> dict:
    """Descarga y parsea el reporte CSV de métricas desde MinIO."""
    try:
        s3 = _get_s3_client()
        response = s3.get_object(Bucket=MINIO_BUCKET, Key=REPORT_KEY)
        df = pd.read_csv(io.BytesIO(response["Body"].read()))
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
    except Exception:
        return {}


def is_pipeline(model):
    """Detecta si el modelo cargado es un Pipeline de sklearn."""
    return hasattr(model, "steps")
