"""
============================================================
MODULE D'INGESTION ET VECTORISATION - Cœur du système RAG
============================================================
Ce script transforme les documents bruts collectés en vecteurs
mathématiques stockés dans ChromaDB.

PIPELINE :
  Documents JSON (bruts)
       │
       ▼
  Découpage en chunks (morceaux de texte)
       │
       ▼
  Génération d'embeddings (sentence-transformers, local, gratuit)
       │
       ▼
  Stockage dans ChromaDB (base vectorielle légère)

USAGE :
    python src/ingestion/vectoriser.py

PRÉ-REQUIS :
    Avoir lancé le scraper : python src/collecte/scraper_ujkz.py
============================================================
"""

import os
import sys
import json
import re

from pathlib import Path
from typing import List, Dict, Tuple
from tqdm import tqdm
from loguru import logger

# ─── Ajout du chemin racine pour les imports ────────────────────────────────
RACINE = Path(__file__).parent.parent.parent
sys.path.insert(0, str(RACINE))

from config.parametres import (
    DOSSIER_DONNEES_BRUTES,
    DOSSIER_BASE_VECTORIELLE,
    MODELE_EMBEDDINGS,
    NOM_COLLECTION,
    TAILLE_CHUNK,
    CHEVAUCHEMENT_CHUNK,
)

# ─── Configuration des logs ─────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO"
)


# ════════════════════════════════════════════════════════════════════════════
# CLASSE 1 : DÉCOUPEUR DE TEXTE (Chunker)
# ════════════════════════════════════════════════════════════════════════════

class DecoupeurTexte:
    """
    Découpe les longs textes en petits morceaux (chunks) avec chevauchement.
    
    Pourquoi découper ?
    - Les modèles d'embeddings ont une limite de tokens
    - Des morceaux courts sont plus précis à retrouver
    - Le chevauchement évite de perdre le contexte aux frontières
    
    Exemple :
        Texte : "A B C D E F G H"
        Chunks (taille=4, chevauchement=2) : ["A B C D", "C D E F", "E F G H"]
    """

    def __init__(
        self,
        taille_chunk: int = TAILLE_CHUNK,
        chevauchement: int = CHEVAUCHEMENT_CHUNK
    ):
        """
        Args:
            taille_chunk: Taille approximative de chaque morceau (en mots)
            chevauchement: Nombre de mots partagés entre morceaux consécutifs
        """
        self.taille_chunk = taille_chunk
        self.chevauchement = chevauchement
        logger.debug(f"DecoupeurTexte : taille={taille_chunk}, chevauchement={chevauchement}")

    def decouper(self, texte: str, metadonnees: dict) -> List[Dict]:
        """
        Découpe un texte en chunks avec chevauchement, en respectant les paragraphes.
        
        Stratégie de découpage "intelligente" :
        1. D'abord, on découpe par paragraphes (séparés par lignes vides)
        2. Si un paragraphe est trop grand, on le redécoupe par phrases
        3. On assemble des phrases jusqu'à atteindre la taille cible
        
        Args:
            texte: Le texte complet à découper
            metadonnees: Infos sur la source (URL, titre, etc.)
            
        Returns:
            Liste de dictionnaires, chaque dict = un chunk avec ses métadonnées
        """
        if not texte or len(texte.strip()) < 50:
            logger.warning("Texte trop court pour être découpé, ignoré.")
            return []

        # ─── Étape 1 : Découpe par paragraphes ──────────────────────────
        # Les paragraphes sont séparés par une ou plusieurs lignes vides
        paragraphes = re.split(r'\n{2,}', texte.strip())
        paragraphes = [p.strip() for p in paragraphes if len(p.strip()) > 20]

        # ─── Étape 2 : Assemblage en chunks de taille cible ─────────────
        chunks = []
        chunk_actuel = []       # Mots du chunk en cours de construction
        nb_mots_actuel = 0      # Compteur de mots dans le chunk actuel

        for paragraphe in paragraphes:
            mots_paragraphe = paragraphe.split()
            nb_mots_para = len(mots_paragraphe)

            # Cas 1 : Le paragraphe seul dépasse la taille → le découper en phrases
            if nb_mots_para > self.taille_chunk:
                # On sauvegarde d'abord le chunk en cours
                if chunk_actuel:
                    chunks.append(" ".join(chunk_actuel))
                    chunk_actuel = []
                    nb_mots_actuel = 0

                # Découpage du grand paragraphe en phrases
                phrases = re.split(r'(?<=[.!?])\s+', paragraphe)
                for phrase in phrases:
                    mots_phrase = phrase.split()
                    if nb_mots_actuel + len(mots_phrase) <= self.taille_chunk:
                        chunk_actuel.extend(mots_phrase)
                        nb_mots_actuel += len(mots_phrase)
                    else:
                        if chunk_actuel:
                            chunks.append(" ".join(chunk_actuel))
                        # Chevauchement : on garde les N derniers mots
                        nb_mots_chevauchement = min(self.chevauchement, len(chunk_actuel))
                        chunk_actuel = chunk_actuel[-nb_mots_chevauchement:] + mots_phrase
                        nb_mots_actuel = len(chunk_actuel)

            # Cas 2 : Ajouter le paragraphe au chunk actuel
            elif nb_mots_actuel + nb_mots_para <= self.taille_chunk:
                chunk_actuel.extend(mots_paragraphe)
                nb_mots_actuel += nb_mots_para

            # Cas 3 : Le chunk est plein → le sauvegarder et commencer un nouveau
            else:
                if chunk_actuel:
                    chunks.append(" ".join(chunk_actuel))
                # Chevauchement : commence le nouveau chunk avec la fin du précédent
                nb_mots_chevauchement = min(self.chevauchement, len(chunk_actuel))
                chunk_actuel = chunk_actuel[-nb_mots_chevauchement:] + mots_paragraphe
                nb_mots_actuel = len(chunk_actuel)

        # Sauvegarde du dernier chunk
        if chunk_actuel:
            chunks.append(" ".join(chunk_actuel))

        # ─── Étape 3 : Construction des dictionnaires de chunks ──────────
        # Chaque chunk est enrichi avec ses métadonnées (pour la traçabilité)
        chunks_enrichis = []
        for idx, texte_chunk in enumerate(chunks):
            if len(texte_chunk.strip()) < 30:
                continue  # Ignore les chunks trop courts (bruit)

            chunk_dict = {
                # Le texte du morceau
                "texte": texte_chunk,
                # Métadonnées pour retrouver la source
                "source_url": metadonnees.get("url", ""),
                "source_titre": metadonnees.get("titre", ""),
                "source_type": metadonnees.get("type_source", ""),
                "date_collecte": metadonnees.get("date_collecte", ""),
                # Position du chunk dans le document original
                "numero_chunk": idx,
                "total_chunks": len(chunks),
                # Longueur pour debug
                "longueur_mots": len(texte_chunk.split()),
            }
            chunks_enrichis.append(chunk_dict)

        logger.debug(
            f"  → Document '{metadonnees.get('titre', 'Sans titre')[:40]}' "
            f"découpé en {len(chunks_enrichis)} chunks"
        )
        return chunks_enrichis


