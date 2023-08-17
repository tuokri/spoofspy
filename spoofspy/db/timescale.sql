-- TimescaleDB table initialization, mainly for
-- development environments or first time production
-- database initialization.
CREATE EXTENSION IF NOT EXISTS timescaledb;

DROP TABLE IF EXISTS "game_server_state";

CREATE TABLE "game_server_state"
(
    time                            TIMESTAMPTZ NOT NULL,
    game_server_address             INET        NOT NULL,
    game_server_port                INTEGER     NOT NULL,

    -- IGameServersService/GetServerList.
    steamid                         BIGINT,
    name                            TEXT,
    appid                           INTEGER,
    gamedir                         TEXT,
    version                         TEXT,
    product                         TEXT,
    region                          INTEGER,
    players                         INTEGER,
    max_players                     INTEGER,
    bots                            INTEGER,
    map                             TEXT,
    secure                          BOOLEAN,
    dedicated                       BOOLEAN,
    os                              TEXT,
    gametype                        TEXT,

    -- A2S info.
    a2s_server_name                 TEXT,
    a2s_map_name                    TEXT,
    a2s_steam_id                    BIGINT,
    a2s_player_count                INTEGER,
    a2s_max_players                 INTEGER,
    a2s_info                        JSONB,

    -- A2S rules.
    a2s_num_open_public_connections INTEGER,
    a2s_num_public_connections      INTEGER,
    a2s_pi_count                    INTEGER,
    a2s_rules                       JSONB,

    -- A2S players.
    a2s_players                     JSONB[],

    CONSTRAINT fk_game_server
        FOREIGN KEY (game_server_address, game_server_port)
            REFERENCES game_server (address, port)
);

CREATE INDEX ON "game_server_state" (time DESC);

SELECT create_hypertable('game_server_state', 'time');
