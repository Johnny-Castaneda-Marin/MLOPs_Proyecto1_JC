## Tabla de contenido

- [1. Objetivo del proyecto](#1-objetivo-del-proyecto)
- [2. Arquitectura actual](#2-arquitectura-actual)
- [3. Estructura del proyecto](#3-estructura-del-proyecto)
- [4. Componentes principales](#4-componentes-principales)
- [5. Flujo del DAG](#5-flujo-del-dag)
- [6. Tablas en MySQL](#6-tablas-en-mysql)
- [7. Configuración actual](#7-configuración-actual)
- [8. Cómo levantar el proyecto](#8-cómo-levantar-el-proyecto)
- [9. Cómo ejecutar el DAG](#9-cómo-ejecutar-el-dag)


---

## 1. Objetivo del proyecto

Construir un pipeline de Machine Learning para el problema de **Forest Cover Type**, usando una arquitectura MLOps con:

- **Airflow** para la orquestación
- **MySQL** para almacenamiento de datos por capas
- **MinIO** para persistencia de modelos
- **FastAPI** para inferencia
- **API externa** como fuente de datos del proyecto

En la versión actual, el pipeline ya está preparado y funcionando con una **fuente dummy**, mientras se obtiene acceso a la API real.

---

## 2. Arquitectura actual

La arquitectura levantada actualmente incluye:

- **PostgreSQL**: base interna de Airflow
- **Redis**: broker de Celery
- **Airflow Webserver**
- **Airflow Scheduler**
- **Airflow Worker**
- **Airflow Triggerer**
- **MySQL**: almacenamiento del pipeline
- **MinIO**: almacenamiento de modelos
- **Jupyter**: entorno de exploración
- **API**: servicio de inferencia existente en el proyecto

---

## 3. Estructura del proyecto

```bash
MLOPs_Proyecto1/
│
├── dags/
│   ├── penguins_pipeline/
│   │   └── ...                 # pipeline anterior del proyecto
│   │
│   └── forest_pipeline/
│       ├── __init__.py
│       ├── forest_pipeline.py
│       └── src/
│           ├── __init__.py
│           ├── config.py
│           ├── extract_raw_forest_cover.py
│           ├── preprocess_forest_cover.py
│           ├── train_models.py
│           └── upload_to_minio.py
│
├── docker/
│   ├── airflow/
│   │   └── Dockerfile
│   └── docker-compose.yml
│
├── mysql-init/
│   └── 01_create_forest_tables.sql
│
├── pyproject.toml
```
---
## 4. Componentes principales

```text
dags/forest_pipeline/forest_pipeline.py
```

Este DAG orquesta 4 tareas:

- extract_raw_data
- preprocess_data
- train_model
- upload_model_to_minio

```text
dags/forest_pipeline/src/config.py
```
Centraliza la configuración del pipeline:

- conexión MySQL
- nombres de tablas
- URL base de la API
- grupo asignado
- configuración de MinIO
- ruta local de modelos
- modo dummy/API

```text
dags/forest_pipeline/src/extract_raw_forest_cover.py
```
Contiene la lógica de extracción.

  Actualmente soporta dos modos:

   - dummy: inserta un registro de prueba
   - api: preparado para futura integración con la API real

Mientras USE_API_SOURCE = False, la tarea usa datos dummy y los inserta en raw_forest_cover

```text
dags/forest_pipeline/src/preprocess_forest_cover.py
```
Lee raw_forest_cover, genera nuevas variables y guarda el resultado en processed_forest_cover.

  Variables derivadas actuales:

  - elevation_scaled
  - slope_scaled
  - hydrology_distance_ratio

```text
dags/forest_pipeline/src/train_models.py
```
Lee processed_forest_cover, entrena un RandomForestClassifier y guarda el modelo en: 
-  /opt/airflow/models/forest_cover_random_forest.pkl

```text
dags/forest_pipeline/src/upload_to_minio.py
```
Sube el modelo entrenado a MinIO
Bucket actual:
  - mlmodels
Objeto esperado:
  - forest_cover_random_forest.pkl

---

## 5. Flujo del DAG

El DAG actual sigue esta secuencia:

```bash
extract_raw_data
    ↓
preprocess_data
    ↓
train_model
    ↓
upload_model_to_minio
```
Descripción de cada etapa
A. extract_raw_data
  - obtiene datos desde dummy o API
  - agrega metadatos como group_id e ingestion_ts
  - inserta en raw_forest_cover
B. preprocess_data
  - lee los datos raw
  - genera features derivadas
  - elimina la columna id antes de insertar
  - guarda en processed_forest_cover
C. train_model
  - separa X y y
  - elimina columnas no entrenables (id, group_id, ingestion_ts)
  - entrena Random Forest
  - serializa el modelo con joblib
D. upload_model_to_minio
  - valida existencia del bucket
  - lo crea si no existe
  - sube el modelo a MinIO


---

## 6. Tablas en MySQL

Las tablas base del pipeline se definieron en:
```text
mysql-init/01_create_forest_tables.sql
```

Tablas creadas
-	**raw_forest_cover** : Capa cruda del pipeline.
-	**processed_forest_cover** : Capa transformada para entrenamiento.
-	**training_ready_forest_cover** : Tabla reservada para una futura capa intermedia lista para entrenamiento.
-	**model_registry** : Tabla reservada para registrar modelos y métricas.


---

## 7. Configuración actual

**Base de datos MySQL**
```text
AIRFLOW_CONN_MYSQL_DEFAULT: 'mysql://user:user1234@mysql:3306/mydatabase'
```
**MinIO**
-	MINIO_ENDPOINT = "minio:9000"
-	MINIO_ACCESS_KEY = "minio_user"
-	MINIO_SECRET_KEY = "minio_password"
-	MINIO_BUCKET = "mlmodels"

---

## 8. Cómo levantar el proyecto
Desde la carpeta docker/:

  **A. Construir imagen de Airflow**
  ```text
    docker compose build airflow-webserver airflow-scheduler airflow-worker airflow-triggerer airflow-init
  ```
  **B. Levantar servicios**
  ```text
    docker compose up -d airflow-init airflow-webserver airflow-scheduler airflow-worker airflow-triggerer mysql minio postgres redis
  ```
  **C.Verificar estado**
  ```text
    docker compose ps
  ```
---

## 9. Cómo ejecutar el DAG

**Ver DAGs disponibles**
 ```text
docker compose exec airflow-webserver airflow dags list
 ```
**Despausar DAG si es necesario**
 ```text
docker compose exec airflow-webserver airflow dags unpause forest_cover_pipeline
 ```
**Lanzar ejecución manual**
 ```text
docker compose exec airflow-webserver airflow dags trigger forest_cover_pipeline
 ```
**Ver ejecuciones**
 ```text
docker compose exec airflow-webserver airflow dags list-runs -d forest_cover_pipeline
 ```
**Ver estado de tareas de una ejecución**
 ```text
docker compose exec airflow-webserver airflow tasks states-for-dag-run forest_cover_pipeline 2026-03-15T03:46:46+00:00
 ```


---
pendiente
•	conectar la extracción a la API real
•	conocer el endpoint exacto y formato de respuesta
•	mapear las columnas reales del dataset de forest cover
•	capturar y registrar metadatos de batch
•	usar la tabla training_ready_forest_cover si se requiere una capa final
•	registrar métricas y modelos en model_registry
•	integrar la API de inferencia con el modelo almacenado en MinIO
•	ajustar entrenamiento a los datos reales del proyecto






















