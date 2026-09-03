# Remote distante — 06 Résilience et tests

## Objectif

Vérifier que la télécommande distante reste une fonctionnalité de confort et ne fragilise jamais la projection locale.

Ce document complète les lots `00` à `05`.

## Principe principal

> Si la fonctionnalité distante tombe, la projection locale continue normalement.

## Scénarios à tester

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

## Critère de validation

La fonctionnalité est considérée robuste si une panne complète du système distant peut être provoquée sans interrompre ni perturber la projection locale.