# ════════════════════════════════════════════════════════════════════════════
# CLASSE 2 : GESTIONNAIRE DE LA BASE VECTORIELLE
# ════════════════════════════════════════════════════════════════════════════

class GestionnaireVectoriel:
    """
    Gère la création et le remplissage de la base de données vectorielle ChromaDB.
    
    Rôle :
    - Charge le modèle d'embeddings (sentence-transformers, gratuit, local)
    - Transforme chaque chunk en vecteur mathématique
    - Stocke les vecteurs dans ChromaDB pour une recherche rapide
    
    Pourquoi ChromaDB ?
    - Gratuit et open-source
    - Fonctionne entièrement en local (pas de serveur externe)
    - Très facile à utiliser avec Python
    - Supporte la recherche par similarité cosinus
    """

    def __init__(self):
        """Initialise le modèle d'embeddings et la base ChromaDB."""

        logger.info("🔧 Initialisation du gestionnaire vectoriel...")

        # ─── Chargement du modèle d'embeddings ──────────────────────────
        # Ce modèle tourne ENTIÈREMENT sur votre machine (pas d'API payante !)
        # Il sera téléchargé automatiquement la première fois (~420 Mo)
        # Modèle choisi : supporte le français et les langues africaines
        logger.info(f" Chargement du modèle d'embeddings : {MODELE_EMBEDDINGS}")
        logger.info("   (Premier lancement : téléchargement ~420 Mo, soyez patient...)")

        from sentence_transformers import SentenceTransformer
        self.modele_embeddings = SentenceTransformer(MODELE_EMBEDDINGS)

        # Dimension des vecteurs produits par ce modèle
        self.dimension_vecteur = self.modele_embeddings.get_sentence_embedding_dimension()
        logger.info(f"    Modèle chargé ! Dimension des vecteurs : {self.dimension_vecteur}")

        # ─── Initialisation de ChromaDB ──────────────────────────────────
        # ChromaDB stocke les données dans un dossier local
        logger.info(f"  Connexion à ChromaDB : {DOSSIER_BASE_VECTORIELLE}")

        import chromadb
        self.client_chroma = chromadb.PersistentClient(
            path=str(DOSSIER_BASE_VECTORIELLE)
        )

        # Récupère ou crée la collection (table) pour l'IFOAD
        # on_duplicate : si la collection existe déjà, on la réutilise
        self.collection = self.client_chroma.get_or_create_collection(
            name=NOM_COLLECTION,
            # Métadonnées de la collection
            metadata={
                "description": "Documents IFOAD-UJKZ vectorisés",
                "modele_embeddings": MODELE_EMBEDDINGS,
                "hnsw:space": "cosine"  # Utilise la similarité cosinus pour la recherche
            }
        )

        logger.info(
            f"    Collection '{NOM_COLLECTION}' prête "
            f"({self.collection.count()} documents existants)"
        )

    def generer_embedding(self, texte: str) -> List[float]:
        """
        Transforme un texte en vecteur numérique (embedding).
        
        Un embedding est une liste de nombres (ex: [0.23, -0.15, 0.87, ...])
        qui capture le "sens" sémantique du texte.
        Deux textes avec un sens proche auront des vecteurs proches.
        
        Args:
            texte: Le texte à vectoriser
            
        Returns:
            Liste de floats représentant le vecteur du texte
        """
        vecteur = self.modele_embeddings.encode(texte, convert_to_numpy=True)
        return vecteur.tolist()

    def ajouter_chunks(self, chunks: List[Dict]) -> int:
        """
        Ajoute une liste de chunks dans ChromaDB avec leurs embeddings.
        
        Pour chaque chunk :
        1. Génère un identifiant unique
        2. Calcule l'embedding du texte
        3. Stocke (texte + embedding + métadonnées) dans ChromaDB
        
        Args:
            chunks: Liste de dictionnaires de chunks (produits par DecoupeurTexte)
            
        Returns:
            Nombre de chunks ajoutés avec succès
        """
        if not chunks:
            return 0

        nb_ajoutes = 0

        # Traitement par lots pour l'efficacité (batch processing)
        taille_lot = 50  # On traite 50 chunks à la fois
        lots = [chunks[i:i+taille_lot] for i in range(0, len(chunks), taille_lot)]

        for lot in lots:
            # Préparation des données pour ce lot
            identifiants = []  # ID unique de chaque chunk
            textes = []        # Texte brut (pour ChromaDB)
            metadonnees = []   # Métadonnées (source, titre, etc.)
            embeddings = []    # Vecteurs numériques

            for chunk in lot:
                # Génération d'un ID unique basé sur la source et la position
                identifiant = (
                    f"{chunk['source_type']}_{chunk['source_url'][:50]}"
                    f"_chunk{chunk['numero_chunk']}"
                )
                # Nettoyage de l'ID (ChromaDB n'accepte pas certains caractères)
                identifiant = re.sub(r'[^a-zA-Z0-9_\-]', '_', identifiant)[:100]

                # Vérification : ce chunk est-il déjà dans la base ?
                existants = self.collection.get(ids=[identifiant])
                if existants["ids"]:
                    logger.debug(f"     Chunk déjà existant, ignoré : {identifiant}")
                    continue

                # Génération de l'embedding pour ce chunk
                embedding = self.generer_embedding(chunk["texte"])

                identifiants.append(identifiant)
                textes.append(chunk["texte"])
                metadonnees.append({
                    "source_url": chunk.get("source_url", ""),
                    "source_titre": chunk.get("source_titre", "")[:200],  # Limite de taille
                    "source_type": chunk.get("source_type", ""),
                    "numero_chunk": chunk.get("numero_chunk", 0),
                    "total_chunks": chunk.get("total_chunks", 1),
                    "date_collecte": chunk.get("date_collecte", ""),
                })
                embeddings.append(embedding)

            # Ajout du lot dans ChromaDB (si des chunks nouveaux existent)
            if identifiants:
                self.collection.add(
                    ids=identifiants,
                    documents=textes,
                    metadatas=metadonnees,
                    embeddings=embeddings,
                )
                nb_ajoutes += len(identifiants)
                logger.debug(f"    {len(identifiants)} chunks ajoutés en base")

        return nb_ajoutes

    def obtenir_statistiques(self) -> dict:
        """
        Retourne des statistiques sur la base vectorielle.
        
        Returns:
            Dictionnaire avec le nombre de documents, les sources, etc.
        """
        nb_total = self.collection.count()

        # Récupération d'un échantillon pour analyser les sources
        if nb_total > 0:
            echantillon = self.collection.get(limit=min(nb_total, 1000))
            types_sources = {}
            for meta in echantillon.get("metadatas", []):
                type_src = meta.get("source_type", "inconnu")
                types_sources[type_src] = types_sources.get(type_src, 0) + 1
        else:
            types_sources = {}

        return {
            "nb_chunks_total": nb_total,
            "collection": NOM_COLLECTION,
            "dossier": str(DOSSIER_BASE_VECTORIELLE),
            "modele_embeddings": MODELE_EMBEDDINGS,
            "dimension_vecteur": self.dimension_vecteur,
            "types_sources": types_sources,
        }


