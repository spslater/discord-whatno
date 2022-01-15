CREATE TABLE IF NOT EXISTS History(
    user INTEGER NOT NULL,
    guild INTEGER NOT NULL,
    channel INTEGER NOT NULL,
    voicestate TEXT NOT NULL,
    starttime TIMESTAMP NOT NULL,
    duration INTEGER NOT NULL
);
