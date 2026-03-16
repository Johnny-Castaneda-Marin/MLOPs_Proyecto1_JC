import pandas as pd
from airflow.providers.mysql.hooks.mysql import MySqlHook

from forest_pipeline.src.config import (
    CONTINUOUS_COLUMNS,
    MYSQL_CONN_ID,
    PROCESSED_TABLE,
    RAW_TABLE,
    SOIL_TYPES,
    WILDERNESS_AREAS,
)

# Columnas one-hot en el orden en que vienen de la API
_WILDERNESS_COLS = [f"wilderness_area_{w.lower().replace(' ', '_')}" for w in WILDERNESS_AREAS]
_SOIL_COLS = [f"soil_type_{s.lower()}" for s in SOIL_TYPES]


def _decode_onehot(df: pd.DataFrame) -> pd.DataFrame:
    """Decodifica las columnas one-hot de wilderness_area y soil_type a valores categóricos.

    Elimina las 44 columnas one-hot y agrega wilderness_area (str) y soil_type (str).
    """
    df["wilderness_area"] = (
        df[_WILDERNESS_COLS]
        .idxmax(axis=1)
        .str.replace("wilderness_area_", "", regex=False)
    )
    df["soil_type"] = (
        df[_SOIL_COLS]
        .idxmax(axis=1)
        .str.replace("soil_type_", "", regex=False)
    )
    df = df.drop(columns=_WILDERNESS_COLS + _SOIL_COLS)
    return df


def preprocess_forest_cover() -> None:
    """Lee el último batch de raw_forest_cover, decodifica one-hot y guarda en processed_forest_cover."""
    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)
    engine = hook.get_sqlalchemy_engine()

    # Leer solo el batch más reciente (mismo ingestion_ts máximo)
    query = f"""
        SELECT * FROM {RAW_TABLE}
        WHERE ingestion_ts = (SELECT MAX(ingestion_ts) FROM {RAW_TABLE})
    """
    df = pd.read_sql(query, con=engine)

    if df.empty:
        raise ValueError(f"No hay datos nuevos en {RAW_TABLE} para procesar.")

    # Eliminar columna id generada por MySQL
    if "id" in df.columns:
        df = df.drop(columns=["id"])

    # Decodificar one-hot → columnas categóricas
    df = _decode_onehot(df)

    # Columnas finales: continuas + wilderness_area + soil_type + cover_type + metadatos
    processed_cols = CONTINUOUS_COLUMNS + ["wilderness_area", "soil_type", "cover_type", "group_id", "ingestion_ts"]
    df = df[processed_cols]

    df.to_sql(name=PROCESSED_TABLE, con=engine, if_exists="append", index=False)

    print(f"Se procesaron {len(df)} registros y se insertaron en {PROCESSED_TABLE}.")
