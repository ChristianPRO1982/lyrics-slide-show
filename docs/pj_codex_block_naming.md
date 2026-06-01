# Relation PJ-Codex pour nommer les blocs de page

Ce document définit la nomenclature à utiliser dans les prompts adressés à Codex pour désigner les blocs visibles de la structure de page.

Objectif :

- éviter de nommer les blocs par leurs classes CSS brutes ;
- utiliser des noms stables, courts et sans ambiguïté ;
- permettre de demander facilement où ajouter, remplacer, déplacer ou supprimer un texte.

## Règle générale

Dans les prompts, nommer les blocs par leur rôle fonctionnel.

Éviter par défaut :

- `bloc class="site-panel site-section-panel"`
- `bloc class="site-panel site-tools-panel"`
- `bloc class="site-panel site-main-panel"`
- `bloc class="site-panel site-mobile-side"`
- `bloc class="site-main-heading"`
- `bloc class="site-main-aside"`
- `bloc class="site-main-footer"`
- `bloc class="site-theme-card"`

Préférer :

- `panneau section`
- `panneau outils`
- `panneau principal`
- `panneau mobile`
- `en-tête principal`
- `encadré résumé`
- `pied de contenu`
- `carte de thème`

## Tableau de correspondance

| Nom à utiliser dans les prompts | Nature | Obligatoire | Bloc Django principal | Classe CSS / élément réel | Rôle |
| --- | --- | --- | --- | --- | --- |
| `panneau section` | panneau latéral | oui | `section_title`, `section_intro`, `section_nav` | `<section class="site-panel site-section-panel">` | navigation ou structure de la section courante |
| `panneau outils` | panneau latéral | oui | `tools_title`, `tools_intro`, `page_tools` | `<section class="site-panel site-tools-panel">` | actions, raccourcis, outils, liens pratiques |
| `panneau principal` | conteneur principal | oui | englobe `page_kicker`, `page_title`, `page_intro`, `page_summary`, `content`, `content_footer` | `<main class="site-panel site-main-panel">` | zone centrale complète de la page |
| `panneau mobile` | panneau latéral mobile | oui | `mobile_side_title`, `mobile_side_intro`, `mobile_side_content` | `<section class="site-panel site-mobile-side">` | navigation et actions condensées pour la mise en page mobile |
| `en-tête principal` | sous-bloc du panneau principal | oui | `page_kicker`, `page_title`, `page_intro` | `<div class="site-main-heading">` | sur-titre, titre principal, texte d’introduction |
| `encadré résumé` | sous-bloc du panneau principal | oui | `page_summary` | `<div class="site-main-aside">` | résumé, aide courte, mémo, informations secondaires |
| `contenu principal` | zone de contenu | oui | `content` | `<section class="site-main-content">` | corps principal de la page |
| `pied de contenu` | bloc de bas de contenu | non | `content_footer` | `<section class="site-main-footer">` | complément, note, rappel, bloc secondaire final |
| `carte de thème` | carte unitaire | non | contenu spécifique de template | `<article class="site-theme-card">` | une carte de sélection de thème |

## Détail fin par bloc Django

### Panneau section

Nom à utiliser :

- `panneau section`

Sous-parties nommables :

- `titre du panneau section` pour `section_title`
- `intro du panneau section` pour `section_intro`
- `contenu du panneau section` pour `section_nav`

Usages typiques :

- navigation locale ;
- liste de rubriques ;
- état de la section ;
- liens de contexte.

### Panneau outils

Nom à utiliser :

- `panneau outils`

Sous-parties nommables :

- `titre du panneau outils` pour `tools_title`
- `intro du panneau outils` pour `tools_intro`
- `contenu du panneau outils` pour `page_tools`

Usages typiques :

- boutons d’action ;
- raccourcis ;
- liens annexes ;
- commandes secondaires.

### Panneau principal

Nom à utiliser :

- `panneau principal`

Ce nom désigne toute la grande colonne centrale.

À utiliser quand la demande concerne l’ensemble de la zone centrale et non un sous-bloc précis.

Exemples :

- ajouter un nouveau bloc dans le panneau principal ;
- réorganiser les blocs du panneau principal ;
- alléger la structure du panneau principal.

### Panneau mobile

Nom à utiliser :

- `panneau mobile`

Sous-parties nommables :

- `titre du panneau mobile` pour `mobile_side_title`
- `intro du panneau mobile` pour `mobile_side_intro`
- `contenu du panneau mobile` pour `mobile_side_content`

Usages typiques :

- navigation compacte sur mobile ;
- actions prioritaires en petit écran ;
- rappel de contexte dans une mise en page resserrée ;
- liens utiles destinés à la version mobile.

### En-tête principal

Nom à utiliser :

- `en-tête principal`

Sous-parties nommables :

- `sur-titre` pour `page_kicker`
- `titre principal` pour `page_title`
- `texte d’introduction` pour `page_intro`

Usages typiques :

- présenter la page ;
- introduire l’objectif ;
- résumer la promesse ou le contexte.

### Encadré résumé

Nom à utiliser :

