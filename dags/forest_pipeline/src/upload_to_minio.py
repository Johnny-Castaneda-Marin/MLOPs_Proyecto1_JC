import os

from minio import Minio
from minio.error import S3Error

from forest_pipeline.src.config import (
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_BUCKET,
    LOCAL_MODEL_DIR,
)


def upload_model_to_minio():
    client = Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )

    bucket_name = MINIO_BUCKET
    model_filename = "forest_cover_random_forest.pkl"
    model_path = os.path.join(LOCAL_MODEL_DIR, model_filename)

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"No existe el modelo en la ruta: {model_path}")

    found = client.bucket_exists(bucket_name)
    if not found:
        client.make_bucket(bucket_name)
        print(f"Bucket creado: {bucket_name}")
    else:
        print(f"Bucket ya existe: {bucket_name}")

    client.fput_object(
        bucket_name,
        model_filename,
        model_path,
    )

    print(f"Modelo subido a MinIO: {bucket_name}/{model_filename}")