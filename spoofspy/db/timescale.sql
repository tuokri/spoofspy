-- TimescaleDB table initialization, mainly for
-- development environments or first time production
-- database initialization.
CREATE EXTENSION IF NOT EXISTS timescaledb;

DROP TABLE IF EXISTS "game_server_state";

-- Currently specific to Rising Storm 2: Vietnam.
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
    a2s_info_responded              BOOLEAN,
    a2s_info_response_time          TIMESTAMPTZ,
    a2s_server_name                 TEXT,
    a2s_map_name                    TEXT,
    a2s_steam_id                    BIGINT,
    a2s_player_count                INTEGER,
    a2s_max_players                 INTEGER,
    a2s_info                        JSONB,

    -- A2S rules.
    a2s_rules_responded             BOOLEAN,
    a2s_rules_response_time         TIMESTAMPTZ,
    a2s_num_open_public_connections INTEGER,
    a2s_num_public_connections      INTEGER,
    a2s_pi_count                    INTEGER,
    a2s_pi_objects                  JSONB,
    a2s_mutators_running            TEXT[],
    a2s_rules                       JSONB,

    -- A2S players.
    a2s_players_responded           BOOLEAN,
    a2s_players_response_time       TIMESTAMPTZ,
    a2s_players                     JSONB[],

    trust_score                     REAL,

    CONSTRAINT fk_game_server
        FOREIGN KEY (game_server_address, game_server_port)
            REFERENCES game_server (address, port)
);

CREATE INDEX ON "game_server_state" (time DESC);
CREATE INDEX ON "game_server_state" (time DESC, trust_score);

SELECT create_hypertable('game_server_state', 'time');

SELECT add_retention_policy('game_server_state', INTERVAL '6 months');

ALTER TABLE game_server_state
    SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'game_server_address, game_server_port'
        );

SELECT add_compression_policy('game_server_state', INTERVAL '10 days');


DROP TABLE IF EXISTS "endpoint_access";

-- Lightweight access log.
CREATE TABLE "endpoint_access"
(
    time      TIMESTAMPTZ NOT NULL,
    address   INET        NOT NULL,
    unique_id BIGINT      NOT NULL
);

SELECT create_hypertable('endpoint_access', 'time');

ALTER TABLE endpoint_access
    SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'unique_id'
        );

SELECT add_compression_policy('endpoint_access', INTERVAL '2 days');

SELECT add_retention_policy('endpoint_access', INTERVAL '6 months');
