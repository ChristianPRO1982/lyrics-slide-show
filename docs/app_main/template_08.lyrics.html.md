# Design du template `lyrics.html`

## Rôle

Template autonome optimisé smartphone pour la lecture publique des paroles.

Il est utilisé par les vues de lecture de paroles qui passent par `build_lyrics_page_context`, notamment la vue smartphone publique d’une animation.

Il ne reprend pas le shell principal du site.

## Données Attendues

- `page_title`,
- `share_url`,
- `qr_code_png_base64`,
- `songs`,
- `has_multiple_songs`,
- `animation_title`,
- `drawer_title`,
- `drawer_link_url`,
- `drawer_link_label`,
- `is_animation_view`.

Chaque entrée de `songs` contient :

- `song_id`,
- `song_title`,
- `song_url`,
- `anchor_id`,
- `blocks`.

Chaque bloc contient :

- `prefix`,
- `style`,
- `text`.

Styles supportés :

- `1` = refrain,
- `2` = couplet standard,
- `3` = `chorus_like`.

## Structure Générale

- barre latérale fixe à gauche,
- topbar fixe avec sélecteur de chant si plusieurs chants existent,
- tiroir latéral masqué par défaut,
- zone principale dédiée à la lecture.

Le CSS et le JavaScript sont embarqués directement dans le HTML.

## Rendu Des Paroles

- le titre d’animation est affiché au-dessus des chants quand `animation_title` existe ;
- chaque chant affiche son titre ;
- les blocs utilisent `white-space: pre-wrap` ;
- les blocs `chorus` et `chorus_like` sont en gras ;
- les préfixes sont en italique ;
- `chorus_like` insère un saut de ligne après le préfixe quand il existe ;
- un séparateur horizontal apparaît entre deux chants.

## Navigation Entre Chants

Si plusieurs chants sont présents :

- un `<select>` fixe liste les chants dans l’ordre fourni ;
- les boutons latéraux `chant précédent` / `chant suivant` sont affichés ;
- le changement de sélection déclenche un scroll vers le chant ciblé ;
- le scroll manuel met aussi à jour le chant courant du `<select>`.

Le template gère le décalage nécessaire pour garder le chant visible sous la topbar fixe.

Si un seul chant est présent :

- la topbar est masquée ;
- les boutons précédent/suivant ne sont pas rendus.

## Barre Latérale

La barre latérale affiche des boutons images pour :

- ouvrir le menu,
- agrandir le texte,
- réduire le texte,
- basculer clair/sombre,
- aller au chant précédent / suivant si plusieurs chants existent.

## Tiroir Latéral

Le tiroir contient :

- un bouton de fermeture,
- le QR code de `share_url` quand disponible,
- le titre `drawer_title`,
- un champ readonly contenant `share_url`,
- un bouton `Copier`,
- le logo Lyrics Slide Show,
- un lien `drawer_link_url` / `drawer_link_label` quand fourni.

## Persistance Et Thème

- la page a son propre thème clair/sombre, indépendant des thèmes principaux du site ;
- au chargement, elle suit `prefers-color-scheme` ;
- l’override manuel clair/sombre n’est pas persisté entre rechargements ;
- tant qu’aucun override manuel n’a eu lieu, un changement du thème système met la page à jour ;
- la taille de police est persistée en `localStorage` pour toutes les pages `lyrics.html`.

## Contraintes Visuelles

- police système simple et lisible ;
- mode clair façon parchemin ;
- mode sombre très contrasté ;
- mise en page pensée pour un smartphone en portrait.
