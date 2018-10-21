CREATE TABLE plonks (
    guild_id bigint,
    user_id bigint,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE greetings (
    guild_id bigint PRIMARY KEY,
    channel_id bigint,
    enabled boolean DEFAULT FALSE,
    message text DEFAULT 'Welcome {0.name} to {1.name}!'
);

CREATE TABLE experience (
    guild_id bigint,
    user_id bigint,
    exp integer DEFAULT 0,
    level smallint DEFAULT 0,
    prestige integer DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE bumps (
    guild_id bigint,
    user_id bigint,
    total bigint,
    current bigint,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE rolesoptout (
    user_id bigint PRIMARY KEY
);

CREATE TABLE rolesblacklist (
    role_id bigint PRIMARY KEY
);
