# Transitions De Projection

## Objectif

Ce document décrit le fonctionnement actuellement implémenté des transitions de projection dans `app_animation`.

Il remplace les anciennes spécifications de chantier.
Le code actuel reste la source de vérité fonctionnelle.

La documentation distingue deux parties :
- le fonctionnement runtime stable, qui décrit comment la projection applique une transition ;
- le catalogue évolutif, qui décrit quelles transitions sont actuellement disponibles et comment elles sont paramétrées.

## Principe Runtime Stable

La projection repose sur trois responsabilités séparées.

### Animation

Une `Animation` est une configuration persistée.

Elle porte :
- la playlist ordonnée ;
- les paramètres visuels par défaut ;
- les overrides par chant et par couplet ;
- une transition par défaut (`default_transition`).

La transition par défaut initialise une nouvelle session de projection.
Elle ne représente pas l'état live courant.

Modifier la transition par défaut d'une animation ne modifie donc pas silencieusement une session de projection déjà ouverte.

### Remote

La remote `lyrics_slide_show.html` est l'autorité runtime.

Elle maintient :
- l'identifiant local de session écran ;
- l'état de navigation courant ;
- la transition active ;
- les raccourcis et actions live ;
- les données fraîches issues du payload Django.

Chaque nouvel ordre réel d'affichage envoyé au display contient :
- un frame complet à rendre ;
- la transition à appliquer pour atteindre ce frame.

Changer la transition active dans la remote ne modifie pas le frame déjà projeté.
Le changement s'applique au prochain ordre d'affichage.

### Display

Le display `lyrics_slide_show_display.html` est une surface de rendu.

Il applique les messages reçus et ne reconstruit pas l'état métier de l'animation.
Si un ordre d'affichage contient une transition, cette transition fait foi pour ce changement d'écran.

Une transition absente, inconnue ou inutilisable se replie sur `direct`.

## Contrat Actuel

Une seule transition par défaut existe aujourd'hui au niveau `Animation`.

Il n'existe actuellement pas de transition configurée :
- par slide ;
- par chant ;
- par bloc de texte ;
- par couplet.

La remote possède une transition active live, restaurée avec l'état local de la session remote (`lss-lyrics-master-state:<animationId>`).
Cette valeur n'est pas sauvegardée dans l'animation.

La remote expose :
- un sélecteur de transition ;
- l'action `Transition suivante` ;
- l'action `Forcer Direct`.

`Transition suivante` suit l'ordre des transitions activées dans le manifeste.
`Forcer Direct` sélectionne `direct` pour les prochains ordres d'affichage.

## Manifeste Technique

Le catalogue des transitions est défini par `app_animation/transitions.json`.

Ce fichier est :
- versionné avec le code ;
- lu par Django ;
- non modifiable par les utilisateurs ;
- non stocké en base ;
- la source de vérité pour la liste, l'ordre, l'activation et les paramètres techniques simples.

Structure minimale :

```json
{
  "default": "direct",
  "transitions": [
    {
      "id": "direct",
      "label_key": "transition_direct",
      "enabled": true,
      "order": 0,
      "params": {
        "duration_ms": 0
      }
    }
  ]
}
```

Chaque transition déclare au minimum :
- `id` : identifiant technique stable ;
- `label_key` : clé i18n résolue par Django ;
- `enabled` : disponibilité dans les formulaires, la remote et le cycle ;
- `order` : ordre d'affichage et ordre du cycle ;
- `params` : paramètres techniques propres à la transition.

Le manifeste ne contient pas d'algorithme graphique, de CSS, de classes DOM ni de code JavaScript.
Déclarer une transition dans le manifeste ne suffit donc pas à la rendre fonctionnelle : le code Django et le code JavaScript doivent aussi savoir l'exposer, la valider et l'exécuter.

## Transitions Actuelles

Catalogue actuellement activé :

| Identifiant | Libellé FR | Paramètres | Comportement |
| --- | --- | --- | --- |
| `direct` | `Direct` | `duration_ms: 0` | remplacement immédiat |
| `fade` | `Fondu` | `duration_ms: 500` | apparition du nouveau frame par opacité |
| `wipe` | `Balayage` | `duration_ms: 400`, `direction: left_to_right` | révélation du nouveau frame de gauche à droite |

Les identifiants sont techniques, stables et indépendants des libellés traduits.

`wipe_horizontal` n'est pas un identifiant valide.
L'identifiant actuel est `wipe`, afin de ne pas lier durablement la transition à une direction unique.

## Lecture Django

Le module `app_animation.transitions` centralise la lecture et la validation du manifeste.

Il expose notamment :
- le manifeste validé ;
- la transition par défaut ;
- toutes les transitions ;
- les transitions activées ;
- les `choices` Django ;
- les options destinées aux popups/templates ;
- le catalogue runtime transmis à la remote ;
- la résolution d'une transition activée avec fallback.

Les formulaires et vues ne doivent pas maintenir de liste parallèle.

Une transition désactivée (`enabled: false`) :
- n'est plus proposée dans les formulaires ;
- n'est plus proposée dans la remote ;
- n'apparaît plus dans le cycle `Transition suivante` ;
- peut rester implémentée côté display.

Une transition persistée mais désactivée se replie sur la transition système par défaut résolue par Django.

