-- Migration des donnees groupes de lss vers common.
--
-- Preconditions:
-- - les tables common.g_groups, common.g_group_user et
--   common.g_group_user_ask_to_join existent deja ;
-- - les anciennes tables lss.g_groups, lss.g_group_user et
--   lss.g_group_user_ask_to_join existent encore ;
-- - ce script ne supprime et ne renomme aucune table lss.

BEGIN;

INSERT INTO common.g_groups (
  group_id,
  name,
  info,
  secret_ciphertext,
  status
)
SELECT
  group_id,
  name,
  info,
  secret_ciphertext,
  status
FROM lss.g_groups
ON CONFLICT (group_id) DO UPDATE
SET
  name = EXCLUDED.name,
  info = EXCLUDED.info,
  secret_ciphertext = EXCLUDED.secret_ciphertext,
  status = EXCLUDED.status;

INSERT INTO common.g_group_user (
  group_id,
  member_id,
  is_group_admin,
  am_access
)
SELECT
  group_id,
  member_id,
  is_group_admin,
  false AS am_access
FROM lss.g_group_user
ON CONFLICT (group_id, member_id) DO UPDATE
SET
  is_group_admin = EXCLUDED.is_group_admin,
  am_access = common.g_group_user.am_access;

INSERT INTO common.g_group_user_ask_to_join (
  group_id,
  member_id
)
SELECT
  group_id,
  member_id
FROM lss.g_group_user_ask_to_join
ON CONFLICT (group_id, member_id) DO NOTHING;

SELECT setval(
  pg_get_serial_sequence('common.g_groups', 'group_id'),
  COALESCE((SELECT MAX(group_id) FROM common.g_groups), 1),
  EXISTS (SELECT 1 FROM common.g_groups)
);

COMMIT;

-- Controles de coherence a executer apres migration.

SELECT
  'g_groups' AS table_name,
  (SELECT COUNT(*) FROM lss.g_groups) AS lss_count,
  (SELECT COUNT(*) FROM common.g_groups) AS common_count,
  (SELECT COUNT(*) FROM lss.g_groups)
    - (SELECT COUNT(*) FROM common.g_groups) AS count_delta;

SELECT
  'g_group_user' AS table_name,
  (SELECT COUNT(*) FROM lss.g_group_user) AS lss_count,
  (SELECT COUNT(*) FROM common.g_group_user) AS common_count,
  (SELECT COUNT(*) FROM lss.g_group_user)
    - (SELECT COUNT(*) FROM common.g_group_user) AS count_delta;

SELECT
  'g_group_user_ask_to_join' AS table_name,
  (SELECT COUNT(*) FROM lss.g_group_user_ask_to_join) AS lss_count,
  (SELECT COUNT(*) FROM common.g_group_user_ask_to_join) AS common_count,
  (SELECT COUNT(*) FROM lss.g_group_user_ask_to_join)
    - (SELECT COUNT(*) FROM common.g_group_user_ask_to_join) AS count_delta;

SELECT lss_groups.group_id
FROM lss.g_groups AS lss_groups
LEFT JOIN common.g_groups AS common_groups
  ON common_groups.group_id = lss_groups.group_id
WHERE common_groups.group_id IS NULL
ORDER BY lss_groups.group_id;

SELECT lss_memberships.group_id, lss_memberships.member_id
FROM lss.g_group_user AS lss_memberships
LEFT JOIN common.g_group_user AS common_memberships
  ON common_memberships.group_id = lss_memberships.group_id
 AND common_memberships.member_id = lss_memberships.member_id
WHERE common_memberships.group_id IS NULL
ORDER BY lss_memberships.group_id, lss_memberships.member_id;

SELECT lss_requests.group_id, lss_requests.member_id
FROM lss.g_group_user_ask_to_join AS lss_requests
LEFT JOIN common.g_group_user_ask_to_join AS common_requests
  ON common_requests.group_id = lss_requests.group_id
 AND common_requests.member_id = lss_requests.member_id
WHERE common_requests.group_id IS NULL
ORDER BY lss_requests.group_id, lss_requests.member_id;

SELECT group_id, member_id
FROM common.g_group_user
WHERE am_access IS DISTINCT FROM false
ORDER BY group_id, member_id;

SELECT common_memberships.group_id, common_memberships.member_id
FROM common.g_group_user AS common_memberships
LEFT JOIN common.g_groups AS common_groups
  ON common_groups.group_id = common_memberships.group_id
WHERE common_groups.group_id IS NULL
ORDER BY common_memberships.group_id, common_memberships.member_id;

SELECT common_requests.group_id, common_requests.member_id
FROM common.g_group_user_ask_to_join AS common_requests
LEFT JOIN common.g_groups AS common_groups
  ON common_groups.group_id = common_requests.group_id
WHERE common_groups.group_id IS NULL
ORDER BY common_requests.group_id, common_requests.member_id;
