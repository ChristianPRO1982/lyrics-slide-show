Je veux mettre en place un SEO propre et maintenable pour Lyrics Slide Show, sans chercher une optimisation SEO professionnelle poussée.

Avant de modifier le code, analyse l’architecture Django existante et réutilise au maximum les mécanismes déjà présents, notamment `templates/base.html`, les templates applicatifs et les URL existantes.

Ne modifie pas les URL publiques existantes, le fonctionnement métier, l’authentification Keycloak, les recherches, les permissions ni la navigation sauf si cela est strictement nécessaire au SEO.

## Objectif général

Lyrics Slide Show doit être clairement compris par Google et Bing comme :

- une application gratuite de gestion et de projection de chants ;
- permettant de rechercher des chants ;
- proposant des pages publiques individuelles pour les chants ;
- disposant de groupes permettant d’organiser l’usage ;
- avec une documentation externe sur le Wiki GitHub.

Le cœur SEO du site est :

1. `/songs/`
2. `/songs/<song_id>/`
3. la homepage
4. `/groups/`

Le reste est secondaire ou doit être exclu de l’index.

## Politique d’indexation

Appliquer cette politique :

### INDEX très important

- `/songs/`
- `/songs/<song_id>/`

Toutes les pages publiques individuelles de chants doivent être indexables et présentes dans le sitemap.

### INDEX important

- `/`
- `/groups/`

Attention : seule la liste publique `/groups/` est indexable.

Les pages de modification/gestion d’un groupe, notamment `/groups/<group_id>/` si elles correspondent à de la gestion métier, ne doivent pas être indexées.

### INDEX

- `/privacy-policy/`
- `/login/`

Le Wiki GitHub reste externe au site Django :
`https://github.com/ChristianPRO1982/lyrics-slide-show/wiki`

Ne pas mettre les URL GitHub dans le sitemap LSS.

### NOINDEX

Au minimum :

- `/animations/` et toutes les pages fonctionnelles dessous ;
- `/themes/`
- `/language/`
- `/account/`
- `/site-params/`
- `/login/diagnostic/`
- `/auth/callback/`
- `/provision/redirect/`
- `/provision/complete/`
- `/logout/`
- `/heavy/` et ses dépendances ;
- toutes les interfaces de création/modification/administration ;
- `/songs/<id>/modify/`
- les interfaces de modification des genres, artistes, groupes musicaux, préfixes ;
- les endpoints techniques liés aux messages, métadonnées, popups ou rendus de texte qui ne sont pas des pages publiques autonomes destinées à Google ;
- toute future page métier non explicitement déclarée publique.

Je préfère une approche sécurisante :

**les pages sont `noindex, follow` par défaut et seules les pages publiques listées ci-dessus optent explicitement pour l’indexation.**

Ainsi une future page métier ne deviendra pas indexable accidentellement.

Ne pas utiliser `robots.txt` pour empêcher Google d’accéder aux pages `noindex`, car le crawler doit pouvoir lire la directive `noindex`.

## Socle SEO commun dans `base.html`

Centraliser proprement les éléments suivants :

- `<title>`
- `meta description`
- `meta robots`
- URL canonical
- Open Graph minimal :
  - `og:title`
  - `og:description`
  - `og:url`
  - `og:type`
  - `og:site_name`

Éviter de dupliquer le `<head>` dans chaque template.

Prévoir des blocs ou variables Django permettant aux pages importantes de personnaliser ces informations.

Les pages indexables doivent avoir une canonical absolue en HTTPS sur :

`https://lss.carthographie.fr/...`

Les pages `noindex` ne doivent pas envoyer de signaux contradictoires.

## Homepage `/`

Conserver son contenu et son fonctionnement actuels.

Vérifier :

- un seul H1 réellement descriptif ;
- un `<title>` explicitant Lyrics Slide Show ;
- une vraie `meta description`.

La description doit expliquer naturellement qu’il s’agit d’un outil gratuit permettant de gérer, rechercher, organiser et projeter des chants pour des animations, célébrations, concerts ou usages similaires.

Ne pas faire de keyword stuffing.

La homepage doit contenir des liens HTML crawlables vers :

- `/songs/`
- `/groups/`
- la documentation GitHub Wiki
- éventuellement `/login/` et `/privacy-policy/`

Le Wiki GitHub doit rester un lien externe normal, sans `nofollow`.

## Catalogue `/songs/`

C’est la page publique la plus importante du site.

Elle doit avoir :

- un `<title>` spécifique ;
- une `meta description` spécifique ;
- un H1 expliquant clairement qu’il s’agit de la recherche/catalogue de chants de Lyrics Slide Show ;
- une canonical vers :
  `https://lss.carthographie.fr/songs/`

La version de base `/songs/` doit être indexable.

Les variantes produites par des paramètres de recherche, filtres, favoris, validation, modération, pagination ou autres paramètres GET ne doivent pas créer des milliers de pages indexables.

Pour ces variantes :

- conserver leur fonctionnement normal pour l’utilisateur ;
- les laisser crawlables ;
- les passer en `noindex, follow` ;
- utiliser `/songs/` comme canonical lorsque le contenu représente simplement une variante filtrée du catalogue.

Ne pas casser les formulaires de recherche.

