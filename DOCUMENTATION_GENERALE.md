# Documentation générale

Ce document présente la documentation générale du projet "yt_windows_appli_v1". Il décrit l'objectif du projet, la structure des documents fournis et les conventions utilisées.

## Objectif du projet
yt_windows_appli_v1 est une application Windows écrite en Python destinée à interagir avec des contenus YouTube (ex : lecture, téléchargement, métadonnées) et/ou à orchestrer des actions vers un backend pour persistance et traitement asynchrone.

## Contenu de la documentation
- ARCHITECTURE.md — Résumé de l'architecture, composants, diagrammes de flux et scénarios d'interaction.
- README.md — Guide d'installation détaillé, configuration, exécution locale, packaging Windows et exemples d'intégration backend / persistance.
- DOCUMENTATION_GENERALE.md — Ce fichier (vue d'ensemble).
- (A ajouter) CONTRIBUTING.md, CHANGELOG.md, SECURITY.md selon besoins.

## Conventions
- Langue : français.
- Code d'exemple : Python 3.10+.
- Configuration : variables d'environnement (fichier .env conseillé).
- Persistence : SQLAlchemy (exemples pour SQLite et PostgreSQL).
- API : REST JSON (exemples avec requests) — si vous utilisez un backend local, indiquez son URL via la variable BACKEND_URL.

## Bonnes pratiques pour la documentation
- Mettre à jour ARCHITECTURE.md à chaque changement significatif d'architecture.
- Inclure diagrammes (mermaid / images) pour clarifier les flux asynchrones.
- Documenter les endpoints backend et les schémas de données (ex : OpenAPI si disponible).
