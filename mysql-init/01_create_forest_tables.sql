CREATE TABLE IF NOT EXISTS raw_forest_cover (
    id INT AUTO_INCREMENT PRIMARY KEY,
    elevation INT,
    aspect INT,
    slope INT,
    horizontal_distance_to_hydrology INT,
    vertical_distance_to_hydrology INT,
    horizontal_distance_to_roadways INT,
    hillshade_9am INT,
    hillshade_noon INT,
    hillshade_3pm INT,
    horizontal_distance_to_fire_points INT,
    cover_type INT,
    group_id VARCHAR(20),
    ingestion_ts DATETIME
);

CREATE TABLE IF NOT EXISTS processed_forest_cover (
    id INT AUTO_INCREMENT PRIMARY KEY,
    elevation INT,
    aspect INT,
    slope INT,
    horizontal_distance_to_hydrology INT,
    vertical_distance_to_hydrology INT,
    horizontal_distance_to_roadways INT,
    hillshade_9am INT,
    hillshade_noon INT,
    hillshade_3pm INT,
    horizontal_distance_to_fire_points INT,
    cover_type INT,
    group_id VARCHAR(20),
    ingestion_ts DATETIME,
    elevation_scaled FLOAT,
    slope_scaled FLOAT,
    hydrology_distance_ratio FLOAT
);

CREATE TABLE IF NOT EXISTS training_ready_forest_cover (
    id INT AUTO_INCREMENT PRIMARY KEY,
    elevation INT,
    aspect INT,
    slope INT,
    horizontal_distance_to_hydrology INT,
    vertical_distance_to_hydrology INT,
    horizontal_distance_to_roadways INT,
    hillshade_9am INT,
    hillshade_noon INT,
    hillshade_3pm INT,
    horizontal_distance_to_fire_points INT,
    cover_type INT,
    group_id VARCHAR(20),
    ingestion_ts DATETIME,
    elevation_scaled FLOAT,
    slope_scaled FLOAT,
    hydrology_distance_ratio FLOAT
);

CREATE TABLE IF NOT EXISTS model_registry (
    id INT AUTO_INCREMENT PRIMARY KEY,
    model_name VARCHAR(100),
    model_path VARCHAR(255),
    bucket_name VARCHAR(100),
    object_name VARCHAR(255),
    train_timestamp DATETIME,
    metric_name VARCHAR(100),
    metric_value FLOAT
);