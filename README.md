# local-tahoma-ha

Fork **généré** de l'intégration Home Assistant [Overkiz](https://github.com/home-assistant/core/tree/dev/homeassistant/components/overkiz), limité à l'**API locale** (TaHoma Switch en mode développeur) et conçu pour cohabiter avec l'intégration officielle `overkiz` (cloud).

| | Officielle | local-tahoma-ha |
|---|---|---|
| Domaine | `overkiz` | `local_tahoma` |
| Mode | cloud + local | local uniquement |
| Appareils | `Volet salon` | `Volet salon (Local)` |
| Entités | `cover.volet_salon` | `cover.volet_salon_local` |
| Services | `overkiz.*` | `local_tahoma.*` |
| Découverte | DHCP + zeroconf | zeroconf `_kizboxdev` (mode développeur) |

## Principe

Le code du composant n'est **pas édité à la main**. `sync.py` récupère l'amont, applique les modifications listées dans `transforms.py`, et écrit `custom_components/local_tahoma/`.

```
upstream/overkiz/               copie brute de HA (un diff git montre ce qui a changé chez HA)
transforms.py                   TOUTES les modifications (seul fichier à maintenir)
sync.py                         récupération + transformation
brand/                          icon.png / icon@2x.png, copiés dans le composant (logo affiché par HA)
translations_overrides/*.json   traductions manuelles (optionnel, copiées telles quelles)
custom_components/local_tahoma/ résultat, à installer dans HA / via HACS
```

## Mise à jour depuis Home Assistant

> **Règle : synchroniser toujours avec le tag de VOTRE version de Home Assistant, jamais avec `dev`.**
> `dev` est en avance sur les versions stables (autre version de `pyoverkiz`, autres classes) : le composant généré échoue alors au chargement (`Invalid handler specified`, `cannot import name …`).
> Version de HA : Paramètres → À propos → Core.

```bash
python3 sync.py --ref 2026.10.3    # remplacer par le tag de votre HA
git diff upstream/                 # ce qui a changé chez Home Assistant
```

- Chaque modification vérifie que son ancre existe exactement une fois. Si HA refactore le code visé, `sync.py` s'arrête avec le motif exact à corriger dans `transforms.py`.
- Les avertissements « référence de traduction inconnue » signalent une nouvelle référence `[%key:…%]` amont : l'ajouter à `COMMON_KEYS`.
- Changer `VERSION` à chaque publication, puis créer une release GitHub dont le tag est identique (voir « Publier une mise à jour » ci-dessous).

## Publier une mise à jour (HACS)

HACS détecte une nouvelle version grâce aux **releases GitHub** du dépôt (sans release, il compare seulement le hash du dernier commit, moins lisible).

1. `python3 sync.py --ref <tag de votre HA>`
2. Incrémenter `VERSION` (ex. `0.1.1`), relancer `python3 sync.py --ref <tag>` pour la reporter dans le manifest, puis commit + push.
3. Sur GitHub : Releases → *Draft a new release* → tag `v0.1.1` (identique à `VERSION`) → publier.
4. Dans HACS : l'intégration affiche « Mise à jour disponible » (parfois après quelques minutes ; ⋮ → *Mettre à jour les informations* pour forcer). Après mise à jour, **redémarrer Home Assistant**.

Version installée : HACS → l'intégration → *Version installée*, et Paramètres → Appareils et services → Overkiz (Local), qui lit `version` du manifest.

## Modifications appliquées (voir `transforms.py`)

1. `DOMAIN = "local_tahoma"` — isole appareils, entités, services, clés de traduction.
2. Config flow : l'étape initiale va directement à la saisie locale (hôte + token) ; titre de l'entrée suffixé `(Local)`.
3. Suppression des identifiants d'application OAuth2 (Rexel/cloud) et de leur dépendance.
4. Noms d'appareils, passerelle et `flow_title` suffixés ` (Local)`.
5. Manifest : nouveau domaine/nom, DHCP et `_kizbox._tcp` retirés (reste `_kizboxdev._tcp`).
6. `translations/en.json` généré depuis `strings.json` (références `[%key:…%]` résolues).

## Limites connues

- Le code cloud reste présent mais inatteignable (réduit au minimum de patchs pour faciliter le suivi).
- `pyoverkiz` est partagé avec l'intégration officielle : la version est celle de l'amont ; synchroniser avec le même `--ref` que votre HA évite les conflits.
- Non testé dans un Home Assistant réel à ce stade.
