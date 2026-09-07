# Template group `includes/_song_*.html`

## Périmètre

- `includes/_song_actions.html`
- `includes/_song_metadata.html`
- `includes/_song_links.html`
- `includes/_active_search_tags.html`

## Rôle

Partiels partagés par plusieurs pages de `app_song`.

## Responsabilité front

- `_song_actions.html`
  - affiche `← Retour à la liste`
  - affiche `Afficher` si la page courante n’est pas déjà `song`
  - pour utilisateur authentifié, affiche le toggle favori
  - si l’utilisateur peut éditer le chant, affiche `Modifier`, `Métadonnées` et `Supprimer`
  - pour chant validé et utilisateur authentifié sans droit d’édition directe, affiche `Signaler une correction`
- `_song_metadata.html`
  - affiche artistes et groupes sous forme de badges
  - affiche les genres groupés par famille
  - chaque badge peut devenir un lien de recherche rapide si `add_url` est fourni
- `_song_links.html`
  - affiche la liste des liens du chant
  - chaque ligne garde l’URL complète comme cible du lien
  - le texte visible du lien est compacté au domaine racine pour une URL externe
  - un lien interne relatif s’affiche avec le libellé `Lyrics Slide Show`
  - si plusieurs liens partagent le même libellé compact, chaque ligne reçoit un marqueur `①` à `⑳`, puis le nombre brut au-delà
  - chaque ligne montre aussi le libellé localisé du type de lien
- `_active_search_tags.html`
  - affiche les filtres de recherche actifs et leurs actions de retrait

## Notes

- `_song_actions.html` s’insère à plat dans les panneaux outils et mobile
- les autorisations et effets backend des actions sont décrits dans `functional_requirements.md`
