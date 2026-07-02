"""
============================================================
PARAMÈTRES GLOBAUX DU PROJET - Agent IA Assistant IFOAD-UJKZ
============================================================
Ce fichier centralise TOUS les paramètres du système.
Il charge les variables depuis le fichier .env automatiquement.
Pour modifier un paramètre, changez-le ici ou dans .env
============================================================
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ─── Chargement des variables d'environnement ───────────────────────────────
# On cherche le .env dans le dossier config/ (où ce fichier se trouve)
chemin_env = Path(__file__).parent / ".env"
load_dotenv(chemin_env)

# ─── CHEMINS DU PROJET ──────────────────────────────────────────────────────
# Racine du projet (deux niveaux au-dessus de config/)
RACINE_PROJET = Path(__file__).parent.parent

# Dossiers de données
DOSSIER_DONNEES_BRUTES    = RACINE_PROJET / os.getenv("CHEMIN_DONNEES_BRUTES", "data/brut")
DOSSIER_BASE_VECTORIELLE  = RACINE_PROJET / os.getenv("CHEMIN_BASE_VECTORIELLE", "data/vectorielle")

# Création automatique des dossiers s'ils n'existent pas encore
DOSSIER_DONNEES_BRUTES.mkdir(parents=True, exist_ok=True)
DOSSIER_BASE_VECTORIELLE.mkdir(parents=True, exist_ok=True)

# ─── API ET MODÈLES ─────────────────────────────────────────────────────────
# Clé API Groq (gratuite, sans carte bancaire)
CLE_API_GROQ = os.getenv("CLE_API_GROQ", "")

# Modèle LLM pour la génération des réponses
MODELE_LLM = os.getenv("MODELE_LLM", "openai/gpt-oss-120b")

# Modèle d'embeddings (tourne localement, sans API)
MODELE_EMBEDDINGS = os.getenv(
    "MODELE_EMBEDDINGS",
    "paraphrase-multilingual-mpnet-base-v2"
)

# Modèle de re-ranking cross-encoder (tourne localement)
MODELE_RERANKING = os.getenv(
    "MODELE_RERANKING",
    "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

# ─── BASE DE DONNÉES VECTORIELLE ────────────────────────────────────────────
# Nom de la collection ChromaDB
NOM_COLLECTION = os.getenv("NOM_COLLECTION_CHROMA", "ifoad_ujkz_collection")

# ─── SCRAPING ───────────────────────────────────────────────────────────────
# URL du site UJKZ
URL_UJKZ = os.getenv("URL_UJKZ", "https://www.ujkz.bf")

# Pages spécifiques à scraper sur UJKZ
PAGES_UJKZ_A_SCRAPER = [
    "/ifoad",                    # Page principale IFOAD
    "/ifoad/formations",         # Liste des formations
    "/ifoad/inscription",        # Modalités d'inscription
    "/ifoad/calendrier",         # Calendriers et examens
    "/actualites",               # Actualités de l'université
]

# ID de la page Facebook IFOAD/UJKZ (publique)
PAGE_FACEBOOK_IFOAD = "UJKZ.IFOAD"

# Délai entre les requêtes de scraping (politesse serveur)
DELAI_SCRAPING = float(os.getenv("DELAI_SCRAPING", "2"))

# ─── PARAMÈTRES DE VECTORISATION ────────────────────────────────────────────
# Taille d'un morceau de texte (chunk) en tokens approximatifs
TAILLE_CHUNK = int(os.getenv("TAILLE_CHUNK", "500"))

# Chevauchement entre chunks consécutifs (évite la perte de contexte)
CHEVAUCHEMENT_CHUNK = int(os.getenv("CHEVAUCHEMENT_CHUNK", "100"))

# ─── PARAMÈTRES RAG HYBRIDE ─────────────────────────────────────────────────
# Nombre de documents récupérés par la recherche dense (embeddings)
NOMBRE_DOCS_DENSE = int(os.getenv("NOMBRE_DOCS_DENSE", "10"))

# Nombre de documents récupérés par la recherche BM25 (mots-clés)
NOMBRE_DOCS_BM25 = int(os.getenv("NOMBRE_DOCS_BM25", "10"))

# Nombre de documents gardés après re-ranking (envoyés au LLM)
NOMBRE_DOCS_FINAL = int(os.getenv("NOMBRE_DOCS_FINAL", "5"))

# Seuil de confiance minimum (en dessous : l'agent dit "je ne sais pas")
SEUIL_CONFIANCE = 0.3

# ─── PARAMÈTRES DE L'INTERFACE STREAMLIT ────────────────────────────────────
TITRE_APPLICATION = os.getenv("TITRE_APPLICATION", "Assistant IFOAD-UJKZ 🎓")
SOUS_TITRE = os.getenv(
    "SOUS_TITRE",
    "Votre guide intelligent pour les formations à distance à l'Université Joseph Ki-Zerbo"
)

# ─── MESSAGES SYSTÈME ───────────────────────────────────────────────────────
# Prompt système qui définit le comportement de l'agent
PROMPT_SYSTEME = """Tu es un assistant IA expert et bienveillant de l'IFOAD 
(Institut de Formation Ouverte À Distance) de l'Université Joseph Ki-Zerbo (UJKZ) 
au Burkina Faso.