Tous les chants affichés dans la liste doivent utiliser de vrais liens HTML `<a href>` vers leurs pages individuelles lorsqu’un lien vers le chant est présenté.

## Pages individuelles `/songs/<song_id>/`

Elles sont essentielles au référencement.

Conserver l’URL numérique actuelle : ne pas introduire de slug ni de migration d’URL dans ce chantier.

Pour chaque chant public et indexable :

- title dynamique basé sur le titre du chant, avec `Lyrics Slide Show` en suffixe ;
- H1 = titre du chant ;
- meta description dynamique mais courte et lisible ;
- canonical absolue vers sa propre URL ;
- page présente dans le sitemap.

Construire la meta description uniquement à partir de métadonnées fiables déjà disponibles dans le modèle/contexte : titre, sous-titre, auteur, compositeur, description, références ou informations équivalentes pertinentes.

Ne pas fabriquer artificiellement une description à partir de grandes portions de paroles.

Éviter les descriptions identiques pour tous les chants.

Ne pas modifier les règles actuelles de visibilité ou de validation des chants : seuls les chants réellement publics doivent apparaître dans le sitemap et être indexables.

## `/groups/`

La page racine `/groups/` doit être indexable.

Lui donner :

- un title clair ;
- une meta description expliquant le rôle des groupes dans Lyrics Slide Show ;
- un H1 clair ;
- une canonical propre.

Les pages de gestion/modification d’un groupe ne sont pas indexables.

## Login et confidentialité

`/login/` :
- indexable ;
- title et description simples ;
- canonical propre.

La page doit expliquer que l’authentification permet d’accéder aux fonctionnalités personnelles ou collaboratives de Lyrics Slide Show.

Ne pas essayer d’indexer Keycloak lui-même.

`/privacy-policy/` :
- indexable ;
- title ;
- description ;
- canonical propre.

## Sitemap LSS

Créer :

`https://lss.carthographie.fr/sitemap.xml`

Utiliser de préférence les mécanismes Django adaptés plutôt qu’un XML maintenu manuellement.

Le sitemap doit contenir seulement les URL canoniques indexables :

- `/`
- `/privacy-policy/`
- `/login/`
- `/songs/`
- chaque `/songs/<song_id>/` réellement public
- `/groups/`

Ne jamais inclure :

- paramètres de recherche ;
- animations ;
- thèmes ;
- langue ;
- compte ;
- pages d’administration/modification ;
- callbacks ;
- pages techniques ;
- pages privées ;
- GitHub Wiki.

Ajouter `lastmod` uniquement si une vraie donnée fiable de dernière modification existe déjà. Ne pas inventer de date.

Ne pas ajouter `priority` ou `changefreq` juste pour donner artificiellement plus d’importance à certaines pages.

## robots.txt

Créer ou vérifier :

`https://lss.carthographie.fr/robots.txt`

Objectif simple :

- permettre l’exploration normale ;
- déclarer le sitemap LSS.

Ne pas bloquer par `robots.txt` les pages disposant d’un `noindex`.

## Données structurées

Rester raisonnable.

Sur la homepage uniquement, si cela s’intègre proprement, ajouter un JSON-LD Schema.org correspondant réellement à Lyrics Slide Show, par exemple `WebSite` et/ou `SoftwareApplication`.

Ne pas ajouter de données structurées artificielles uniquement pour multiplier les balises SEO.

Pour les pages de chants, ne pas inventer de schéma complexe si aucun type pertinent n’est clairement adapté aux données disponibles.

## Internationalisation

Le projet possède plusieurs langues d’interface.

Ne pas ajouter `hreflang` sauf si des URL distinctes et stables existent réellement pour chaque version linguistique d’une même page.

Ne pas créer de nouvelles URL uniquement pour ce chantier.

## Tests

Ajouter des tests Django ciblés qui vérifient au minimum :

1. homepage indexable ;
2. `/songs/` indexable sans paramètres ;
3. une page publique `/songs/<id>/` indexable et canonicalisée ;
4. une recherche `/songs/?...` en `noindex`;
5. `/groups/` indexable ;
6. une page de gestion de groupe en `noindex`;
7. `/animations/` en `noindex`;
8. `/themes/` en `noindex`;
9. `/language/` en `noindex`;
10. `/account/` en `noindex`;
11. sitemap contenant les principales URL publiques ;
12. sitemap contenant les chants publics ;
13. sitemap ne contenant aucune URL métier privée ou `noindex`;
14. `robots.txt` déclarant correctement le sitemap.

## Contraintes

- conserver les URL existantes ;
- conserver le comportement fonctionnel existant ;
- ne pas refaire l’UI ;
- ne pas introduire de dépendance SEO externe ;
- privilégier une implémentation Django simple et centralisée ;
- respecter l’architecture actuelle du projet ;
- éviter le sur-engineering ;
- ajouter ou adapter la documentation technique nécessaire.

Avant de coder, fais un court état des lieux des mécanismes existants et indique les fichiers que tu comptes modifier.

Après implémentation, donne-moi :
- la liste des fichiers modifiés ;
- les règles INDEX/NOINDEX effectivement appliquées ;
- les URL présentes dans le sitemap ;
- les tests ajoutés et leur résultat.
