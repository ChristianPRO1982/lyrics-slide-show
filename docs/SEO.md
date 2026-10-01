# SEO Lyrics Slide Show

Ce document décrit le socle SEO réellement appliqué dans `Lyrics Slide Show`.

L'objectif reste volontairement raisonnable : rendre les pages publiques compréhensibles par les moteurs de recherche sans transformer le projet en chantier SEO professionnel lourd.

## Principe général

La politique d'indexation est sécurisante :

- toutes les pages sont `noindex, follow` par défaut ;
- seules les pages publiques explicitement déclarées optent pour `index, follow` ;
- les pages métier, privées, techniques ou futures restent donc non indexables tant qu'elles ne sont pas volontairement exposées.

Cette règle évite qu'une nouvelle page d'administration, de modification ou de workflow interne devienne indexable par accident.

Le SEO ne doit pas modifier :

- les URL publiques existantes ;
- l'authentification Keycloak ;
- les permissions métier ;
- les recherches ;
- la navigation ;
- le comportement fonctionnel des pages.

## Implémentation

Le socle commun est centralisé dans `templates/base.html`.

Les variables de contexte SEO utilisées par le template sont :

- `seo_title` ;
- `seo_description` ;
- `seo_robots` ;
- `seo_canonical_url` ;
- `seo_og_title` ;
- `seo_og_description` ;
- `seo_og_url` ;
- `seo_og_type` ;
- `seo_site_name` ;
- `seo_json_ld`.

Les helpers sont centralisés dans `app_main/seo.py`.

Ils fournissent notamment :

- la base canonique ;
- la construction d'URL absolues ;
- le contexte SEO standard ;
- les descriptions SEO communes ;
- la description dynamique d'une page de chant ;
- le JSON-LD de la homepage ;
- la réponse `robots.txt`.

La base canonique par défaut est :

```text
https://lss.carthographie.fr
```

Elle peut être surchargée par la variable d'environnement :

```text
LSS_CANONICAL_BASE_URL
```

Les pages indexables doivent utiliser une canonical absolue en HTTPS.

Les pages `noindex` ne doivent normalement pas fournir de canonical, afin d'éviter des signaux contradictoires. La seule exception prévue est une variante de recherche du catalogue `/songs/?...`, qui reste `noindex, follow` mais pointe vers la canonical `/songs/`.

## Pages indexables

Les pages suivantes sont indexables :

| URL | Raison |
| --- | --- |
| `/` | présentation publique du service |
| `/songs/` sans paramètres | catalogue public des chants |
| `/songs/<song_id>/` pour les chants publics | page individuelle d'un chant |
| `/groups/` | liste publique des groupes |
| `/login/` | entrée de connexion au service |
| `/privacy-policy/` | politique de confidentialité |

Un chant est considéré public pour le SEO s'il est accessible anonymement avec les règles métier actuelles, donc avec `licensed=False`.

Le statut de validation du chant ne décide pas son indexation SEO. Un chant non licencié peut apparaître dans le sitemap même s'il n'est pas validé, car il est déjà accessible publiquement selon les règles actuelles du site.

## Pages non indexables

Toutes les autres pages restent `noindex, follow` par défaut.

Cela couvre notamment :

- `/animations/` et toutes les pages fonctionnelles dessous ;
- `/themes/` ;
- `/language/` ;
- `/account/` ;
- `/site-params/` ;
- `/login/diagnostic/` ;
- `/auth/callback/` ;
- `/provision/redirect/` ;
- `/provision/complete/` ;
- `/logout/` ;
- `/heavy/` et ses dépendances ;
- les pages de création, modification, administration ou modération ;
- `/groups/<group_id>/` ;
- `/songs/<song_id>/modify/` ;
- les pages de modification des genres, artistes, groupes musicaux et préfixes ;
- les endpoints techniques de messages, métadonnées, popups ou rendu de texte ;
- toute future page métier non explicitement déclarée publique.

Les pages `noindex` ne doivent pas être bloquées dans `robots.txt`, car les robots doivent pouvoir lire la balise `noindex`.

## Catalogue de chants

La page `/songs/` sans paramètre est indexable.

Les variantes avec paramètres GET ne sont pas indexables :

```text
/songs/?text=...
/songs/?genre_ids=...
/songs/?favorites_only=...
/songs/?validation=...
```

Ces variantes conservent leur fonctionnement utilisateur normal, mais émettent :

```text
noindex, follow
```

et une canonical vers :

```text
https://lss.carthographie.fr/songs/
```

Ce choix évite de créer un grand nombre de pages indexables pour les recherches, filtres et préférences.

Les liens affichés vers les chants restent de vrais liens HTML `<a href="...">`.

## Pages individuelles de chants

