INSERT INTO users.users (
    id,
    username,
    email,
    email_verified,
    first_name,
    last_name,
    enabled
) VALUES (
    '11111111-1111-1111-1111-111111111111',
    'demo',
    'demo@example.test',
    true,
    'Demo',
    'User',
    true
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO lss.users (id)
VALUES ('11111111-1111-1111-1111-111111111111')
ON CONFLICT (id) DO NOTHING;

INSERT INTO common.groups ("name", info, private)
VALUES ('LSS Demo Group', 'Groupe seed de développement pour le bootstrap Django.', false)
ON CONFLICT ("name") DO NOTHING;

INSERT INTO lss.site_params (
    language,
    title,
    title_h1,
    home_text,
    bloc1_text,
    bloc2_text,
    verse_max_lines,
    verse_max_characters_for_a_line,
    chorus_prefix,
    verse_prefix1,
    verse_prefix2,
    admin_message,
    moderator_message
) VALUES (
    'fr',
    'Lyrics Slide Show',
    'Lyrics Slide Show',
    'Bootstrap Django + OIDC mock',
    'Lecture du schéma lss.',
    'Lecture du schéma common.',
    4,
    40,
    'Refrain',
    'Couplet',
    'V.',
    'Message administrateur',
    'Message modérateur'
)
ON CONFLICT (language) DO NOTHING;
