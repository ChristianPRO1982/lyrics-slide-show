-- users.users definition

-- Drop table

-- DROP TABLE users.users;

CREATE TABLE users.users (
	id uuid NOT NULL,
	username varchar(255) NOT NULL,
	email varchar(255) NULL,
	email_verified bool DEFAULT false NOT NULL,
	first_name varchar(255) NULL,
	last_name varchar(255) NULL,
	enabled bool DEFAULT true NOT NULL,
	last_login_at timestamptz NULL,
	synced_at timestamptz NULL,
	CONSTRAINT users_pk PRIMARY KEY (id),
	CONSTRAINT users_unique UNIQUE (username)
);
CREATE INDEX users_last_login_at_idx ON users.users USING btree (last_login_at);