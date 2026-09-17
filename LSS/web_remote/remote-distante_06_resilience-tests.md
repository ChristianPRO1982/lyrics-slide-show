# Remote distante — 06 Résilience et tests

## Objectif

Vérifier que la télécommande distante reste une fonctionnalité de confort et ne fragilise jamais la projection locale.

Ce document complète les lots `00` à `05`.

## Principe principal

> Si la fonctionnalité distante tombe, la projection locale continue normalement.

## Scénarios à tester

### Greffon Inactif

Sans session distante active :

* la remote master actuelle fonctionne comme avant ;
* `lyrics_slide_show_master.js` initialise son état local normalement ;
* le display local reçoit toujours les frames via `BroadcastChannel` ou `localStorage` ;
* le QR public actuel des paroles reste inchangé ;
* aucune connexion WebSocket distante n'est nécessaire pour projeter.

### Perte d'Internet

Si Internet devient indisponible :

* la remote master continue de fonctionner ;
* clavier et pédalier continuent de fonctionner ;
* l'afficheur n'est pas affecté ;
* les remotes distantes passent en état de reconnexion.

### Reconnexion d'une remote distante

Après reconnexion :

* récupérer le dernier `STATE` ;
* reprendre l'affichage normal ;
* ne rejouer aucune commande ancienne.

### Master indisponible

Si la master quitte le canal distant :

```text
remote distante
→ MASTER_UNAVAILABLE
```

Aucune commande distante ne doit être mise en attente.

### Plusieurs remotes

Tester plusieurs remotes connectées à la même session.

Après chaque modification, toutes doivent converger vers le même `STATE`.

### Commandes concurrentes

Exemple :

```text
Remote A → NEXT_SLIDE
Remote B → NEXT_SLIDE pendant le cooldown
```

Résultat attendu :

```text
A → COMMAND_ACCEPTED
B → COMMAND_REJECTED / COOLDOWN
```

Puis les deux reçoivent le même nouvel `STATE`.

### Commande locale pendant le cooldown

Une action locale doit toujours être exécutée immédiatement, même pendant le cooldown distant.

```text
Remote distante → NEXT_SLIDE
Remote master → PREVIOUS_SLIDE
```

La commande locale n'est jamais bloquée.

Le dernier état de la master devient l'état autoritaire.

### Black Mode

Vérifier la synchronisation du Black Mode entre :

* master ;
* afficheur ;
* toutes les remotes distantes.

### Désactivation

Lorsqu'une session distante est désactivée :

* les remotes sont déconnectées ;
* les nouvelles commandes sont refusées ;
* l'ancien accès devient invalide ;
* la projection locale continue.

### Ancien token

Un token issu d'une ancienne session ne doit jamais permettre de contrôler une nouvelle projection.

### Déploiement Multi-Workers

Avec plusieurs workers ou processus :

* la validation du token ne dépend pas de la mémoire process ;
* l'expiration de session reste cohérente ;
* le cooldown distant reste partagé ;
* une session désactivée est refusée par tous les workers.

## Tests de non-régression

Vérifier également le fonctionnement de LSS sans activer la fonctionnalité distante :

* navigation des slides ;
* navigation des chants ;
* clavier ;
* pédalier ;
* Black Mode ;
* transitions ;
* afficheur.

Le comportement existant doit rester inchangé.

Vérifier en particulier que :

* l'afficheur ne connaît pas la remote distante ;
* le bridge local master → display conserve son protocole ;
* `BLACK MODE`, QR public et transitions restent pilotés par la master.

## Tests Techniques Attendus

### Tests Django

Prévoir des tests `TestCase` pour :

* création de session distante persistée en PostgreSQL ;
* génération de token non prédictible ;
* refus d'une session inactive ou expirée ;
* invalidation d'un ancien token après désactivation ;
* cooldown partagé entre commandes distantes ;
* refus des commandes sans master connectée.

### Tests JavaScript Ciblés

Prévoir des tests ou assertions ciblées sur l'adaptateur master :

* `handleExternalCommand` existe comme point d'entrée unique ;
* les commandes simples appellent les actions locales existantes ;
* `GO_TO_SONG` utilise `animation_song_id` ;
* `GO_TO_PROJECTION_STEP` utilise `projection_index` ;
* une cible invalide est rejetée sans modifier l'état local.

### Tests De Transport

Prévoir des tests de protocole WebSocket pour :

* connexion master avec session valide ;
* connexion remote distante avec token valide ;
* rejet d'un token invalide ;
* diffusion d'un `STATE` de la master vers toutes les remotes ;
* rejet immédiat d'une commande pendant cooldown.

## Critère de validation

La fonctionnalité est considérée robuste si une panne complète du système distant peut être provoquée sans interrompre ni perturber la projection locale.