- `encadré résumé`

Sous-partie nommable :

- `résumé de page` pour `page_summary`

Usages typiques :

- informations synthétiques ;
- rappel court ;
- aide de lecture ;
- indicateurs ou points clés.

### Contenu principal

Nom à utiliser :

- `contenu principal`

Sous-partie nommable :

- `contenu de page` pour `content`

Usages typiques :

- cartes de contenu ;
- formulaires ;
- tableaux ;
- listes ;
- explications détaillées.

### Pied de contenu

Nom à utiliser :

- `pied de contenu`

Sous-partie nommable :

- `contenu du pied de page principal` pour `content_footer`

Usages typiques :

- note complémentaire ;
- bloc de rappel ;
- aide secondaire ;
- zone informative finale.

Règle :

- ce bloc est optionnel ;
- s’il est vide, il reste présent dans la structure mais sans contenu utile.

### Carte de thème

Nom à utiliser :

- `carte de thème`

Nom plus précis possible :

- `carte de thème Clair`
- `carte de thème Sombre`
- `carte de thème <nom>`

Usages typiques :

- modifier le titre d’une carte ;
- modifier son texte ;
- modifier son état actif ;
- ajouter une information dans une carte précise.

## Vocabulaire recommandé dans les prompts

Formulations simples recommandées :

- `Ajoute ce texte dans l’en-tête principal.`
- `Remplace le texte d’introduction dans l’en-tête principal.`
- `Mets cette liste dans le panneau outils.`
- `Ajoute ce lien dans le panneau mobile.`
- `Réécris le résumé dans l’encadré résumé.`
- `Ajoute une note dans le pied de contenu.`
- `Change le texte de la carte de thème Clair.`
- `Ajoute un nouveau bloc dans le contenu principal.`
- `Déplace ce paragraphe du panneau outils vers l’encadré résumé.`

Formulations encore plus précises :

- `Remplace le sur-titre.`
- `Remplace le titre principal.`
- `Réécris le texte d’introduction.`
- `Change le titre du panneau section.`
- `Ajoute une phrase dans l’intro du panneau outils.`
- `Remplace le contenu du panneau mobile.`
- `Remplace le contenu du panneau section.`
- `Ajoute une carte dans le contenu principal.`

## Vocabulaire à éviter

Éviter sauf en cas de besoin technique explicite :

- les noms de classes CSS bruts ;
- `bloc de gauche`, car il peut devenir ambigu selon le responsive ;
- `bloc du haut`, car plusieurs blocs sont en haut ;
- `bloc principal`, s’il ne désigne pas clairement le `panneau principal` complet ;
- `sidebar`, `hero`, `footer`, sauf si Codex connaît déjà exactement la convention visée.

## Ambiguïtés à éviter

Ne pas écrire seulement :

- `mets ce texte dans le header`
- `mets ce texte dans l’aside`
- `ajoute ce bloc dans le panel`
- `change le footer`

Préférer :

- `mets ce texte dans l’en-tête principal`
- `mets ce texte dans l’encadré résumé`
- `ajoute ce bloc dans le panneau outils`
- `ajoute cette note dans le pied de contenu`

## Faut-il utiliser des backticks ?

Non, ce n’est pas obligatoire.

Ces formulations sont suffisantes sans backticks :

- ajoute ce texte dans l’en-tête principal
- remplace le résumé dans l’encadré résumé
- mets cette liste dans le panneau outils

Les backticks sont utiles seulement dans les cas suivants :

- tu cites un nom de bloc exact comme convention de travail : `en-tête principal`
- tu cites un nom de bloc Django : `page_title`
- tu cites une classe CSS ou un sélecteur : `site-main-heading`
- tu veux lever toute ambiguïté dans un prompt long

Règle pratique :

- pour les demandes normales en français naturel, pas besoin de backticks ;
- pour les noms techniques, les identifiants de bloc Django ou les classes CSS, utiliser des backticks est préférable.

## Modèle de prompt recommandé

Structure courte :

1. action ;
2. bloc cible ;
3. position éventuelle ;
4. texte ou intention.

Exemples :

1. `Ajoute dans l’en-tête principal, sous le titre principal, le texte suivant : ...`
2. `Remplace le résumé de page dans l’encadré résumé par : ...`
3. `Dans le panneau outils, ajoute un lien secondaire intitulé : ...`
4. `Dans le contenu principal, crée une nouvelle carte avec ce titre et ce texte : ...`
5. `Dans le pied de contenu, ajoute une note courte expliquant : ...`

## Convention finale à retenir

Noms de référence à utiliser dans les échanges PJ-Codex :

- `panneau section`
- `panneau outils`
- `panneau principal`
- `en-tête principal`
- `encadré résumé`
- `contenu principal`
- `pied de contenu`
- `carte de thème`

Sous-noms utiles :

- `sur-titre`
- `titre principal`
- `texte d’introduction`
- `résumé de page`
- `titre du panneau section`
- `intro du panneau section`
- `contenu du panneau section`
- `titre du panneau outils`
- `intro du panneau outils`
- `contenu du panneau outils`
