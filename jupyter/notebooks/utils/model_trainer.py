"""
Clase encargada de entrenar modelos, subirlos directamente a MinIO en memoria,
mostrar métricas visuales y actualizar el reporte CSV también en memoria.
No se escribe nada en disco local.
"""

import io
import joblib
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import boto3
from botocore.client import Config
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
)
from sklearn.pipeline import Pipeline


class ModelTrainer:
    """Entrena pipelines de sklearn, los persiste en MinIO (en memoria) y mantiene el reporte."""

    def __init__(
        self,
        minio_endpoint: str = None,
        minio_access_key: str = None,
        minio_secret_key: str = None,
        minio_bucket: str = "mlmodels",
        report_key: str = "model_metrics.csv",
    ):
        self.minio_bucket = minio_bucket
        self.report_key = report_key

        # Configurar cliente MinIO (S3)
        self.s3 = None
        if minio_endpoint:
            self.s3 = boto3.client(
                "s3",
                endpoint_url=f"http://{minio_endpoint}",
                aws_access_key_id=minio_access_key,
                aws_secret_access_key=minio_secret_key,
                config=Config(signature_version="s3v4"),
                region_name="us-east-1",
            )
            self._ensure_bucket()

    def _ensure_bucket(self):
        """Crea el bucket en MinIO si no existe."""
        try:
            existing = [b["Name"] for b in self.s3.list_buckets().get("Buckets", [])]
            if self.minio_bucket not in existing:
                self.s3.create_bucket(Bucket=self.minio_bucket)
                print(f"Bucket '{self.minio_bucket}' creado en MinIO")
        except Exception as e:
            print(f"ERROR al verificar/crear bucket: {e}")

    def train_and_save(self, name: str, estimator, X_train, X_test, y_train, y_test, scaler=None):
        """
        Construye un Pipeline, entrena, evalúa, muestra métricas,
        serializa en memoria y sube directamente a MinIO.

        Parámetros
        ----------
        name : str          Nombre del modelo (ej. 'randomforest').
        estimator :         Estimador de sklearn (sin entrenar).
        X_train, X_test :   Features.
        y_train, y_test :   Labels.
        scaler :            Transformador opcional (ej. StandardScaler()).

        Retorna
        -------
        dict con las métricas calculadas.
        """
        pipeline = self._build_pipeline(estimator, scaler)
        pipeline.fit(X_train, y_train)

        metrics = self._evaluate(pipeline, name, X_train, X_test, y_train, y_test)
        self._show_report(pipeline, name, X_test, y_test)

        # Serializar en memoria y subir a MinIO
        filename = f"{name.lower()}_model.pkl"
        if self.s3:
            self._upload_model_to_minio(pipeline, filename)

        # Actualizar reporte en MinIO (en memoria)
        self._update_report(metrics)

        return metrics

    def _build_pipeline(self, estimator, scaler=None) -> Pipeline:
        steps = []
        if scaler is not None:
            steps.append(("scaler", scaler))
        steps.append(("model", estimator))
        return Pipeline(steps)

    def _evaluate(self, pipeline, name, X_train, X_test, y_train, y_test) -> dict:
        y_train_pred = pipeline.predict(X_train)
        y_test_pred = pipeline.predict(X_test)
        return {
            "model": name.lower(),
            "train_accuracy": round(accuracy_score(y_train, y_train_pred), 4),
            "test_accuracy": round(accuracy_score(y_test, y_test_pred), 4),
            "test_precision": round(precision_score(y_test, y_test_pred, average="weighted", zero_division=0), 4),
            "test_recall": round(recall_score(y_test, y_test_pred, average="weighted", zero_division=0), 4),
            "test_f1": round(f1_score(y_test, y_test_pred, average="weighted", zero_division=0), 4),
        }

    def _show_report(self, pipeline, name, X_test, y_test):
        y_pred = pipeline.predict(X_test)

        print(f"\n{'='*50}")
        print(f"  {name} — Classification Report")
        print(f"{'='*50}")
        print(classification_report(y_test, y_pred, zero_division=0))

        cm = confusion_matrix(y_test, y_pred)
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
        plt.title(f"Matriz de Confusión — {name}")
        plt.ylabel("Valor Real")
        plt.xlabel("Predicción")
        plt.tight_layout()
        plt.show()

    def _upload_model_to_minio(self, pipeline, object_name: str):
        """Serializa el pipeline en memoria y lo sube a MinIO sin escribir en disco."""
        try:
            buffer = io.BytesIO()
            joblib.dump(pipeline, buffer)
            buffer.seek(0)
            self.s3.put_object(
                Bucket=self.minio_bucket,
                Key=object_name,
                Body=buffer.getvalue(),
            )
            print(f"Pipeline subido a MinIO: s3://{self.minio_bucket}/{object_name}")
        except Exception as e:
            print(f"ERROR al subir modelo a MinIO: {e}")

    def _update_report(self, metrics: dict):
        """
        Descarga el reporte CSV actual de MinIO (si existe), actualiza en memoria
        y lo vuelve a subir. No se escribe nada en disco.
        """
        if not self.s3:
            return

        # Intentar descargar el reporte existente
        df = pd.DataFrame()
        try:
            response = self.s3.get_object(Bucket=self.minio_bucket, Key=self.report_key)
            df = pd.read_csv(io.BytesIO(response["Body"].read()))
        except self.s3.exceptions.NoSuchKey:
            pass  # Primera vez, el reporte no existe aún
        except Exception:
            pass  # Si falla por cualquier otra razón, empezamos con df vacío

        # Reemplazar fila del modelo si ya existe
        model_name = metrics["model"]
        if not df.empty and "model" in df.columns:
            df = df[df["model"] != model_name]

        df = pd.concat([df, pd.DataFrame([metrics])], ignore_index=True)

        # Subir reporte actualizado a MinIO en memoria
        try:
            buffer = io.BytesIO()
            df.to_csv(buffer, index=False)
            buffer.seek(0)
            self.s3.put_object(
                Bucket=self.minio_bucket,
                Key=self.report_key,
                Body=buffer.getvalue(),
            )
            print(f"Reporte actualizado en MinIO: s3://{self.minio_bucket}/{self.report_key}")
        except Exception as e:
            print(f"ERROR al subir reporte a MinIO: {e}")
