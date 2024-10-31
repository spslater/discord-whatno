CREATE TABLE IF NOT EXISTS Arc(
    number PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    url TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS Comic(
    release PRIMARY KEY,
    title TEXT NOT NULL,
    image TEXT UNIQUE NOT NULL,
    url TEXT UNIQUE NOT NULL,
    arcId
        REFERENCES Arc(rowid)
        ON DELETE CASCADE
        ON UPDATE CASCADE
        NOT NULL
);

CREATE TABLE IF NOT EXISTS Alt(
    comicId
        UNIQUE
        REFERENCES Comic(release)
        ON DELETE CASCADE
        ON UPDATE CASCADE
        NOT NULL,
    alt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Tag(
    comicId
        REFERENCES Comic(release)
        ON DELETE CASCADE
        ON UPDATE CASCADE
        NOT NULL,
    tag TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Latest(
    msg PRIMARY KEY,
    url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS React(
    msg
        REFERENCES Latest(msg)
        ON DELETE CASCADE
        ON UPDATE CASCADE
        NOT NULL,
    user INTEGER NOT NULL,
    reaction TEXT NOT NULL,
    CONSTRAINT one_react UNIQUE (msg, user, reaction)
);

CREATE TABLE IF NOT EXISTS Discussion(
    msg INTEGER PRIMARY KEY,
    time INTEGER NOT NULL,
    user INTEGER NOT NULL,
    comic
        REFERENCES Latest(msg)
        ON DELETE CASCADE
        ON UPDATE CASCADE
        NOT NULL,
    content TEXT,
    attach TEXT,
    embed TEXT
);
