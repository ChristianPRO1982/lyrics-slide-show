# Contrat de provisioning Home pour LSS

Ce document décrit le contrat d'appel entre Lyrics Slide Show et la page de
provisionnement hébergée par `home`.

## URL d'entrée

```text
https://carthographie.fr/provision/start
```

## Paramètres de requête

| Paramètre | Obligatoire | Description |
| --- | --- | --- |
| `app_id` | oui | Identifiant applicatif. Pour LSS : `lss`. |
| `return_url` | oui | URL exacte vers laquelle `home` renvoie l'utilisateur après provisioning. |
| `ts` | oui | Timestamp Unix en secondes. |
| `nonce` | oui | Valeur aléatoire non rejouable. |
| `sig` | oui | Signature HMAC SHA-256 hexadécimale. |

## Signature

La signature est calculée sur les valeurs décodées avant encodage URL.

Chaîne canonique :

```text
app_id + "\n" + return_url + "\n" + ts + "\n" + nonce
```

Algorithme :

```text
sig = hex(HMAC-SHA256(secret_app, canonical_string))
```

Pour LSS, le secret partagé est stocké côté serveur dans :

```text
/opt/stacks/_shared/secrets/home-provisioning/redirect_lss_secret.txt
```

Ce secret ne doit jamais être envoyé au navigateur.

Si `HOME_PROVISION_SHARED_SECRET_FILE` n'est pas défini dans LSS, LSS tente
automatiquement de lire ce chemin contractuel.

## Fenêtre de validité

- `ts` est accepté pendant 120 secondes.
- `nonce` est mémorisé 5 minutes côté `home`.
- Un même couple `app_id` / `nonce` ne peut pas être réutilisé.

## URL de retour

Dans l’implémentation actuelle côté `LSS`, `HOME_PROVISION_RETURN_URL` doit être :

- une URL HTTPS absolue
- sans query string
- sans fragment
- avec le chemin exact `/provision/complete/`

Exemple production attendu :

```text
https://lss.carthographie.fr/provision/complete/
```

Le code Django ne valide pas aujourd’hui une liste d’hôtes contractuelle plus
fine ; il impose surtout ce format absolu HTTPS et ce chemin exact. En
production, l’URL attendue reste celle de `LSS`.

## Exemple Python

```python
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlencode

app_id = "lss"
return_url = "https://lss.carthographie.fr/provision/complete/"
ts = str(int(time.time()))
nonce = secrets.token_urlsafe(24)
secret = "SECRET_FROM_SERVER_FILE"

canonical = f"{app_id}\n{return_url}\n{ts}\n{nonce}"
sig = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()

url = "https://carthographie.fr/provision/start?" + urlencode({
    "app_id": app_id,
    "return_url": return_url,
    "ts": ts,
    "nonce": nonce,
    "sig": sig,
})
```

## Comportement attendu

1. LSS détecte que l'utilisateur Keycloak n'existe pas encore dans
   `users.users`.
2. LSS génère le ticket signé côté serveur.
3. LSS affiche une page intermédiaire avec un lien visible vers `home` et une
   redirection automatique.
4. Le navigateur arrive sur `/provision/start`.
5. `home` vérifie le ticket.
6. Si l'utilisateur n'a pas de session `home`, `home` le renvoie vers Keycloak.
7. `home` vérifie les claims Keycloak, puis demande au receiver
   `keycloak-user-sync` de provisionner l'utilisateur.
8. En cas de succès confirmé par le receiver, `home` redirige directement le
   navigateur vers l'URL exacte `return_url`.
9. Le retour final doit viser cette URL exacte, qui pointe vers
   `LSS /provision/complete/`.
10. Cet endpoint LSS exécute lui-même la dernière action applicative :
    relecture de `users.users`, ouverture de session locale, affichage d'une
    reprise, ou relance contrôlée d'un flux interne LSS si nécessaire.

## Contrat de retour final

Le retour final vers `LSS` n'est pas un callback OIDC.

Il doit permettre à `LSS` de relire `users.users` dans la même session
navigateur, grâce à l'état temporaire `lss_pending_provision` stocké après le
premier callback Keycloak valide.

`home` ne doit ni deviner, ni recalculer, ni compléter cette dernière étape.
La responsabilité de la dernière action fonctionnelle appartient entièrement a
`LSS`, via l'URL `return_url` qu'il a lui-même signée.

Règles :

- `home` ou `cARThographie` doit renvoyer le navigateur vers `return_url`
  exactement ;
- `LSS` doit signer une `return_url` qui déclenche une reprise applicative
  réelle, et non une simple page d'accueil ;
- il ne faut pas renvoyer vers `/`, `/auth/callback/` ou `/login/?start=1` ;
- pour rester cohérent avec le code actuel, il ne faut pas non plus ajouter de
  query string ni de fragment à `return_url` ;
- le succès final ne passe pas par une page HTML intermédiaire ;
- aucun identifiant utilisateur ou jeton spécifique à `LSS` n'est requis dans
  ce retour ;
- en cas d'échec de provisioning, `home` ne doit pas renvoyer vers
  `return_url` ;
- si la session navigateur `LSS` a été perdue, le flux nominal n'est plus
  récupérable sans nouvelle connexion Keycloak.

Si LSS ne peut pas générer le ticket signé parce que sa configuration est
incomplète, il ne doit pas rediriger vers l'accueil générique de `home`, car
cette URL ne déclenche pas le provisioning.

## Erreurs gérées

- `403` : ticket absent, invalide, expiré, rejoué ou URL de retour refusée.
- `403` : email Keycloak non vérifié.
- `400` : identifiant Keycloak absent ou invalide.
- `502` : receiver de provisioning indisponible ou erreur temporaire.
