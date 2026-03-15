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
- [10. Validaciones realizadas](#10-validaciones-realizadas)
- [11. Problemas resueltos](#11-problemas-resueltos)
- [12. Estado actual del proyecto](#12-estado-actual-del-proyecto)
- [13. Trabajo pendiente](#13-trabajo-pendiente)

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
Lee processed_forest_cover, entrena un RandomForestClassifier y guarda el modelo en: /opt/airflow/models/forest_cover_random_forest.pkl













---
