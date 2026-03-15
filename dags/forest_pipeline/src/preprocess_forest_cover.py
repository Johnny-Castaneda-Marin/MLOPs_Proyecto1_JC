import pandas as pd
from airflow.providers.mysql.hooks.mysql import MySqlHook

from forest_pipeline.src.config import MYSQL_CONN_ID, RAW_TABLE, PROCESSED_TABLE


def preprocess_forest_cover():
    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)
    engine = hook.get_sqlalchemy_engine()

    query = f"SELECT * FROM {RAW_TABLE}"
    df = pd.read_sql(query, con=engine)

    if df.empty:
        raise ValueError(f"No hay datos en la tabla {RAW_TABLE} para procesar")

    df["elevation_scaled"] = df["elevation"] / 1000.0
    df["slope_scaled"] = df["slope"] / 100.0
    df["hydrology_distance_ratio"] = df["vertical_distance_to_hydrology"] / (
        df["horizontal_distance_to_hydrology"] + 1
    )

    if "id" in df.columns:
        df = df.drop(columns=["id"])

    df.to_sql(
        name=PROCESSED_TABLE,
        con=engine,
        if_exists="append",
        index=False,
    )

    print(f"Se insertaron {len(df)} registros en {PROCESSED_TABLE}")