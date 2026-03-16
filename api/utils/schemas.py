from pydantic import BaseModel, Field


class ForestCoverInput(BaseModel):
    elevation: int = Field(
        ge=1859, le=3858,
        examples=[3117],
        description="Elevación en metros (1859–3858)"
    )
    aspect: int = Field(
        ge=0, le=360,
        examples=[287],
        description="Orientación en grados azimut (0–360)"
    )
    slope: int = Field(
        ge=0, le=66,
        examples=[28],
        description="Pendiente en grados (0–66)"
    )
    horizontal_distance_to_hydrology: int = Field(
        ge=0, le=1397,
        examples=[484],
        description="Distancia horizontal al agua más cercana en metros (0–1397)"
    )
    vertical_distance_to_hydrology: int = Field(
        ge=-173, le=601,
        examples=[13],
        description="Distancia vertical al agua más cercana en metros (-173–601)"
    )
    horizontal_distance_to_roadways: int = Field(
        ge=0, le=7117,
        examples=[1518],
        description="Distancia horizontal a la carretera más cercana en metros (0–7117)"
    )
    hillshade_9am: int = Field(
        ge=0, le=255,
        examples=[132],
        description="Índice de sombra a las 9am (0–255)"
    )
    hillshade_noon: int = Field(
        ge=0, le=255,
        examples=[225],
        description="Índice de sombra al mediodía (0–255)"
    )
    hillshade_3pm: int = Field(
        ge=0, le=255,
        examples=[228],
        description="Índice de sombra a las 3pm (0–255)"
    )
    horizontal_distance_to_fire_points: int = Field(
        ge=0, le=7173,
        examples=[3108],
        description="Distancia horizontal al punto de ignición más cercano en metros (0–7173)"
    )
    wilderness_area: int = Field(
        ge=0, le=3,
        examples=[0],
        description="Área wilderness codificada: 0=Rawah, 1=Neota, 2=Comanche Peak, 3=Cache la Poudre"
    )
    soil_type: int = Field(
        ge=0, le=39,
        examples=[28],
        description="Tipo de suelo codificado (0–39, corresponde a C1–C40)"
    )
