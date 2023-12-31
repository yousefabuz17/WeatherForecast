CREATE TABLE IF NOT EXISTS Locations (
    location_id SERIAL PRIMARY KEY,
    location_name VARCHAR(255),
    longitude DECIMAL(9, 6),
    latitude DECIMAL(9, 6)
);

CREATE TABLE IF NOT EXISTS Temperature (
    temperature_id SERIAL PRIMARY KEY,
    location_id INTEGER,
    day DATE,
    min_temp_cel DECIMAL(5, 2),
    min_temp_fah DECIMAL(5, 2),
    max_temp_cel DECIMAL(5, 2),
    max_temp_fah DECIMAL(5, 2),
    FOREIGN KEY (location_id) REFERENCES Locations (location_id)
);

CREATE TABLE IF NOT EXISTS Hourly (
    hourly_id SERIAL PRIMARY KEY,
    temperature_id INTEGER,
    hour TIME,
    temp_cel DECIMAL(5, 2),
    temp_fah DECIMAL(5, 2),
    humidity INTEGER,
    conditions VARCHAR(255),
    FOREIGN KEY (temperature_id) REFERENCES Temperature (temperature_id)
);

CREATE TABLE IF NOT EXISTS WeatherEmoji (
    emoji_id SERIAL PRIMARY KEY,
    description VARCHAR(255),
    icon_code VARCHAR(255) UNIQUE,
    day_bytes BYTEA,
    night_bytes BYTEA
);

INSERT INTO Locations (location_name, longitude, latitude)
VALUES (%s, %s, %s)
RETURNING location_id;

INSERT INTO Temperature (location_id, day, min_temp_cel, min_temp_fah, max_temp_cel, max_temp_fah)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING temperature_id;

INSERT INTO Hourly (temperature_id, hour, temp_cel, temp_fah, humidity, conditions)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING hourly_id;

INSERT INTO WeatherEmoji (description, icon_code, day_bytes, night_bytes)
VALUES (%s, %s, %s, %s)
RETURNING emoji_id;

SELECT l.location_name, TO_CHAR(t.day, 'MM/DD/YYYY'), h.hour, t.min_temp_fah, t.max_temp_fah, h.temp_fah, h.humidity, h.condition
FROM Locations l
JOIN Temperature t ON l.location_id = t.location_id
JOIN (
    SELECT temperature_id, array_agg(hour) AS hours, array_agg(temp_fah) AS temps_fah,
    array_agg(humidity) AS humidities, array_agg(conditions) AS conditions
    FROM Hourly
    GROUP BY temperature_id
) h_agg ON t.temperature_id = h_agg.temperature_id
CROSS JOIN UNNEST(h_agg.hours, h_agg.temps_fah, h_agg.humidities, h_agg.conditions)
    AS h(hour, temp_fah, humidity, condition);