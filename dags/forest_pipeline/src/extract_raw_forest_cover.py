from datetime import datetime

import pandas as pd
import requests
from airflow.providers.mysql.hooks.mysql import MySqlHook

from forest_pipeline.src.config import (
    API_BASE_URL,
    API_TIMEOUT,
    BATCH_LOG_TABLE,
    GROUP_ID,
    MYSQL_CONN_ID,
    RAW_COLUMNS,
    RAW_TABLE,
)


def _get_api_data() -> dict:
    """Llama a la API con group_number y retorna el dict JSON
    con las claves group_number, batch_number y data."""
    url = f"{API_BASE_URL}/data?group_number={GROUP_ID}"
    response = requests.get(url, timeout=API_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _batch_already_loaded(hook: MySqlHook, batch_number: int, group_number: int) -> bool:
    """Consulta batch_log y retorna True si el batch ya existe, False en caso contrario."""
    sql = f"SELECT COUNT(*) FROM {BATCH_LOG_TABLE} WHERE batch_number = %s AND group_number = %s"
    result = hook.get_first(sql, parameters=(batch_number, group_number))
    return result[0] > 0


def _map_batch_to_dataframe(data: list, group_number: int) -> pd.DataFrame:
    """Convierte una lista de filas con 55 columnas one-hot a un DataFrame tipado.

    Estructura esperada de cada fila (55 elementos):
      - Índices  0-9  : columnas continuas (CONTINUOUS_COLUMNS)
      - Índices 10-13 : one-hot wilderness_area (WILDERNESS_AREAS)
      - Índices 14-53 : one-hot soil_type (SOIL_TYPES)
      - Índice  54    : cover_type

    Lanza ValueError si alguna fila no tiene exactamente 55 elementos.
    """
    expected = len(RAW_COLUMNS)  # 55
    for i, row in enumerate(data):
        if len(row) != expected:
            raise ValueError(f"Fila {i} tiene {len(row)} elementos, se esperaban {expected}.")

    df = pd.DataFrame(data, columns=RAW_COLUMNS)
    df = df.astype(int)

    df["group_id"] = str(group_number)
    df["ingestion_ts"] = datetime.now()

    return df


def _log_batch(hook: MySqlHook, batch_number: int, group_number: int, record_count: int) -> None:
    """Inserta un registro en batch_log con loaded_at = datetime.now()."""
    sql = f"""
        INSERT INTO {BATCH_LOG_TABLE} (batch_number, group_number, record_count, loaded_at)
        VALUES (%s, %s, %s, %s)
    """
    hook.run(sql, parameters=(batch_number, group_number, record_count, datetime.now()))


def extract_raw_forest_cover() -> bool:
    """Punto de entrada del PythonOperator de Airflow.
    
    Retorna True si se insertaron datos nuevos, False si el batch ya existía.
    """
    # Paso 1: Obtener datos de la API
    response = _get_api_data()
    batch_number = response["batch_number"]
    group_number = response["group_number"]
    data = response["data"]

    # Paso 2: Verificar si el batch ya fue cargado
    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)
    if _batch_already_loaded(hook, batch_number, group_number):
        print(f"Batch {batch_number} del grupo {group_number} ya fue cargado. Omitiendo.")
        return False

    # Paso 3: Mapear datos a DataFrame
    df = _map_batch_to_dataframe(data, group_number)

    # Paso 4: Insertar en raw_forest_cover
    engine = hook.get_sqlalchemy_engine()
    df.to_sql(name=RAW_TABLE, con=engine, if_exists="append", index=False)

    # Paso 5: Registrar batch en batch_log
    _log_batch(hook, batch_number, group_number, record_count=len(df))

    print(f"Batch {batch_number}: {len(df)} registros insertados en {RAW_TABLE}")
    return True
