-- common."groups" definition

-- Drop table

-- DROP TABLE common."groups";

CREATE TABLE common."groups" (
	group_id serial4 NOT NULL,
	"name" varchar(255) NOT NULL,
	info text NULL,
	"token" varchar(255) NULL,
	private bool DEFAULT false NULL,
	CONSTRAINT groups_pk PRIMARY KEY (group_id),
	CONSTRAINT groups_unique UNIQUE (name)
);
CREATE INDEX groups_private_idx ON common.groups USING btree (private);
CREATE INDEX groups_token_idx ON common.groups USING btree (token);


-- common.group_user_ask_to_join definition

-- Drop table

-- DROP TABLE common.group_user_ask_to_join;

CREATE TABLE common.group_user_ask_to_join (
	group_id int4 NOT NULL,
	user_id uuid NOT NULL,
	CONSTRAINT group_user_ask_to_join_pk PRIMARY KEY (group_id, user_id),
	CONSTRAINT group_user_ask_to_join_groups_fk FOREIGN KEY (group_id) REFERENCES common."groups"(group_id) ON DELETE CASCADE,
	CONSTRAINT group_user_ask_to_join_users_fk FOREIGN KEY (user_id) REFERENCES users.users(id) ON DELETE CASCADE
);


-- common.bands definition

-- Drop table

-- DROP TABLE common.bands;

CREATE TABLE common.bands (
	band_id serial4 NOT NULL,
	"name" varchar(255) NOT NULL,
	CONSTRAINT bands_pk PRIMARY KEY (band_id),
	CONSTRAINT bands_unique UNIQUE (name)
);


-- common.band_links definition

-- Drop table

-- DROP TABLE common.band_links;

CREATE TABLE common.band_links (
	band_id int4 NOT NULL,
	link varchar(255) NOT NULL,
	CONSTRAINT band_links_pk PRIMARY KEY (band_id, link),
	CONSTRAINT band_links_bands_fk FOREIGN KEY (band_id) REFERENCES common.bands(band_id) ON DELETE CASCADE
);


-- common.artists definition

-- Drop table

-- DROP TABLE common.artists;

CREATE TABLE common.artists (
	artist_id serial4 NOT NULL,
	"name" varchar(255) NOT NULL,
	CONSTRAINT artists_pk PRIMARY KEY (artist_id),
	CONSTRAINT artists_unique UNIQUE (name)
);


-- common.artist_links definition

-- Drop table

-- DROP TABLE common.artist_links;

CREATE TABLE common.artist_links (
	artist_id int4 NOT NULL,
	link varchar(255) NOT NULL,
	CONSTRAINT artist_links_pk PRIMARY KEY (artist_id, link),
	CONSTRAINT artist_links_artists_fk FOREIGN KEY (artist_id) REFERENCES common.artists(artist_id) ON DELETE CASCADE
);