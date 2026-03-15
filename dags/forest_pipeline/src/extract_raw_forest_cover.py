from datetime import datetime

import pandas as pd
import requests
from airflow.providers.mysql.hooks.mysql import MySqlHook

from forest_pipeline.src.config import (
    MYSQL_CONN_ID,
    RAW_TABLE,
    GROUP_ID,
    API_BASE_URL,
    API_TIMEOUT,
    USE_API_SOURCE,
)


def _get_dummy_data():
    return pd.DataFrame(
        [
            {
                "elevation": 2500,
                "aspect": 120,
                "slope": 15,
                "horizontal_distance_to_hydrology": 300,
                "vertical_distance_to_hydrology": 20,
                "horizontal_distance_to_roadways": 1500,
                "hillshade_9am": 220,
                "hillshade_noon": 230,
                "hillshade_3pm": 180,
                "horizontal_distance_to_fire_points": 1200,
                "cover_type": 2,
                "group_id": GROUP_ID,
                "ingestion_ts": datetime.now(),
            }
        ]
    )


def _get_api_data():
    """
    Placeholder para la API real.
    Cuando tengamos endpoint y formato exacto, aquí se reemplaza la lógica.
    """
    url = f"{API_BASE_URL}"
    response = requests.get(url, timeout=API_TIMEOUT)
    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = pd.DataFrame([data])

    df["group_id"] = GROUP_ID
    df["ingestion_ts"] = datetime.now()

    return df


def extract_raw_forest_cover():
    if USE_API_SOURCE:
        df = _get_api_data()
        print("Fuente usada: API")
    else:
        df = _get_dummy_data()
        print("Fuente usada: dummy")

    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)
    engine = hook.get_sqlalchemy_engine()

    df.to_sql(
        name=RAW_TABLE,
        con=engine,
        if_exists="append",
        index=False,
    )

    print(f"Se insertaron {len(df)} registros en {RAW_TABLE}")