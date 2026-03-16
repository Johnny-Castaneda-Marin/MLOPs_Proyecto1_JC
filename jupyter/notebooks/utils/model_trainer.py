"""
Clase encargada de entrenar modelos, guardarlos localmente y en MinIO,
mostrar métricas visuales y actualizar el reporte.
"""

import os
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
    """Entrena pipelines de sklearn, los persiste local y en MinIO, y mantiene el reporte."""

    def __init__(
        self,
        models_dir: str = "/app/models",
        report_path: str = "/app/report/model_metrics.csv",
        minio_endpoint: str = None,
        minio_access_key: str = None,
        minio_secret_key: str = None,
        minio_bucket: str = "mlmodels",
    ):
        self.models_dir = models_dir
        self.report_path = report_path
        self.minio_bucket = minio_bucket
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(os.path.dirname(report_path), exist_ok=True)

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

    def train_and_save(self, name: str, estimator, X_train, X_test, y_train, y_test, scaler=None):
        """
        Construye un Pipeline, entrena, evalúa, muestra métricas,
        guarda el pipeline local y en MinIO, y actualiza el reporte CSV.

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

        # Guardar pipeline localmente
        filename = f"{name.lower()}_model.pkl"
        model_path = os.path.join(self.models_dir, filename)
        joblib.dump(pipeline, model_path)
        print(f"\nPipeline '{name}' guardado en {model_path}")

        # Subir a MinIO
        if self.s3:
            self._upload_to_minio(model_path, filename)

        # Actualizar reporte
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
            "test_precision": round(precision_score(y_test, y_test_pred, average="weighted"), 4),
            "test_recall": round(recall_score(y_test, y_test_pred, average="weighted"), 4),
            "test_f1": round(f1_score(y_test, y_test_pred, average="weighted"), 4),
        }

    def _show_report(self, pipeline, name, X_test, y_test):
        y_pred = pipeline.predict(X_test)

        print(f"\n{'='*50}")
        print(f"  {name} — Classification Report")
        print(f"{'='*50}")
        print(classification_report(y_test, y_pred))

        cm = confusion_matrix(y_test, y_pred)
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")
        plt.title(f"Matriz de Confusión — {name}")
        plt.ylabel("Valor Real")
        plt.xlabel("Predicción")
        plt.tight_layout()
        plt.show()

    def _upload_to_minio(self, local_path: str, object_name: str):
        """Sube el archivo a MinIO, creando el bucket si no existe."""
        try:
            existing = [b["Name"] for b in self.s3.list_buckets().get("Buckets", [])]
            if self.minio_bucket not in existing:
                self.s3.create_bucket(Bucket=self.minio_bucket)
                print(f"Bucket '{self.minio_bucket}' creado en MinIO")

            self.s3.upload_file(local_path, self.minio_bucket, object_name)
            print(f"Pipeline subido a MinIO: s3://{self.minio_bucket}/{object_name}")
        except Exception as e:
            print(f"ERROR al subir a MinIO: {e}")

    def _update_report(self, metrics: dict):
        """Actualiza el reporte CSV de métricas (reemplaza si el modelo ya existe)."""
        if os.path.exists(self.report_path):
            df = pd.read_csv(self.report_path)
        else:
            df = pd.DataFrame()

        model_name = metrics["model"]
        if not df.empty and "model" in df.columns:
            df = df[df["model"] != model_name]

        df = pd.concat([df, pd.DataFrame([metrics])], ignore_index=True)
        df.to_csv(self.report_path, index=False)
        print(f"Reporte actualizado en {self.report_path}")
