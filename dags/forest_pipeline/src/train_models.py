import os
import joblib
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from airflow.providers.mysql.hooks.mysql import MySqlHook

from forest_pipeline.src.config import (
    MYSQL_CONN_ID,
    PROCESSED_TABLE,
    LOCAL_MODEL_DIR,
    TARGET_COLUMN,
)


def train_forest_models():
    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)
    engine = hook.get_sqlalchemy_engine()

    query = f"SELECT * FROM {PROCESSED_TABLE}"
    df = pd.read_sql(query, con=engine)

    if df.empty:
        raise ValueError(f"No hay datos en la tabla {PROCESSED_TABLE} para entrenar")

    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"La columna objetivo '{TARGET_COLUMN}' no existe en {PROCESSED_TABLE}")

    columns_to_drop = ["id", "group_id", "ingestion_ts", TARGET_COLUMN]
    existing_columns_to_drop = [col for col in columns_to_drop if col in df.columns]

    X = df.drop(columns=existing_columns_to_drop)
    y = df[TARGET_COLUMN]

    model = RandomForestClassifier(random_state=42)
    model.fit(X, y)

    os.makedirs(LOCAL_MODEL_DIR, exist_ok=True)
    model_path = os.path.join(LOCAL_MODEL_DIR, "forest_cover_random_forest.pkl")
    joblib.dump(model, model_path)

    print(f"Modelo entrenado y guardado en: {model_path}")