# ════════════════════════════════════════════════════════════════════════════
# FONCTION PRINCIPALE : Orchestration de la vectorisation
# ════════════════════════════════════════════════════════════════════════════

def vectoriser_tous_les_documents() -> int:
    """
    Fonction principale qui orchestre tout le pipeline de vectorisation.
    
    Étapes :
    1. Lit tous les fichiers JSON dans data/brut/
    2. Découpe chaque document en chunks
    3. Génère les embeddings
    4. Stocke tout dans ChromaDB
    
    Returns:
        Nombre total de chunks vectorisés
    """
    logger.info("=" * 60)
    logger.info(" DÉMARRAGE DE LA VECTORISATION")
    logger.info("=" * 60)

    # ─── Vérification du dossier de données brutes ──────────────────────
    fichiers_json = list(DOSSIER_DONNEES_BRUTES.glob("*.json"))

    if not fichiers_json:
        logger.error(
            f" Aucun fichier JSON trouvé dans : {DOSSIER_DONNEES_BRUTES}\n"
            "   → Lancez d'abord le scraper : python src/collecte/scraper_ujkz.py"
        )
        return 0

    logger.info(f" {len(fichiers_json)} fichiers JSON à traiter")

    # ─── Initialisation des composants ──────────────────────────────────
    decoupeur = DecoupeurTexte(
        taille_chunk=TAILLE_CHUNK,
        chevauchement=CHEVAUCHEMENT_CHUNK
    )
    gestionnaire = GestionnaireVectoriel()

    # ─── Traitement de chaque document ──────────────────────────────────
    nb_chunks_total = 0
    nb_documents_traites = 0

    logger.info(f"\n Traitement des {len(fichiers_json)} documents...")

    # tqdm affiche une barre de progression dans le terminal
    for chemin_fichier in tqdm(fichiers_json, desc="Vectorisation", unit="doc"):

        # Lecture du document JSON
        try:
            with open(chemin_fichier, "r", encoding="utf-8") as f:
                document = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"  Fichier illisible ignoré : {chemin_fichier.name} ({e})")
            continue

        # Extraction du texte et des métadonnées
        texte = document.get("contenu", "")
        if not texte or len(texte) < 50:
            logger.debug(f"     Document trop court ignoré : {chemin_fichier.name}")
            continue

        # Découpage en chunks
        chunks = decoupeur.decouper(texte, document)
        if not chunks:
            continue

        # Vectorisation et stockage dans ChromaDB
        nb_ajoutes = gestionnaire.ajouter_chunks(chunks)
        nb_chunks_total += nb_ajoutes
        nb_documents_traites += 1

        logger.info(
            f"    '{document.get('titre', '?')[:45]}...' "
            f"→ {len(chunks)} chunks, {nb_ajoutes} nouveaux"
        )

    # ─── Rapport final ───────────────────────────────────────────────────
    stats = gestionnaire.obtenir_statistiques()

    logger.info("\n" + "=" * 60)
    logger.success(" VECTORISATION TERMINÉE !")
    logger.success(f"   → {nb_documents_traites} documents traités")
    logger.success(f"   → {nb_chunks_total} chunks vectorisés")
    logger.success(f"   → {stats['nb_chunks_total']} chunks TOTAL en base")
    logger.info(f"\n   Distribution par source :")
    for type_src, nb in stats["types_sources"].items():
        logger.info(f"      • {type_src:<20} : {nb} chunks")
    logger.info("=" * 60)

    # ─── CORRECTION : on retourne le TOTAL en base, pas seulement les nouveaux
    # Si nb_chunks_total == 0 mais que la base contient déjà des chunks,
    # c'est un succès (les données étaient déjà vectorisées)
    nb_total_en_base = stats['nb_chunks_total']
    return nb_total_en_base


# ════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Lancement : python src/ingestion/vectoriser.py
    """
    (RACINE / "logs").mkdir(exist_ok=True)

    nb_chunks = vectoriser_tous_les_documents()

    if nb_chunks > 0:
        print(f"\n✅ Succès ! {nb_chunks} chunks disponibles en base.")
        print("📌 Prochaine étape : python src/interface/application.py")
    else:
        print("\n❌ Échec de la vectorisation. Vérifiez les logs.")
        sys.exit(1)
