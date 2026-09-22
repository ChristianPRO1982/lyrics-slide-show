-- Controles post-migration des groupes de lss vers common.
--
-- Ce script est volontairement en lecture seule.
-- Les deltas de comptage doivent etre a 0.
-- Les requetes de recherche de trous, divergences et orphelins doivent
-- retourner 0 ligne.

-- 1. Comptages globaux : les deltas doivent etre a 0.
SELECT 'g_groups' AS table_name,
       (SELECT COUNT(*) FROM lss.g_groups) AS lss_count,
       (SELECT COUNT(*) FROM common.g_groups) AS common_count,
       (SELECT COUNT(*) FROM common.g_groups)
         - (SELECT COUNT(*) FROM lss.g_groups) AS delta
UNION ALL
SELECT 'g_group_user',
       (SELECT COUNT(*) FROM lss.g_group_user),
       (SELECT COUNT(*) FROM common.g_group_user),
       (SELECT COUNT(*) FROM common.g_group_user)
         - (SELECT COUNT(*) FROM lss.g_group_user)
UNION ALL
SELECT 'g_group_user_ask_to_join',
       (SELECT COUNT(*) FROM lss.g_group_user_ask_to_join),
       (SELECT COUNT(*) FROM common.g_group_user_ask_to_join),
       (SELECT COUNT(*) FROM common.g_group_user_ask_to_join)
         - (SELECT COUNT(*) FROM lss.g_group_user_ask_to_join);

-- 2. Groupes presents dans lss mais absents de common : 0 ligne attendue.
SELECT group_id
FROM lss.g_groups
EXCEPT
SELECT group_id
FROM common.g_groups
ORDER BY group_id;

-- 3. Groupes presents dans common mais absents de lss : 0 ligne attendue
-- juste apres migration LSS, avant toute creation commune posterieure.
SELECT group_id
FROM common.g_groups
EXCEPT
SELECT group_id
FROM lss.g_groups
ORDER BY group_id;

-- 4. Memberships presentes dans lss mais absentes de common : 0 ligne attendue.
SELECT group_id, member_id
FROM lss.g_group_user
EXCEPT
SELECT group_id, member_id
FROM common.g_group_user
ORDER BY group_id, member_id;

-- 5. Memberships presentes dans common mais absentes de lss : 0 ligne attendue
-- juste apres migration LSS, avant toute creation commune posterieure.
SELECT group_id, member_id
FROM common.g_group_user
EXCEPT
SELECT group_id, member_id
FROM lss.g_group_user
ORDER BY group_id, member_id;

-- 6. Demandes presentes dans lss mais absentes de common : 0 ligne attendue.
SELECT group_id, member_id
FROM lss.g_group_user_ask_to_join
EXCEPT
SELECT group_id, member_id
FROM common.g_group_user_ask_to_join
ORDER BY group_id, member_id;

-- 7. Demandes presentes dans common mais absentes de lss : 0 ligne attendue
-- juste apres migration LSS, avant toute creation commune posterieure.
SELECT group_id, member_id
FROM common.g_group_user_ask_to_join
EXCEPT
SELECT group_id, member_id
FROM lss.g_group_user_ask_to_join
ORDER BY group_id, member_id;

-- 8. Divergences de contenu sur les groupes : 0 ligne attendue.
SELECT l.group_id,
       l.name AS lss_name,
       c.name AS common_name,
       l.info AS lss_info,
       c.info AS common_info,
       l.secret_ciphertext AS lss_secret,
       c.secret_ciphertext AS common_secret,
       l.status AS lss_status,
       c.status AS common_status
FROM lss.g_groups AS l
JOIN common.g_groups AS c USING (group_id)
WHERE l.name IS DISTINCT FROM c.name
   OR l.info IS DISTINCT FROM c.info
   OR l.secret_ciphertext IS DISTINCT FROM c.secret_ciphertext
   OR l.status IS DISTINCT FROM c.status
ORDER BY l.group_id;

-- 9. Divergences de role responsable de groupe : 0 ligne attendue.
SELECT l.group_id,
       l.member_id,
       l.is_group_admin AS lss_is_group_admin,
       c.is_group_admin AS common_is_group_admin
FROM lss.g_group_user AS l
JOIN common.g_group_user AS c USING (group_id, member_id)
WHERE l.is_group_admin IS DISTINCT FROM c.is_group_admin
ORDER BY l.group_id, l.member_id;

-- 10. am_access initialise autrement que false : 0 ligne attendue juste apres
-- migration LSS, tant qu'AM n'a pas applique ses validations.
SELECT group_id, member_id, am_access
FROM common.g_group_user
WHERE am_access IS DISTINCT FROM false
ORDER BY group_id, member_id;

-- 11. Memberships common sans groupe common : 0 ligne attendue.
SELECT u.group_id, u.member_id
FROM common.g_group_user AS u
LEFT JOIN common.g_groups AS g ON g.group_id = u.group_id
WHERE g.group_id IS NULL
ORDER BY u.group_id, u.member_id;

-- 12. Demandes common sans groupe common : 0 ligne attendue.
SELECT r.group_id, r.member_id
FROM common.g_group_user_ask_to_join AS r
LEFT JOIN common.g_groups AS g ON g.group_id = r.group_id
WHERE g.group_id IS NULL
ORDER BY r.group_id, r.member_id;

-- 13. Membres common absents de users.users : 0 ligne attendue.
SELECT u.group_id, u.member_id
FROM common.g_group_user AS u
LEFT JOIN users.users AS directory_user ON directory_user.id = u.member_id
WHERE directory_user.id IS NULL
ORDER BY u.group_id, u.member_id;

-- 14. Demandes common avec membre absent de users.users : 0 ligne attendue.
SELECT r.group_id, r.member_id
FROM common.g_group_user_ask_to_join AS r
LEFT JOIN users.users AS directory_user ON directory_user.id = r.member_id
WHERE directory_user.id IS NULL
ORDER BY r.group_id, r.member_id;

-- 15. Animations LSS pointant vers un groupe absent de common : 0 ligne attendue.
SELECT a.animation_id, a.group_id
FROM lss.a_animations AS a
LEFT JOIN common.g_groups AS g ON g.group_id = a.group_id
WHERE g.group_id IS NULL
ORDER BY a.animation_id;

-- 16. Verification non destructive de l'identity common.g_groups.group_id.
-- sequence_last_value doit etre superieur ou egal a max_group_id.
SELECT
  group_bounds.max_group_id,
  sequences.last_value AS sequence_last_value,
  sequences.last_value - group_bounds.max_group_id AS sequence_delta
FROM (
  SELECT COALESCE(MAX(group_id), 0) AS max_group_id
  FROM common.g_groups
) AS group_bounds
CROSS JOIN LATERAL (
  SELECT last_value
  FROM pg_sequences
  WHERE schemaname = 'common'
    AND sequencename = (
      SELECT relname
      FROM pg_class
      WHERE oid = pg_get_serial_sequence('common.g_groups', 'group_id')::regclass
    )
) AS sequences;
