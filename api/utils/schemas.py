from pydantic import BaseModel, Field


class ForestCoverInput(BaseModel):
    elevation: int = Field(examples=[3117])
    aspect: int = Field(examples=[287])
    slope: int = Field(examples=[28])
    horizontal_distance_to_hydrology: int = Field(examples=[484])
    vertical_distance_to_hydrology: int = Field(examples=[13])
    horizontal_distance_to_roadways: int = Field(examples=[1518])
    hillshade_9am: int = Field(examples=[132])
    hillshade_noon: int = Field(examples=[225])
    hillshade_3pm: int = Field(examples=[228])
    horizontal_distance_to_fire_points: int = Field(examples=[3108])
    wilderness_area: int = Field(examples=[0], description="Encoded wilderness area (0-3)")
    soil_type: int = Field(examples=[28], description="Encoded soil type (0-39)")
