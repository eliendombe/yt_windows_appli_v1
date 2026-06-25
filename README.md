# yt_windows_appli_v1 — Guide d'installation (FR)

Ce guide explique comment installer, configurer et exécuter l'application en local (Windows) et contient des exemples d'intégration avec un backend et la persistance.

---

## Table des matières
- Pré-requis
- Installation (développement)
- Configuration (fichiers et variables d'environnement)
- Exécution locale
- Packaging Windows (optionnel)
- Intégration Backend — Exemples de code
- Exemple de persistance — SQLAlchemy
- Checklist de production
- Dépannage

---

## Pré-requis
- Windows 10/11
- Python 3.10 ou 3.11 (installation via python.org)
- Git
- (Optionnel) Virtualenv / venv
- (Si backend séparé) Redis (pour queue) / PostgreSQL / S3-compatible storage

---

## Installation en développement

1. Cloner le dépôt
   git clone https://github.com/eliendombe/yt_windows_appli_v1.git
   cd yt_windows_appli_v1

2. Créer un environnement virtuel
   python -m venv .venv
   .venv\Scripts\activate

3. Mettre à jour pip et installer dépendances
   python -m pip install --upgrade pip
   pip install -r requirements.txt

   Remarque : si requirements.txt n'existe pas encore, ajouter les paquets nécessaires (exemples) :
   pip install requests sqlalchemy alembic python-dotenv yt-dlp

4. Configurer les variables d'environnement
   Copier `.env.example` en `.env` et éditer :
   - BACKEND_URL=http://localhost:8000
   - DATABASE_URL=sqlite:///./data/db.sqlite3
   - REDIS_URL=redis://localhost:6379/0
   - STORAGE_PATH=./storage
   - SECRET_KEY=change_moi

   Exemple minimal `.env` :
   BACKEND_URL=http://localhost:8000
   DATABASE_URL=sqlite:///./data/db.sqlite3
   STORAGE_PATH=./storage

5. Créer répertoire de stockage
   mkdir storage
   mkdir data

6. Initialiser la base de données (si vous utilisez Alembic / SQLAlchemy)
   - Configurer alembic.ini et la variable DATABASE_URL.
   - Lancer les migrations :
     alembic upgrade head

---

## Exécution locale (mode standalone)
Par défaut, l'application peut s'exécuter en mode tout-en-un (UI + logique) :
1. Activez l'environnement virtuel
2. Lancer l'app :
   python src/main.py
ou
   python -m yt_app

Ajustez la commande selon l'entrypoint réel de votre projet.

---

## Packaging pour Windows (optionnel)
Pour créer un exécutable Windows avec PyInstaller :
1. Installer PyInstaller
   pip install pyinstaller

2. Construire
   pyinstaller --noconfirm --onefile --name yt_windows_appli_v1 src/main.py

3. Signer l'exécutable (recommandé en production)
   - Utiliser signtool (Microsoft) et certificat code-signing.

---

## Intégration Backend — Exemples

A) Exemple d'appel POST pour créer un job (client -> backend)
```python name=examples/api_client.py
import os
import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def create_download_job(youtube_url: str, quality: str = "best"):
    payload = {
        "youtube_url": youtube_url,
        "options": {"quality": quality}
    }
    resp = requests.post(f"{BACKEND_URL}/jobs", json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    job = create_download_job("https://www.youtube.com/watch?v=EXAMPLE")
    print("Job créé :", job)
```

B) Polling / WebSocket pour suivre l'état
- Si le backend expose WebSocket : connectez-vous pour recevoir les mises à jour.
- Sinon, poller GET /jobs/{id}.

---

## Persistance — Exemple SQLAlchemy

A) Modèle simple
```python name=examples/models.py
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid
import datetime

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    youtube_url = Column(String, nullable=False)
    status = Column(String, default="pending")
    output_path = Column(String, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
```

B) Session et CRUD minimal
```python name=examples/db_session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from examples.models import Base, Job
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/db.sqlite3")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def create_job(youtube_url: str):
    db = SessionLocal()
    job = Job(youtube_url=youtube_url)
    db.add(job)
    db.commit()
    db.refresh(job)
    db.close()
    return job
```

C) Exemple d'utilisation
```python name=examples/usage_db.py
from examples.db_session import init_db, create_job

if __name__ == "__main__":
    init_db()
    job = create_job("https://www.youtube.com/watch?v=EXAMPLE")
    print("Job créé:", job.id)
```

---

## Checklist de production

Avant déploiement en production, vérifier :
- [ ] Revue de sécurité (gestion des entrées URLs, validation).
- [ ] Sécurisation des secrets (utiliser vault / secrets manager, pas .env dans le repo).
- [ ] Chiffrement des données sensibles au repos si nécessaire.
- [ ] Migrations de base testées et automatisées (Alembic + CI).
- [ ] Logging structuré (niveau, rotation, centralisation).
- [ ] Monitoring & alerting (uptime, erreurs, taux d'échecs des jobs).
- [ ] Tests automatisés (unitaires + intégration).
- [ ] CI/CD pour builds et déploiements.
- [ ] Tests de charge et scalabilité (worker concurrency, queue).
- [ ] Backup & restauration DB testés.
- [ ] Distribution signée (code-signing pour exécutable Windows).
- [ ] Conformité légale (YouTube TOS, licences des bibliothèques).
- [ ] Politique de mise à jour / auto-update ou release process.
- [ ] Plan de rollback.

---

## Dépannage rapide
- Erreur de connexion DB : vérifier DATABASE_URL et que le service est accessible.
- Permission écriture storage : vérifier droits Windows et antivirus.
- yt-dlp ne fonctionne pas : tester en CLI yt-dlp <url> ; vérifier dépendances (ffmpeg si transcodage).
- Timeout demande HTTP : augmenter le timeout côté client ou optimiser backend.

---

## Points légaux et conformité
- Attention aux droits d'auteur : l'utilisation et redistribution des contenus YouTube peuvent être restreintes.
- Respecter les limites d'utilisation de l'API YouTube.

---

Si vous souhaitez que je crée ces fichiers directement dans le dépôt, indiquez la branche cible (par ex. `main`) et je ferai le commit contenant les trois fichiers. Je peux aussi générer un fichier .env.example et requirements.txt minimal si utile.