## Contrat Remote Vers Display

Les messages d'affichage réels transportent un frame complet et une transition.

Forme conceptuelle :

```json
{
  "type": "frame",
  "frame": {
    "mode": "slide"
  },
  "transition": {
    "id": "wipe",
    "params": {
      "duration_ms": 400,
      "direction": "left_to_right"
    }
  }
}
```

Le protocole réel reste celui du JavaScript existant.
Le point fonctionnel important est que le display n'a pas besoin de lire directement le manifeste.
La remote transmet la configuration runtime nécessaire.

Frames concernées :
- `idle` ;
- `slide` ;
- `black` ;
- `qr` ;
- `f11-reminder`.

Le heartbeat peut transporter de l'état technique, mais sa réception ne déclenche jamais de transition visuelle.

Les doublons de transport sont filtrés par `nonce`.
La déduplication ne repose jamais sur le contenu du frame, le texte, le chant, la slide ou le `projectionIndex`.

## Display Et Stratégies JS

Le display utilise deux couches plein écran superposées :
- une couche active visible ;
- une couche inactive utilisée pour rendre le frame entrant.

À la réception d'un ordre valide :
1. le message est filtré par session et par `nonce` ;
2. la transition demandée est résolue avec fallback `direct` ;
3. le frame entrant est rendu dans la couche inactive ;
4. la stratégie de transition est exécutée ;
5. la couche entrante devient active ;
6. les styles temporaires sont nettoyés.

Le renderer de frame est commun.
Les transitions ne possèdent pas leur propre logique métier de rendu.

Le code JavaScript du display maintient la liste des identifiants qu'il sait exécuter et route chaque identifiant vers son comportement graphique.
Cette couche ne doit pas recopier les libellés, l'ordre, l'activation ou les durées du manifeste.

Les stratégies consomment les paramètres transmis par la remote.
Si une stratégie échoue ou si l'identifiant est inconnu, le frame entrant est affiché immédiatement en comportement `direct`.

## Ajouter Une Transition

Le catalogue est volontairement évolutif.

Ajouter une nouvelle transition n'est pas une simple édition du manifeste.
Le manifeste annonce une capacité, mais l'implémentation doit être développée dans toute la chaîne runtime.

Instructions à suivre :
- choisir un identifiant technique stable en anglais, sans dépendance au libellé affiché ;
- ajouter la transition dans `app_animation/transitions.json` avec `label_key`, `enabled`, `order` et uniquement les paramètres utiles ;
- ajouter la clé `label_key` dans le mapping Django des labels de transition, puis ajouter les traductions ;
- adapter la validation Django du manifeste si la transition introduit de nouveaux paramètres ou contraintes ;
- vérifier que `AnimationForm`, les options de popup et le payload runtime continuent à provenir des helpers Django, sans liste parallèle ;
- développer le comportement graphique dans `static/js/lyrics_slide_show_display.js` ;
- déclarer l'identifiant comme supporté côté display et le router vers sa stratégie ;
- faire consommer à la stratégie les paramètres reçus dans le message, sans durée ou option contradictoire codée en dur ;
- conserver le fallback `direct` en cas d'identifiant inconnu, de paramètres invalides ou d'erreur d'exécution ;
- ajouter ou adapter les tests de manifeste, i18n, exposition Django, payload runtime et support display.

Une transition ne doit être mise en `enabled: true` que lorsque la stratégie display correspondante existe et que les tests de base sont couverts.
Si une transition est en développement ou temporairement instable, elle doit rester `enabled: false`.

Les formulaires, templates et la logique générique de cycle ne doivent pas dépendre d'une liste codée en dur.

## Évolutions Futures De Priorité

Une évolution future vers une transition par chant, par slide ou par bloc ne doit pas modifier les responsabilités fondamentales :
- la remote reste l'autorité runtime ;
- le display reste une surface de rendu ;
- le message d'affichage transporte la transition résolue ;
- le fallback sûr reste `direct`.

Le point d'intégration naturel de ces futures priorités est le resolveur de transition.
La priorité pourrait évoluer plus tard vers une chaîne du type :

```text
choix live remote -> transition de slide -> transition de chant -> préférence animation -> direct
```

Cette chaîne n'est pas implémentée aujourd'hui.
Aucun champ, payload ou contrôle utilisateur ne doit être documenté comme existant pour ces niveaux tant que le code ne les porte pas.

## Hors-Périmètre Actuel

Le fonctionnement actuel n'expose pas :
- de durée configurable par utilisateur ;
- de direction configurable par utilisateur ;
- de transition par slide ;
- de transition par chant ;
- de transition par bloc ;
- de table SQL de transitions ;
- de chargement dynamique de plugins de transition ;
- de cache fonctionnel de slides dans le display.

## Validation Attendue

Les tests et vérifications doivent couvrir :
- validation du manifeste ;
- ordre `direct`, `fade`, `wipe` pour le catalogue actuel ;
- absence de l'identifiant `wipe_horizontal` ;
- exposition des choix depuis Django ;
- fallback `direct` pour une valeur inconnue ou désactivée ;
- présence des stratégies JS pour les transitions activées ;
- non-rejeu visuel sur heartbeat ;
- déduplication par `nonce` ;
- conservation du rendu simple et double existant.
