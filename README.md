# Forest Cover Type — Pipeline MLOps

## Tabla de Contenidos

- [📁 1. Estructura del Proyecto](#1-estructura-del-proyecto)
- [🐳 2. Creación de Dockerfiles custom](#2-creación-de-dockerfiles-custom)
- [🗄️ 3. Servicio MySQL en Docker Compose](#3-servicio-mysql-en-docker-compose)
- [🧱 4. Script de inicialización de BD](#4-script-de-inicialización-de-bd)
- [🏗️ 5. Arquitectura Docker Compose](#5-arquitectura-docker-compose)
- [🌲 6. DAG: forest_cover_pipeline](#6-dag-forest_cover_pipeline)
- [📓 7. Entrenamiento en Jupyter](#7-entrenamiento-en-jupyter)
- [⚡ 8. API de inferencia](#8-api-de-inferencia)
- [🚀 9. Cómo levantar el proyecto](#9-cómo-levantar-el-proyecto)
- [✅ 10. Pruebas de funcionamiento](#10-pruebas-de-funcionamiento)
- [👥 11. Colaboradores](#-colaboradores)

---

## 1. Estructura del Proyecto

```
├── api/                                    # API de inferencia (FastAPI)
│   ├── app.py                              # Endpoints
│   └── utils/
│       ├── logger.py                       # Logger de predicciones
│       ├── model_utils.py                  # Carga de modelos desde MinIO
│       └── schemas.py                      # Esquemas Pydantic
├── dags/forest_pipeline/
│   ├── forest_pipeline.py                  # DAG principal
│   └── src/
│       ├── config.py                       # Configuración centralizada
│       ├── extract_raw_forest_cover.py     # Extracción desde API externa
│       └── process_data.py                 # Decodificación one-hot → categórico
├── docker/
│   ├── airflow/
│   │   ├── Dockerfile                      # Imagen custom de Airflow
│   │   └── pyproject.toml                  # Dependencias de Airflow
│   ├── api/
│   │   ├── Dockerfile                      # Imagen de la API
│   │   └── pyproject.toml                  # Dependencias de la API
│   ├── jupyter/
│   │   └── Dockerfile                      # Imagen de Jupyter
│   └── docker-compose.yaml                 # Orquestación de servicios
├── jupyter/notebooks/
│   ├── train.ipynb                         # Notebook de entrenamiento
│   ├── test_connections.ipynb              # Test de conectividad
│   └── utils/
│       └── model_trainer.py                # Clase de entrenamiento + subida a MinIO
├── mysql-init/
│   └── create_forest_tables.sql            # Esquemas iniciales
└── images/                                 # Capturas de evidencia
```

Infraestructura (`docker/`) separada del código del pipeline (`dags/`), la API (`api/`) y los notebooks (`jupyter/`).

```bash
# Levantar
docker compose -f docker/docker-compose.yaml up --build

# Detener y borrar volúmenes
docker compose -f docker/docker-compose.yaml down -v
```

---

## 2. Creación de Dockerfiles custom

### 2.1 Airflow

El Dockerfile custom de Airflow instala dependencias del sistema (`default-libmysqlclient-dev`, `build-essential`, `pkg-config`) necesarias para compilar el cliente MySQL de Python. Se usa `uv` como gestor de paquetes por su velocidad.

```dockerfile
FROM apache/airflow:2.6.0
USER root
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         default-libmysqlclient-dev build-essential pkg-config \
  && apt-get autoremove -yqq --purge && apt-get clean
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
COPY pyproject.toml /app/
WORKDIR /app
ENV UV_SYSTEM_PYTHON=1
ENV UV_PROJECT_ENVIRONMENT=/usr/local
RUN uv sync --no-dev
USER airflow
```

Las variables `UV_SYSTEM_PYTHON` y `UV_PROJECT_ENVIRONMENT` evitan que `uv` cree un virtualenv y fuerzan la instalación en el Python del sistema, donde Airflow busca los paquetes.

### 2.2 API de inferencia

Imagen basada en Python 3.9 con `uv`. Incluye `boto3` para descargar modelos desde MinIO al iniciar.

```dockerfile
FROM python:3.9-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
WORKDIR /app
COPY docker/api/pyproject.toml .
RUN uv sync --no-dev
COPY api/ /app/
RUN mkdir -p /app/models /app/results
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.3 Jupyter

Imagen con JupyterLab, scikit-learn, boto3 y mysql-connector-python para conectarse a MySQL y MinIO desde los notebooks.

---

## 3. Servicio MySQL en Docker Compose

Se creó una base de datos MySQL separada del PostgreSQL que Airflow usa internamente para sus metadatos. MySQL almacena los datos del pipeline (raw y processed).

```yaml
mysql:
  image: mysql:8.0
  environment:
    MYSQL_ROOT_PASSWORD: admin1234
    MYSQL_DATABASE: mydatabase
    MYSQL_USER: user
    MYSQL_PASSWORD: user1234
  ports:
    - "3306:3306"
  volumes:
    - mysql_data:/var/lib/mysql
    - ../mysql-init:/docker-entrypoint-initdb.d
  healthcheck:
    test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "-padmin1234"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 30s
```

- Versión fijada en `8.0` para reproducibilidad.
- El volumen `mysql_data` persiste datos entre reinicios.
- El volumen `mysql-init` se monta en `/docker-entrypoint-initdb.d` para ejecutar el SQL de inicialización en el primer arranque.
- Health check con `mysqladmin ping` y 30s de gracia para que MySQL termine de inicializar.

La conexión desde Airflow se registra automáticamente via variable de entorno:

```yaml
AIRFLOW_CONN_MYSQL_DEFAULT: 'mysql://user:user1234@mysql:3306/mydatabase'
```

Airflow interpreta variables con prefijo `AIRFLOW_CONN_` como conexiones. Esto evita crearla manualmente en la UI cada vez que se recrean los contenedores.

---

## 4. Script de inicialización de BD

El archivo `mysql-init/create_forest_tables.sql` se ejecuta solo en la primera inicialización del contenedor MySQL.

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
- cover_type (INT)

**`batch_log`** — Control de deduplicación. Registra cada batch ingestado con una restricción `UNIQUE` sobre `(batch_number, group_number)` para evitar cargas duplicadas.

---

## 5. Arquitectura Docker Compose

<p align="center">
    <img src="images/arquitectura.png" alt="Arquitectura del Proyecto" width="600"/>
</p>


El archivo `docker/docker-compose.yaml` define tres redes aisladas que segmentan los servicios:

```mermaid
graph TB
    subgraph airflow-net
        PG[(PostgreSQL<br/>:5432)]
        RD[(Redis<br/>:6379)]
        WS[Airflow Webserver<br/>:8080]
        SC[Airflow Scheduler]
        WK[Airflow Worker]
        TR[Airflow Triggerer]
        INIT[Airflow Init]
    end

    subgraph storage-net
        API[API FastAPI<br/>:8989]
    end

    subgraph jupyter-net
        JUP[Jupyter Lab<br/>:8888]
    end

    MYSQL[(MySQL<br/>:3306)]
    MINIO[(MinIO<br/>:9000 / :9001)]

    %% Airflow internals
    WS & SC & WK & TR --> PG
    WS & SC & WK & TR --> RD
    WK -->|MySqlHook| MYSQL
    WK -.->|host.docker.internal:8090| EXT((API Externa))

    %% MySQL en dos redes
    MYSQL --- airflow-net
    MYSQL --- jupyter-net

    %% MinIO en dos redes
    MINIO --- storage-net
    MINIO --- jupyter-net

    %% Jupyter
    JUP -->|SQLAlchemy| MYSQL
    JUP -->|boto3| MINIO

    %% API
    API -->|boto3 on-demand| MINIO

    style airflow-net fill:#e8f4fd,stroke:#2196F3
    style storage-net fill:#fff3e0,stroke:#FF9800
    style jupyter-net fill:#e8f5e9,stroke:#4CAF50
```

### Comunicación entre servicios

- Los servicios de Airflow se comunican con MySQL a través de `airflow-net` usando `MySqlHook`.
- Para alcanzar la API externa del proyecto (puerto 8090 en el host), los contenedores de Airflow usan `extra_hosts: host.docker.internal:host-gateway`. Esto es necesario porque los contenedores Docker viven en redes aisladas y no pueden acceder directamente a servicios que corren en la máquina host. La directiva `extra_hosts` agrega una entrada en `/etc/hosts` del contenedor que resuelve `host.docker.internal` a la IP del gateway del host, permitiendo que el Worker de Airflow llame a `http://host.docker.internal:8090` como si fuera un hostname normal.
- MySQL está en dos redes (`airflow-net` y `jupyter-net`) para que tanto Airflow como Jupyter puedan acceder.
- MinIO está en `storage-net` y `jupyter-net` para ser accesible desde la API y Jupyter.

### Volúmenes

| Volumen | Uso |
|---|---|
| `postgres-db-volume` | Persistencia de metadatos de Airflow |
| `mysql_data` | Persistencia de tablas del pipeline |
| `minio_data` | Persistencia de objetos/modelos en MinIO |
| `../dags` → `/opt/airflow/dags` | Código de los DAGs (montado) |
| `../logs` → `/opt/airflow/logs` | Logs de ejecución de Airflow |
| `../mysql-init` → `/docker-entrypoint-initdb.d` | Scripts SQL de inicialización |

---

## 6. DAG: forest_cover_pipeline

### 6.1 Configuración del objeto DAG

```python
with DAG(
    dag_id="forest_cover_pipeline",
    start_date=datetime(2026, 3, 15),
    schedule_interval=timedelta(seconds=30),
    catchup=False,
    tags=["mlops", "forest-cover", "api"],
) as dag:
```

- `schedule_interval=timedelta(seconds=30)`: El DAG se ejecuta automáticamente cada 30 segundos. Se usa `timedelta` porque cron no soporta intervalos menores a 1 minuto.
- `catchup=False`: Desactiva la ejecución retroactiva. Sin esto, Airflow intentaría crear runs para cada intervalo entre `start_date` y la fecha actual.

### 6.2 Workflow

<p align="center">
  <img src="images/bloque_dag.png" alt="workflow" width="600"/>
</p>

```
extract_raw_data (ShortCircuitOperator) → preprocess_data (PythonOperator)
```

2 tasks secuenciales. Si la primera retorna `False`, la segunda se marca como `skipped`.

### 6.3 extract_raw_data

Usa `ShortCircuitOperator` para controlar el flujo:

1. Llama a la API externa (`http://host.docker.internal:8090/data?group_number=5`)
2. Si la API responde 400 (sin datos disponibles), retorna `False` → el DAG termina
3. Consulta `batch_log` para verificar si el batch ya fue cargado (deduplicación)
4. Si ya existe, retorna `False` → el DAG termina
5. Si es nuevo: mapea las 55 columnas a un DataFrame, inserta en `raw_forest_cover`, registra en `batch_log` y retorna `True`


### 6.4 preprocess_data

Solo se ejecuta si `extract_raw_data` retornó `True`:

1. Lee el batch más reciente de `raw_forest_cover` (filtrado por `MAX(ingestion_ts)`)
2. Decodifica las columnas one-hot de wilderness_area (4 cols → 1 string) y soil_type (40 cols → 1 string)
3. Inserta el resultado en `processed_forest_cover` (13 columnas sin metadatos)

### 6.5 Evidencias de ejecución

DAG ejecutado correctamente:

<p align="center">
  <img src="images/ejecucion_del_dag .png" alt="DAG ejecutado" width="600"/>
</p>

Datos en `raw_forest_cover` (55 columnas one-hot):

<div align="center">
  <img src="images/conexion_bbdd.png" alt="workflow" width="700">
</div>


Datos en `processed_forest_cover` (13 columnas categóricas):

<p align="center">
  <img src="images/processed_forest_cover.png" alt="Datos procesados" width="600"/>
</p>

Registros en `batch_log` (deduplicación):

<p align="center">
  <img src="images/batch_log.png" alt="Batch log" width="700"/>
</p>

---

## 7. Entrenamiento en Jupyter

El notebook `jupyter/notebooks/train.ipynb` se conecta a MySQL, lee los datos procesados y entrena 3 modelos de clasificación.

### 7.1 Flujo del notebook

1. Conexión a MySQL usando variables de entorno del compose
2. Carga de `processed_forest_cover` con `pd.read_sql`
3. Codificación de columnas categóricas (`wilderness_area`, `soil_type`) con `LabelEncoder`
4. Split 80/20 estratificado por `cover_type`
5. Entrenamiento de 3 modelos con `ModelTrainer`:
   - **Random Forest** (200 estimadores, max_depth=15)
   - **Gradient Boosting** (200 estimadores, max_depth=8, lr=0.1)
   - **SVM** (kernel RBF, C=1.0)

### 7.2 ModelTrainer

La clase `ModelTrainer` (`jupyter/notebooks/utils/model_trainer.py`) encapsula:

- Construcción de `sklearn.Pipeline` (StandardScaler + clasificador)
- Evaluación con accuracy, precision, recall, F1 (weighted)
- Visualización de classification report y matriz de confusión
- Serialización del pipeline en memoria (`io.BytesIO`) y subida directa a MinIO — sin escribir nada en disco
- Actualización del reporte CSV (`model_metrics.csv`) también en memoria: descarga el CSV actual de MinIO, actualiza y lo vuelve a subir

### 7.3 Evidencias

Notebook ejecutado:

<p align="center">
  <img src="images/notebook_entrenamiento.png" alt="Notebook de entrenamiento" width="600"/>
</p>

Métricas de los modelos:

<p align="center">
  <img src="images/metricas_modelos.png" alt="Métricas" width="600"/>
</p>

Matriz de confusión:

<p align="center">
  <img src="images/matriz_confusion.png" alt="Matriz de confusión" width="600"/>
</p>

Modelos en MinIO:

<p align="center">
  <img src="images/modelos_en _minio.png" alt="Modelos en MinIO" width="600"/>
</p>

---

## 8. API de inferencia

### 8.1 Integración en Docker Compose

```yaml
api:
  build:
    context: ..
    dockerfile: docker/api/Dockerfile
  ports:
    - "8989:8000"
  environment:
    MINIO_ENDPOINT: minio:9000
    MINIO_ACCESS_KEY: minio_user
    MINIO_SECRET_KEY: minio1234
  depends_on:
    minio:
      condition: service_healthy
  networks:
    - storage-net
```

La API corre internamente en el puerto 8000 y se expone en el puerto 8989 del host. Todos los modelos y el reporte de métricas se leen directamente desde MinIO en cada request, sin almacenamiento local.

### 8.2 Estructura

```
api/
├── app.py                  # Endpoints FastAPI
└── utils/
    ├── schemas.py          # ForestCoverInput (Pydantic)
    ├── model_utils.py      # discover_models, load_model, load_metrics (todos desde MinIO)
    └── logger.py           # PredictionLogger (registro de predicciones)
```

### 8.3 Endpoints

**`GET /health`** — Health check. Retorna `{"status": "ok"}`.

**`GET /models`** — Lista los modelos disponibles en MinIO con sus métricas. Consulta el bucket `mlmodels` en cada llamada.

**`POST /predict/{model_name}`** — Recibe las 12 features de Forest Cover (10 continuas + wilderness_area + soil_type codificados), descarga el modelo desde MinIO en memoria, ejecuta la predicción y retorna el tipo de cobertura.

### 8.4 Validación de campos

El endpoint `POST /predict/{model_name}` valida automáticamente los campos de entrada mediante Pydantic. Si algún valor está fuera de rango, la API retorna `422 Unprocessable Entity` con detalle del error.

| Campo | Tipo | Rango válido | Descripción |
|---|---|---|---|
| `elevation` | int | 1859–3858 | Elevación en metros |
| `aspect` | int | 0–360 | Orientación en grados azimut |
| `slope` | int | 0–66 | Pendiente en grados |
| `horizontal_distance_to_hydrology` | int | 0–1397 | Distancia horizontal al agua (m) |
| `vertical_distance_to_hydrology` | int | -173–601 | Distancia vertical al agua (m) |
| `horizontal_distance_to_roadways` | int | 0–7117 | Distancia horizontal a carretera (m) |
| `hillshade_9am` | int | 0–255 | Índice de sombra a las 9am |
| `hillshade_noon` | int | 0–255 | Índice de sombra al mediodía |
| `hillshade_3pm` | int | 0–255 | Índice de sombra a las 3pm |
| `horizontal_distance_to_fire_points` | int | 0–7173 | Distancia horizontal a punto de ignición (m) |
| `wilderness_area` | int | 0–3 | 0=Rawah, 1=Neota, 2=Comanche Peak, 3=Cache la Poudre |
| `soil_type` | int | 0–39 | Tipo de suelo codificado (C1–C40) |

Ejemplo de error de validación:

```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["body", "aspect"],
      "msg": "Input should be less than or equal to 360",
      "input": 400
    }
  ]
}
```

### 8.5 Integración con MinIO

La API no usa disco local. En cada operación:

- `GET /models` → `list_objects_v2` sobre el bucket `mlmodels`, filtra `.pkl`
- `POST /predict` → `get_object` del `.pkl` correspondiente, deserializa con `joblib` en un `BytesIO`
- `GET /report` → `get_object` de `model_metrics.csv`, parsea con `pandas` en memoria

### 8.5 Evidencias

API respondiendo en `/models`:

<p align="center">
  <img src="images/api_models.png" alt="API models" width="600"/>
</p>

Predicción exitosa:

<p align="center">
  <img src="images/api_prediccion.png" alt="API predicción" width="600"/>
</p>


---

## 9. Cómo levantar el proyecto

Desde la carpeta `docker/`:

```bash
# Construir todas las imágenes
docker compose build

# Levantar todos los servicios
docker compose up -d

# Verificar estado
docker compose ps
```

### Accesos

| Servicio | URL | Credenciales |
|---|---|---|
| Airflow UI | http://localhost:8080 | airflow / airflow |
| MinIO Console | http://localhost:9001 | minio_user / minio1234 |
| Jupyter Lab | http://localhost:8888 | Token: mlops12345 |
| API (Swagger) | http://localhost:8989/docs | — |
| MySQL | localhost:3306 | user / user1234 |

### Ejecutar el DAG

```bash
# Despausar el DAG (se ejecuta automáticamente cada 30s)
docker compose exec airflow-webserver airflow dags unpause forest_cover_pipeline

# O lanzar ejecución manual
docker compose exec airflow-webserver airflow dags trigger forest_cover_pipeline
```

---

## 10. Pruebas de funcionamiento

### 10.1 Pipeline de ingesta (DAG)

Verificación que el DAG se ejecuta y los datos llegan a MySQL:

<p align="center">
  <img src="images/ejecucion_del_dag .png" alt="Prueba DAG" width="600"/>
</p>

### 10.2 Entrenamiento (Jupyter)

1. Acceder a http://localhost:8888 (token: `mlops12345`)
2. Abrir `notebooks/train.ipynb`
3. Ejecutar todas las celdas
4. Verificar que los modelos aparecen en MinIO Console (http://localhost:9001, bucket `mlmodels`)

<p align="center">
  <img src="images/prueba_jupyter.png" alt="Prueba Jupyter" width="600"/>
</p>

### 10.3 API de inferencia

```bash
# Health check
curl http://localhost:8989/health

# Listar modelos
curl http://localhost:8989/models

# Predicción con Random Forest
curl -X POST http://localhost:8989/predict/randomforest \
  -H "Content-Type: application/json" \
  -d '{
    "elevation": 3117,
    "aspect": 287,
    "slope": 28,
    "horizontal_distance_to_hydrology": 484,
    "vertical_distance_to_hydrology": 13,
    "horizontal_distance_to_roadways": 1518,
    "hillshade_9am": 132,
    "hillshade_noon": 225,
    "hillshade_3pm": 228,
    "horizontal_distance_to_fire_points": 3108,
    "wilderness_area": 0,
    "soil_type": 28
  }'
```

<p align="center">
  <img src="images/prueba_api_health.png" alt="Prueba API - Healthcheck" width="600"/>
</p>

<p align="center">
  <img src="images/prueba_api_models.png" alt="Prueba API - listado de modelos" width="600"/>
</p>

<p align="center">
  <img src="images/prueba_api.png" alt="Prueba API - Inferencia" width="600"/>
</p>

### 10.4 MinIO

Verificación de que los modelos y el reporte están almacenados:

<p align="center">
  <img src="images/modelos_en _minio.png" alt="Prueba MinIO" width="600"/>
</p>

---

## 👥 Colaboradores

- 🧑‍💻 **Camilo Cortés** — [![GitHub](https://img.shields.io/badge/GitHub-@cccortesh95-181717?logo=github)](https://github.com/cccortesh95)
- 🧑‍💻 **Johnny Castañeda** — [![GitHub](https://img.shields.io/badge/GitHub-@Johnny--Castaneda--Marin-181717?logo=github)](https://github.com/Johnny-Castaneda-Marin)
- 🧑‍💻 **Benkos Triana** — [![GitHub](https://img.shields.io/badge/GitHub-@BenkosT-181717?logo=github)](https://github.com/BenkosT)
