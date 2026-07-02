# 🎓 Agent IA Assistant IFOAD-UJKZ
## Projet Data Science 2026 — Système RAG Hybride Avancé

---

## 📌 Description du Projet

Cet agent IA est un assistant intelligent capable de répondre précisément aux questions
sur les **maquettes de cours**, **calendriers d'examens** et **modalités d'inscription**
de l'IFOAD (Institut de Formation Ouverte À Distance) de l'Université Joseph Ki-Zerbo (UJKZ)
de Burkina Faso.

---

## 🚀 Architecture Technique — RAG Hybride Avancé (2026)

Notre système **dépasse le RAG classique** en implémentant un pipeline moderne :

```
Requête Utilisateur
        │
        ▼
┌─────────────────────┐
│  HyDE (génération   │  ← Génère un document hypothétique pour
│  doc hypothétique)  │    améliorer la recherche sémantique
└─────────────────────┘
        │
        ▼
┌──────────────────────────────────────────┐
│          RECHERCHE HYBRIDE               │
│  ┌─────────────────┐ ┌────────────────┐  │
│  │ Recherche Dense  │ │ Recherche BM25 │  │ ← Combine sémantique
│  │ (Embeddings)     │ │ (Mots-clés)   │  │   + mots-clés exacts
│  └─────────────────┘ └────────────────┘  │
│              │                │           │
│              └───── RRF ──────┘           │ ← Reciprocal Rank Fusion
└──────────────────────────────────────────┘
        │
        ▼
┌─────────────────────┐
│  RE-RANKING         │  ← Réordonne les résultats avec cross-encoder
│  (BGE Reranker)     │    pour une précision maximale
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│  LLM (Groq)         │  ← Génère la réponse finale avec le contexte
│  Llama 3.3 70B      │    enrichi + vérification anti-hallucination
└─────────────────────┘
        │
        ▼
   Réponse Finale + Sources citées
```

### Pourquoi ce pipeline est meilleur que le RAG classique ?

| Technique | RAG Classique | Notre Système |
|-----------|--------------|---------------|
| Recherche | Dense uniquement | **Hybride** (Dense + BM25) |
| Requête | Question brute | **HyDE** (doc hypothétique) |
| Résultats | Top-K direct | **Re-ranking** cross-encoder |
| Fusion | Non | **RRF** (Reciprocal Rank Fusion) |
| Hallucination | Non contrôlé | **Détection automatique** |

---

## 📦 Installation

### 1. Cloner le dépôt
```bash
git clone https://github.com/votre-groupe/agent-ifoad.git
cd agent-ifoad
```

### 2. Créer un environnement virtuel
```bash
python -m venv env_ifoad
# Windows
env_ifoad\Scripts\activate
# Linux/Mac
source env_ifoad/bin/activate
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Configurer les clés API
```bash
cp config/.env.exemple config/.env
# Remplir les valeurs dans config/.env
```

### 5. Collecter les données
```bash
python src/collecte/scraper_ujkz.py
```

### 6. Vectoriser les données
```bash
python src/ingestion/vectoriser.py
```

### 7. Lancer l'interface
```bash
streamlit run src/interface/application.py
```

---

## 🏗️ Structure du Projet

```
agent_ifoad/
├── config/
│   ├── .env.exemple          # Variables d'environnement (modèle)
│   └── parametres.py         # Paramètres globaux du système
├── data/
│   ├── brut/                 # Données brutes scrapées
│   └── vectorielle/          # Base ChromaDB (vecteurs)
├── src/
│   ├── collecte/
│   │   └── scraper_ujkz.py   # Scraper UJKZ + Facebook IFOAD
│   ├── ingestion/
│   │   └── vectoriser.py     # Chunking + Embeddings + Stockage
│   ├── agent/
│   │   └── pipeline_rag.py   # Pipeline RAG Hybride complet
│   └── interface/
│       └── application.py    # Interface Streamlit
├── tests/
│   └── evaluer_rag.py        # Évaluation anti-hallucination
├── docs/
│   └── rapport_technique.md  # Rapport du projet
├── requirements.txt
└── README.md
```

---

## 👥 Groupe

- Membre 1 : [Nom Prénom]
- Membre 2 : [Nom Prénom]
- Membre 3 : [Nom Prénom]

**Classe :** Master 1 IFOAD — UJKZ
**Enseignant :** Dr Delwende D. Arthur Sawadogo
**Date de présentation :** Lundi 13 Juillet 2026
