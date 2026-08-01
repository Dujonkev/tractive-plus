<p align="center">
  <img src="custom_components/tractive_plus/brand/logo.png" alt="Tractive Plus" width="340">
</p>

<h1 align="center">Tractive Plus — intégration Home Assistant</h1>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-custom-41BDF5.svg" alt="HACS custom"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.12%2B-blue.svg" alt="Home Assistant 2024.12+">
</p>

## Pourquoi cette intégration ?

L'intégration officielle **Tractive** de Home Assistant n'expose qu'une petite partie
des données renvoyées par l'API : position, batterie et quelques compteurs d'activité.

**Tractive Plus** vient la compléter : elle réutilise la session déjà ouverte par
l'intégration officielle (aucun identifiant supplémentaire à saisir) et publie une
trentaine d'entités additionnelles pour chaque tracker et chaque animal.

## Fonctionnalités

**Tracker (35 capteurs)** : altitude, précision de la position, source de position
(GPS / LTE / Wi-Fi), horodatage de la dernière position, vitesse, cap, état de la
batterie, raison de l'état courant, statut matériel, dernier rapport matériel, état
du clip, état de température, version du firmware, édition matérielle, mode économie
de batterie, sensibilité des clôtures virtuelles.

**Zones et abonnement** : zone d'économie d'énergie active, type de zone prioritaire,
date d'entrée et dernière détection dans la zone, statut / fin / formule / périodicité
de l'abonnement.

**Santé et activité de l'animal** : fréquence cardiaque au repos, fréquence
respiratoire au repos, aboiements, grattage, alertes santé, progression de l'objectif
d'activité, sommeil total, activité de l'heure en cours, dernière synchronisation,
objectifs quotidiens de distance et de points.

**Capteurs binaires (4)** : présence dans une zone d'économie d'énergie, assurance
active, abonnement reconductible, phase de séparation.

**Service `tractive_plus.probe`** : interroge n'importe quel endpoint de l'API
Tractive et renvoie la réponse JSON, pratique pour explorer de nouvelles données.

## Prérequis

- Home Assistant 2024.12 ou plus récent
- L'intégration officielle **Tractive** installée, configurée et chargée
- Un tracker Tractive avec un abonnement actif

## Installation

### Via HACS (dépôt personnalisé)

1. HACS → menu ⋮ → **Dépôts personnalisés**
2. URL : `https://github.com/Dujonkev/tractive-plus`, catégorie : **Integration**
3. Rechercher **Tractive Plus**, installer, puis redémarrer Home Assistant
4. **Paramètres → Appareils et services → Ajouter une intégration → Tractive Plus**

### Manuellement

Copier le dossier `custom_components/tractive_plus` dans le dossier
`custom_components` de votre configuration, redémarrer Home Assistant, puis ajouter
l'intégration.

## Configuration

Aucune. Le flux de configuration ne demande rien : l'intégration récupère la session
Tractive existante. Les données sont rafraîchies toutes les 2 minutes (les endpoints
lents, santé et abonnement, sont interrogés moins souvent).

## Exemple : service probe

```yaml
action: tractive_plus.probe
data:
  path: pet/<pet_id>/health/overview
  aps: false
```

La réponse JSON est renvoyée dans la variable de réponse de l'action et journalisée
au niveau `info`.

## Dépannage

- **L'intégration ne se charge pas** : vérifiez que l'intégration officielle Tractive
  est bien chargée, Tractive Plus en dépend.
- **Des capteurs sont indisponibles** : tous les champs ne sont pas renvoyés par tous
  les modèles de tracker ni tous les abonnements.
- **Journaux détaillés** :

```yaml
logger:
  default: warning
  logs:
    custom_components.tractive_plus: debug
```

## Contribuer

Les issues et les pull requests sont bienvenues. Les noms d'entités sont pour
l'instant en français côté code ; une bascule complète vers les `translation_key`
est prévue.

## Avertissement

Projet personnel, non affilié à Tractive GmbH ni à Home Assistant. « Tractive » est
une marque de son propriétaire respectif ; ce dépôt utilise l'API non documentée du
service, qui peut évoluer sans préavis.

Sous licence MIT.
