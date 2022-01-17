CREATE TABLE IF NOT EXISTS History(
    user INTEGER NOT NULL,
    guild INTEGER NOT NULL,
    channel INTEGER NOT NULL,
    voicestate TEXT NOT NULL,
    starttime TIMESTAMP NOT NULL,
    duration REAL NOT NULL,
    historic BOOLEAN
);

CREATE TABLE IF NOT EXISTS Total(
    user INTEGER NOT NULL,
    channel INTEGER NOT NULL,
    voicestate TEXT NOT NULL,
    duration REAL NOT NULL
);
