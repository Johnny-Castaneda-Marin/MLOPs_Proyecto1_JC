import numpy as np
from fastapi import FastAPI, HTTPException

from utils.model_utils import (
    COVER_TYPE_MAP,
    discover_models,
    load_metrics,
    load_model,
)
from utils.logger import PredictionLogger
from utils.schemas import ForestCoverInput

app = FastAPI(title="Forest Cover Type Classifier API")
pred_logger = PredictionLogger()


@app.get("/health")
async def health():
    return {"status": "ok"}


def _build_features(data: ForestCoverInput) -> np.ndarray:
    return np.array([[
        data.elevation, data.aspect, data.slope,
        data.horizontal_distance_to_hydrology,
        data.vertical_distance_to_hydrology,
        data.horizontal_distance_to_roadways,
        data.hillshade_9am, data.hillshade_noon, data.hillshade_3pm,
        data.horizontal_distance_to_fire_points,
        data.wilderness_area, data.soil_type,
    ]])


@app.get("/models")
async def list_models():
    """Lista todos los modelos disponibles en MinIO con sus métricas."""
    available = discover_models()
    metrics = load_metrics()
    return {
        "available_models": [
            {
                "name": name,
                "endpoint": f"POST /predict/{name}",
                "metrics": metrics.get(name, {}),
            }
            for name in sorted(available.keys())
        ]
    }



@app.post("/predict/{model_name}")
async def predict(model_name: str, data: ForestCoverInput):
    """Predice el tipo de cobertura forestal usando el modelo especificado."""
    available = discover_models()
    if model_name not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Modelo '{model_name}' no encontrado. Usa GET /models para ver los disponibles.",
        )
    try:
        model = load_model(available[model_name])
        features = _build_features(data)
        prediction = int(model.predict(features)[0])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    cover_name = COVER_TYPE_MAP.get(prediction, "Desconocido")
    result = {
        "model": model_name,
        "cover_type_id": prediction,
        "cover_type_name": cover_name,
    }

    pred_logger.log(data.model_dump(), result)
    return result
