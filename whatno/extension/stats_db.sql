PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS History(
    user INTEGER NOT NULL,
    guild INTEGER NOT NULL,
    channel INTEGER NOT NULL,
    voicestate TEXT NOT NULL,
    starttime TIMESTAMP NOT NULL,
    duration REAL NOT NULL,
    historic BOOLEAN,
    h_time TEXT,
    UNIQUE(user, channel, voicestate, starttime)
);

CREATE TABLE IF NOT EXISTS Total(
    user INTEGER NOT NULL,
    channel INTEGER NOT NULL,
    voicestate TEXT NOT NULL,
    duration REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS Message(
    message INTEGER NOT NULL,
    user INTEGER,
    guild INTEGER NOT NULL,
    channel INTEGER NOT NULL,
    timestamp INTEGER NOT NULL,
    event TEXT NOT NULL,
    content TEXT,
    attachment TEXT,
    embed TEXT,
    replyto INTEGER,
    historical BOOLEAN,
    h_time TEXT,
    UNIQUE(message, event, timestamp)
);
