## Tabla de contenido

- [1. Objetivo del proyecto](#1-objetivo-del-proyecto)
- [2. Arquitectura Docker Compose](#2-arquitectura-docker-compose)
- [3. Estructura del proyecto](#3-estructura-del-proyecto)
- [4. Inicialización de MySQL](#4-inicialización-de-mysql)
- [5. DAG: forest_cover_pipeline](#5-dag-forest_cover_pipeline)
- [6. Configuración](#6-configuración)
- [7. Cómo levantar el proyecto](#7-cómo-levantar-el-proyecto)
- [8. Cómo ejecutar el DAG](#8-cómo-ejecutar-el-dag)

---

## 1. Objetivo del proyecto

Pipeline MLOps para el dataset **Forest Cover Type** que ingesta datos desde una API externa, los almacena en crudo (55 columnas one-hot), los procesa a formato categórico y los deja listos para entrenamiento.

---

## 2. Arquitectura Docker Compose

El archivo `docker/docker-compose.yaml` define tres redes aisladas que segmentan los servicios:

```
airflow-net (bridge, con acceso a internet)
├── PostgreSQL       — base de datos interna de Airflow (metadatos, DAG runs)
├── Redis            — broker de mensajes para Celery
├── Airflow Webserver — UI en puerto 8080
├── Airflow Scheduler — planificación de DAGs
├── Airflow Worker   — ejecución de tareas vía Celery
├── Airflow Triggerer — triggers asincrónicos
├── Airflow Init     — migración de BD y creación de usuario admin
└── MySQL            — almacenamiento del pipeline (raw, processed, batch_log)

storage-net
├── MinIO            — almacenamiento de objetos (modelos) en puertos 9000/9001
└── API              — servicio FastAPI de inferencia en puerto 8989

jupyter-net
├── Jupyter          — notebooks de exploración en puerto 8888
├── MySQL            — compartido con airflow-net
└── MinIO            — compartido con storage-net
```

### Comunicación entre servicios

- Los servicios de Airflow se comunican con MySQL a través de `airflow-net` usando la conexión `mysql://user:user1234@mysql:3306/mydatabase`
- Para alcanzar la API externa (que corre en el host en el puerto 8090), los contenedores de Airflow usan `extra_hosts: host.docker.internal:host-gateway`
- MySQL está en dos redes (`airflow-net` y `jupyter-net`) para que tanto Airflow como Jupyter puedan acceder
- MinIO está en `storage-net` y `jupyter-net` para ser accesible desde la API y Jupyter

### Volúmenes

| Volumen | Uso |
|---|---|
| `postgres-db-volume` | Persistencia de metadatos de Airflow |
| `mysql_data` | Persistencia de tablas del pipeline |
| `minio_data` | Persistencia de objetos/modelos |
| `../dags` → `/opt/airflow/dags` | Código de los DAGs (montado) |
| `../logs` → `/opt/airflow/logs` | Logs de ejecución de Airflow |
| `../mysql-init` → `/docker-entrypoint-initdb.d` | Scripts SQL de inicialización |

---

## 3. Estructura del proyecto

```
├── dags/
│   └── forest_pipeline/
│       ├── forest_pipeline.py              # Definición del DAG
│       └── src/
│           ├── config.py                   # Configuración centralizada
│           ├── extract_raw_forest_cover.py # Extracción desde API → raw_forest_cover
│           └── process_data.py             # Procesamiento one-hot → categórico
│
├── docker/
│   ├── airflow/Dockerfile                  # Imagen de Airflow
│   ├── api/Dockerfile                      # Imagen de la API de inferencia
│   ├── jupyter/Dockerfile                  # Imagen de Jupyter
│   └── docker-compose.yaml                 # Orquestación de servicios
│
├── mysql-init/
│   └── create_forest_tables.sql            # DDL de tablas del pipeline
│
├── api/                                    # Código de la API de inferencia
├── jupyter/notebooks/                      # Notebooks de exploración
├── models/                                 # Modelos entrenados (runtime)
├── data/                                   # Datos generados (runtime)
└── logs/                                   # Logs de Airflow (runtime)
```

---

## 4. Inicialización de MySQL

El archivo `mysql-init/create_forest_tables.sql` se monta en `/docker-entrypoint-initdb.d` del contenedor MySQL. Docker ejecuta automáticamente estos scripts la primera vez que se crea el volumen.

### Tablas creadas

**`raw_forest_cover`** — Capa cruda. Almacena las 55 columnas tal como vienen de la API:
- 10 columnas continuas (elevation, aspect, slope, distancias, hillshades)
- 4 columnas one-hot de wilderness_area
- 40 columnas one-hot de soil_type
- 1 columna cover_type
- Metadatos: group_id, ingestion_ts

**`processed_forest_cover`** — Capa procesada. Las 44 columnas one-hot se decodifican a 2 columnas categóricas:
- 10 columnas continuas (mismas que raw)
- wilderness_area (VARCHAR) — nombre del área
- soil_type (VARCHAR) — tipo de suelo
- cover_type
- Metadatos: group_id, ingestion_ts

**`batch_log`** — Control de deduplicación. Registra cada batch ingestado con una restricción UNIQUE sobre (batch_number, group_number) para evitar cargas duplicadas.

> Si necesitas recrear las tablas (por cambios en el esquema), debes eliminar el volumen de MySQL:
> ```bash
> docker compose -f docker/docker-compose.yaml down -v
> docker compose -f docker/docker-compose.yaml up -d
> ```

---

## 5. DAG: forest_cover_pipeline

El DAG se ejecuta automáticamente cada 30 segundos y tiene 2 tareas encadenadas:

```
extract_raw_data (ShortCircuitOperator) → preprocess_data (PythonOperator)
```

### extract_raw_data

Usa `ShortCircuitOperator` para controlar el flujo:

1. Llama a la API externa (`http://host.docker.internal:8090/data?group_number=5`)
2. Si la API responde 400 (sin datos), retorna `False` → el DAG termina sin error
3. Consulta `batch_log` para verificar si el batch ya fue cargado
4. Si ya existe, retorna `False` → el DAG termina (deduplicación)
5. Si es nuevo: mapea las 55 columnas a un DataFrame, inserta en `raw_forest_cover`, registra en `batch_log` y retorna `True`

### preprocess_data

Solo se ejecuta si `extract_raw_data` retornó `True`:

1. Lee el batch más reciente de `raw_forest_cover` (filtrado por `MAX(ingestion_ts)`)
2. Decodifica las columnas one-hot de wilderness_area y soil_type a strings categóricos
3. Inserta el resultado en `processed_forest_cover`

---

## 6. Configuración

Toda la configuración del pipeline está centralizada en `dags/forest_pipeline/src/config.py`:

| Variable | Valor | Descripción |
|---|---|---|
| `API_BASE_URL` | `http://host.docker.internal:8090` | URL de la API desde Docker |
| `GROUP_ID` | `5` | Grupo asignado del proyecto |
| `API_TIMEOUT` | `30` | Timeout en segundos para la API |
| `RAW_TABLE` | `raw_forest_cover` | Tabla de datos crudos (55 cols) |
| `PROCESSED_TABLE` | `processed_forest_cover` | Tabla de datos procesados (13 cols) |
| `BATCH_LOG_TABLE` | `batch_log` | Tabla de control de deduplicación |

---

## 7. Cómo levantar el proyecto

Desde la carpeta `docker/`:

```bash
# Construir imágenes
docker compose build

# Levantar todos los servicios
docker compose up -d

# Verificar estado
docker compose ps
```

---

## 8. Cómo ejecutar el DAG

El DAG está configurado para ejecutarse automáticamente cada 30 segundos. Para operaciones manuales:

```bash
# Despausar el DAG
docker compose exec airflow-webserver airflow dags unpause forest_cover_pipeline

# Lanzar ejecución manual
docker compose exec airflow-webserver airflow dags trigger forest_cover_pipeline

# Ver ejecuciones
docker compose exec airflow-webserver airflow dags list-runs -d forest_cover_pipeline
```

Acceso a la UI de Airflow: `http://localhost:8080` (usuario: airflow, contraseña: airflow)

---

## Colaboradores

- Camilo Cortés — [GitHub](https://github.com/cccortesh95)
- Johnny Castañeda — [GitHub](https://github.com/Johnny-Castaneda-Marin)
- Benkos Triana — [GitHub](https://github.com/BenkosT)
