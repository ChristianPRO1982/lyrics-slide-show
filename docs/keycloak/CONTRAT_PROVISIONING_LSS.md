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

Pour `app_id=lss`, `home` accepte uniquement les URLs HTTPS dont l'hôte est :

- `carthographie.fr`
- `lss.carthographie.fr`

L'URL signée peut contenir un chemin et une query string. Les fragments `#...`
sont refusés.

## Exemple Python

```python
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlencode

app_id = "lss"
return_url = "https://lss.carthographie.fr/"
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
8. En cas de succès, `home` affiche le lien de retour et redirige
   automatiquement après 5 secondes.

Si LSS ne peut pas générer le ticket signé parce que sa configuration est
incomplète, il ne doit pas rediriger vers l'accueil générique de `home`, car
cette URL ne déclenche pas le provisioning.

## Erreurs gérées

- `403` : ticket absent, invalide, expiré, rejoué ou URL de retour refusée.
- `403` : email Keycloak non vérifié.
- `400` : identifiant Keycloak absent ou invalide.
- `502` : receiver de provisioning indisponible ou erreur temporaire.
