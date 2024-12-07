DROP TABLE IF EXISTS entries;

CREATE TABLE entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    state TEXT NOT NULL,
    light_val INTEGER NOT NULL,
    light_intensity INTEGER NOT NULL,
    color_temp INTEGER NOT NULL
);