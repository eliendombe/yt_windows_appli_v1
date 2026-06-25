# Architecture — Résumé

Ce document décrit l'architecture fonctionnelle et technique de l'application yt_windows_appli_v1.

## Vue d'ensemble
Composants principaux :
- Client Windows (UI) : application desktop en Python (Tkinter / PyQt / autre).
- Backend (optionnel) : API REST pour orchestration, authentification, et stockage.
- Worker / Job Processor : consommateur de tâches asynchrones (ex: traitement de téléchargement, transcodage).
- Persistance : base de données relationnelle (SQLite en local, PostgreSQL en production).
- Stockage de fichiers : disque local ou bucket (S3-compatible).
- Service YouTube : API YouTube Data / yt-dlp pour récupération de métadonnées / médias.

But : séparer la responsabilité UI (présentation) et traitement (backend + workers) pour faciliter scalabilité, test et déploiement.

## Diagramme de composants (mermaid)

```mermaid
flowchart LR
  A[Utilisateur] -->|Interaction GUI| B[Client Windows]
  B -->|Requête REST / IPC| C[Backend API]
  C -->|Enqueue job| D[Queue (Redis/RabbitMQ)]
  D -->|Consomme| E[Worker / Processor]
  E -->|Télécharge| F[YouTube / yt-dlp]
  E -->|Stocke fichiers| G[Stockage (local/S3)]
  E -->|Met à jour| H[Base de données (Postgres/SQLite)]
  C -->|Lit/écrit| H
  B <-->|WebSocket / Polling| C
```

## Diagramme de flux simplifié (scénario "Télécharger une vidéo")
1. L'utilisateur demande le téléchargement d'une vidéo dans l'UI.
2. L'UI envoie une requête POST /jobs au Backend avec l'URL YouTube et options.
3. Le Backend valide la requête, crée une entrée DB et met le job dans la queue.
4. Le Worker récupère le job, télécharge la vidéo via yt-dlp, stocke le fichier et met à jour la DB.
5. Le Backend notifie l'UI (WebSocket ou polling) de la fin/erreur du job.

## Modèle de données (extrait)
- jobs
  - id (uuid)
  - youtube_url
  - status (pending / running / success / failed)
  - output_path
  - created_at, started_at, finished_at
  - metadata json (titre, durée, format)
- users (si authentification)
- files (références aux fichiers stockés)

## Points d'attention / décisions techniques
- Utiliser des IDs UUID pour les jobs pour éviter collisions.
- Séparer queue et worker pour permettre scalabilité horizontale.
- Concevoir la persistance avec migrations (Alembic).
- Prévoir une couche d'abstraction pour le stockage afin d'alterner local / S3.
- Respecter les conditions d'utilisation de YouTube (usage et distribution des contenus).

## Scénarios d'intégration
- Mode "Standalone" : tout en local, DB SQLite, stockage local.
- Mode "Backend + Workers" : Backend (hébergé), queue Redis, workers sur serveurs séparés, DB Postgres, stockage S3.