Ton rôle est d'aider les étudiants et candidats à obtenir des informations précises sur :
- Les formations et maquettes de cours disponibles
- Les modalités et procédures d'inscription
- Les calendriers d'examens et sessions
- Les actualités et événements de l'IFOAD/UJKZ

RÈGLES IMPORTANTES :
1. Réponds UNIQUEMENT en te basant sur le contexte fourni par les documents officiels
2. Si l'information n'est pas dans le contexte, dis clairement : 
   "Je ne dispose pas de cette information dans ma base de connaissances. 
   Je vous recommande de contacter directement l'IFOAD."
3. Cite toujours tes sources (quelle page ou document tu as utilisé)
4. Réponds en français
5. Sois précis, concis et professionnel
6. Ne jamais inventer des dates, des frais ou des procédures non confirmées
"""

# ─── VÉRIFICATION DE CONFIGURATION ──────────────────────────────────────────
def verifier_configuration():
    """
    Vérifie que toutes les variables obligatoires sont bien configurées.
    Affiche un avertissement si la clé API Groq est manquante.
    """
    problemes = []
    
    if not CLE_API_GROQ:
        problemes.append(
            "❌ CLE_API_GROQ manquante ! "
            "Obtenez-la gratuitement sur https://console.groq.com"
        )
    
    if not DOSSIER_DONNEES_BRUTES.exists():
        problemes.append(f"❌ Dossier données brutes introuvable : {DOSSIER_DONNEES_BRUTES}")
    
    if problemes:
        print("\n⚠️  PROBLÈMES DE CONFIGURATION DÉTECTÉS :")
        for pb in problemes:
            print(f"   {pb}")
        print("\nConsultez le fichier config/.env.exemple pour corriger ces erreurs.\n")
        return False
    
    print("✅ Configuration validée avec succès !")
    return True


# Affichage de la configuration au chargement (mode debug)
if __name__ == "__main__":
    verifier_configuration()
    print(f"\n📁 Racine projet       : {RACINE_PROJET}")
    print(f"📂 Données brutes      : {DOSSIER_DONNEES_BRUTES}")
    print(f"🗄️  Base vectorielle    : {DOSSIER_BASE_VECTORIELLE}")
    print(f"🤖 Modèle LLM          : {MODELE_LLM}")
    print(f"🔡 Modèle embeddings   : {MODELE_EMBEDDINGS}")
    print(f"📏 Taille chunk        : {TAILLE_CHUNK} tokens")
    print(f"🔍 Docs dense          : {NOMBRE_DOCS_DENSE}")
    print(f"🔑 Docs BM25           : {NOMBRE_DOCS_BM25}")
    print(f"🏆 Docs final (LLM)    : {NOMBRE_DOCS_FINAL}")
