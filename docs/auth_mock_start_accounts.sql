-- Lyrics Slide Show - auth_mock starter accounts
--
-- Purpose:
-- - seed the external directory table used by LSS in development;
-- - seed the local LSS role table for one admin and one moderator;
-- - keep the SQL idempotent with INSERT ... ON CONFLICT.
--
-- Notes:
-- - users.users is the external directory source of truth.
-- - LSS must match users by UUID only.
-- - unknown.user is intentionally not inserted:
--   33333333-3333-3333-3333-333333333333

INSERT INTO users.users (
    id,
    username,
    first_name,
    last_name,
    email,
    enabled,
    email_verified
) VALUES
    (
        '11111111-1111-1111-1111-111111111111',
        'testmock',
        'Test',
        'Mock',
        'testmock@example.test',
        true,
        false
    ),
    (
        '22222222-2222-2222-2222-222222222222',
        'disabled.user',
        'Disabled',
        'User',
        'disabled.user@example.test',
        false,
        false
    ),
    (
        '44444444-4444-4444-4444-444444444444',
        'testmock_moderateur',
        'Testmock',
        'Moderateur',
        'testmock_moderateur@example.test',
        true,
        false
    ),
    (
        '55555555-5555-5555-5555-555555555555',
        'testmock_simpletuser',
        'Testmock',
        'Simpletuser',
        'testmock_simpletuser@example.test',
        true,
        false
    )
ON CONFLICT (id) DO UPDATE SET
    username = EXCLUDED.username,
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    email = EXCLUDED.email,
    enabled = EXCLUDED.enabled,
    email_verified = EXCLUDED.email_verified;

INSERT INTO lss.m_member_roles (
    member_id,
    is_moderator,
    is_admin
) VALUES
    (
        '11111111-1111-1111-1111-111111111111',
        true,
        true
    ),
    (
        '44444444-4444-4444-4444-444444444444',
        true,
        false
    )
ON CONFLICT (member_id) DO UPDATE SET
    is_moderator = EXCLUDED.is_moderator,
    is_admin = EXCLUDED.is_admin;
