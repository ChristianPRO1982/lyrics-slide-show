# Remote distante — 04 Gestion depuis la master

## Objectif

Ajouter dans la remote master les éléments nécessaires pour activer, superviser et désactiver la télécommande distante.

Ce document complète les lots `00` à `03`.

## Activation

La fonctionnalité distante doit être inactive par défaut.

Depuis la remote master, l'utilisateur peut activer une session distante.

L'activation doit :

* créer ou activer la session live ;
* générer un accès temporaire sécurisé ;
* connecter la master au canal temps réel ;
* rendre l'accès distant utilisable immédiatement.

## Affichage de l'accès

Une fois activée, la remote master doit afficher au minimum :

* un QR code ;
* un lien d'accès distant ;
* l'état de la session ;
* le nombre de remotes distantes connectées.

Exemple conceptuel :

```text
Télécommande distante : active

[ QR CODE ]

2 télécommandes connectées

[ Désactiver ]
```

Le token technique ne doit pas être affiché séparément s'il est déjà intégré au lien.

## Désactivation

La désactivation doit :

* invalider l'accès distant ;
* fermer la session distante ;
* déconnecter les remotes distantes ;
* empêcher toute nouvelle commande distante.

La projection locale continue normalement.

## Statuts

Prévoir des états simples :

```text
INACTIVE
ACTIVE
MASTER_CONNECTING
MASTER_CONNECTED
ERROR
```

L'interface doit rester compréhensible sans exposer les détails techniques.

## État des remotes

Afficher le nombre de remotes connectées.

Une gestion détaillée appareil par appareil n'est pas nécessaire en V1.

## Indépendance locale

Une erreur du système distant ne doit jamais :

* bloquer les boutons de la master ;
* bloquer le clavier ou le pédalier ;
* interrompre l'afficheur ;
* fermer la projection locale.

En cas d'erreur, seule la fonctionnalité distante doit être signalée comme indisponible.

## Cycle de vie

La session distante est liée à la session live de projection.

Elle ne doit pas survivre inutilement à la fermeture ou à la fin de la projection.

Un ancien lien distant ne doit pas permettre de reprendre le contrôle d'une nouvelle session.

## Contraintes

Ne pas implémenter dans ce lot :

* l'UI mobile finale ;
* rôles ou permissions avancés ;
* gestion individuelle des remotes ;
* historique des connexions ;
* paramètres utilisateur complexes.

L'objectif est une gestion simple : **activer, partager, voir l'état, désactiver**.
