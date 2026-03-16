from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator

from forest_pipeline.src.extract_raw_forest_cover import extract_raw_forest_cover
from forest_pipeline.src.preprocess_forest_cover import preprocess_forest_cover


with DAG(
    dag_id="forest_cover_pipeline",
    description="Pipeline de ingesta, procesamiento, entrenamiento y publicación para forest cover",
    start_date=datetime(2026, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["mlops", "forest-cover", "api"],
) as dag:

    extract_raw_data = ShortCircuitOperator(
        task_id="extract_raw_data",
        python_callable=extract_raw_forest_cover,
    )

    preprocess_data = PythonOperator(
        task_id="preprocess_data",
        python_callable=preprocess_forest_cover,
    )

    extract_raw_data >> preprocess_data