Les pages `/songs/<song_id>/` conservent l'URL numérique historique.

Il n'y a pas de slug dans ce chantier.

Pour une page de chant publique :

- le titre SEO est basé sur le titre complet du chant avec `Lyrics Slide Show` en suffixe ;
- le H1 existant reste le titre du chant ;
- la description SEO est courte ;
- la canonical pointe vers l'URL propre du chant ;
- la page est présente dans le sitemap.

La description SEO d'un chant est construite uniquement à partir de données fiables déjà disponibles :

- titre ;
- sous-titre ;
- description ;
- artistes ;
- groupes musicaux ;
- genres.

Elle ne doit pas être fabriquée à partir de grandes portions de paroles.

## Homepage

La homepage `/` est indexable.

Elle reçoit :

- un title explicite ;
- une meta description décrivant Lyrics Slide Show comme outil gratuit de gestion, recherche, organisation et projection de chants ;
- une canonical absolue ;
- un JSON-LD raisonnable de type `WebSite` et `SoftwareApplication`.

Le Wiki GitHub reste une documentation externe :

```text
https://github.com/ChristianPRO1982/lyrics-slide-show/wiki
```

Il peut être lié depuis les pages du site, mais il ne doit pas être inclus dans le sitemap LSS.

## Sitemap

Le sitemap est généré dynamiquement par Django à l'adresse :

```text
/sitemap.xml
```

La route est déclarée dans `lyrics_slide_show/urls.py` et la vue dans `app_main/views.py`.

Le sitemap contient uniquement les URL canoniques indexables :

- `/` ;
- `/privacy-policy/` ;
- `/login/` ;
- `/songs/` ;
- `/groups/` ;
- chaque `/songs/<song_id>/` dont le chant a `licensed=False`.

Le sitemap ne contient jamais :

- des paramètres de recherche ;
- des pages d'animations ;
- des pages de thèmes ;
- la page de langue ;
- la page de compte ;
- des pages d'administration ou modification ;
- des callbacks ;
- des pages techniques ;
- des pages privées ;
- le Wiki GitHub.

Le sitemap ne fournit pas `lastmod`, car le modèle `Song` ne possède pas de date fiable de dernière modification.

Il ne fournit pas non plus `priority` ni `changefreq`.

## robots.txt

Le fichier `robots.txt` est généré par Django à l'adresse :

```text
/robots.txt
```

Il autorise l'exploration normale et déclare le sitemap :

```text
User-agent: *
Allow: /
Sitemap: https://lss.carthographie.fr/sitemap.xml
```

Il ne bloque pas les pages `noindex`.

## Open Graph

`base.html` expose un Open Graph minimal quand les données SEO sont présentes :

- `og:title` ;
- `og:description` ;
- `og:url` ;
- `og:type` ;
- `og:site_name`.

Il n'y a pas d'image Open Graph dédiée à ce stade.

## Internationalisation

Le site possède plusieurs langues d'interface, mais il n'existe pas d'URL stable distincte par langue pour chaque page.

Il ne faut donc pas ajouter de `hreflang` dans l'état actuel.

Il ne faut pas créer de nouvelles URL uniquement pour le SEO.

Les textes SEO ajoutés côté Python doivent rester compatibles avec Django i18n.

## Maintenance

Pour rendre une nouvelle page indexable :

1. vérifier qu'elle est réellement publique et utile pour les moteurs ;
2. ajouter un contexte SEO explicite avec `seo_context(..., index=True, ...)` ;
3. fournir une canonical absolue ;
4. vérifier que la page ne dépend pas d'un état de session privé ;
5. l'ajouter au sitemap seulement si elle est canonicale et publique ;
6. ajouter ou adapter un test SEO.

Pour créer une page métier, de gestion ou technique :

- ne rien ajouter au SEO ;
- laisser le fallback `noindex, follow` ;
- ne pas l'ajouter au sitemap.

## Tests

Les tests SEO ciblés sont dans `app_main.tests.SeoIntegrationTests`.

Ils vérifient notamment :

- la homepage indexable ;
- `/songs/` indexable sans paramètres ;
- une variante `/songs/?...` en `noindex` ;
- une page de chant publique indexable et canonicalisée ;
- `/groups/`, `/login/` et `/privacy-policy/` indexables ;
- des pages métier en `noindex` ;
- le contenu du sitemap ;
- l'absence de chants licenciés dans le sitemap ;
- l'absence d'URL privées ou techniques dans le sitemap ;
- `robots.txt`.

Commande utile :

```bash
uv run python manage.py test app_main.tests.SeoIntegrationTests --noinput -v 2
```

Pour le contrôle global du projet :

```bash
uv run python manage.py test app_main app_song app_group app_animation --noinput -v 2
```
