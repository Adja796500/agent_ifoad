"""
============================================================
PIPELINE RAG HYBRIDE AVANCÉ - Cerveau de l'Agent IA IFOAD
============================================================
Ce module implémente l'architecture RAG moderne (2026) qui
DÉPASSE le RAG classique grâce à 4 innovations majeures :

1. HyDE (Hypothetical Document Embeddings)
   → Au lieu de chercher directement avec la question de
     l'utilisateur, on génère d'abord un document hypothétique
     qui "ressemblerait" à la réponse, puis on cherche
     des documents similaires à CE document hypothétique.
     Résultat : une meilleure correspondance sémantique.

2. Recherche Hybride (Dense + BM25)
   → Dense : recherche par similarité sémantique (vecteurs)
   → BM25 : recherche par mots-clés exacts (comme Google)
   → On combine les deux pour ne rater aucun résultat

3. Fusion RRF (Reciprocal Rank Fusion)
   → Algorithme mathématique pour combiner les résultats
     des deux types de recherche de façon optimale

4. Re-ranking (Cross-Encoder)
   → Un modèle spécialisé réévalue chaque résultat récupéré
     pour sélectionner les VRAIMENT pertinents
     avant d'envoyer au LLM

USAGE :
    from src.agent.pipeline_rag import AgentRAGHybride
    agent = AgentRAGHybride()
    reponse = agent.repondre("Quelles sont les formations disponibles ?")
============================================================
"""

import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple
from loguru import logger

# ─── Ajout du chemin racine ─────────────────────────────────────────────────
RACINE = Path(__file__).parent.parent.parent
sys.path.insert(0, str(RACINE))

from config.parametres import (
    CLE_API_GROQ,
    MODELE_LLM,
    MODELE_EMBEDDINGS,
    MODELE_RERANKING,
    NOM_COLLECTION,
    DOSSIER_BASE_VECTORIELLE,
    NOMBRE_DOCS_DENSE,
    NOMBRE_DOCS_BM25,
    NOMBRE_DOCS_FINAL,
    SEUIL_CONFIANCE,
    PROMPT_SYSTEME,
)

# ─── Logs ───────────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout,
    format="<cyan>{time:HH:mm:ss}</cyan> | <level>{level: <8}</level> | {message}",
    level="INFO"
)


# ════════════════════════════════════════════════════════════════════════════
# CLASSE 1 : RÉCUPÉRATEUR HYBRIDE
# Combine Dense + BM25 + RRF pour la meilleure couverture possible
# ════════════════════════════════════════════════════════════════════════════

class RecuperateurHybride:
    """
    Implémente la recherche hybride : Dense (sémantique) + BM25 (mots-clés).
    
    DENSE (recherche sémantique) :
    - Transforme la question en vecteur
    - Cherche les documents dont le vecteur est le plus PROCHE
    - Avantage : comprend le SENS même si les mots sont différents
    - Exemple : "formation en ligne" trouve aussi "cours à distance"
    
    BM25 (recherche par mots-clés) :
    - Algorithme classique de moteur de recherche (comme TF-IDF amélioré)
    - Cherche les documents qui contiennent les mêmes MOTS EXACTS
    - Avantage : très précis pour les termes spécifiques, dates, codes
    - Exemple : "FCFA 2026" trouve exactement les documents avec ces mots
    
    RRF (Reciprocal Rank Fusion) :
    - Combine les classements des deux recherches de façon mathématique
    - Score RRF = Σ(1 / (k + rang_i)) pour chaque liste de résultats
    - k=60 est la valeur standard recommandée dans la littérature
    """

    def __init__(self):
        """Initialise le récupérateur avec les deux moteurs de recherche."""
        logger.info("🔍 Initialisation du Récupérateur Hybride...")

        # ─── Initialisation ChromaDB (recherche dense) ───────────────────
        import chromadb
        from sentence_transformers import SentenceTransformer

        self.client_chroma = chromadb.PersistentClient(
            path=str(DOSSIER_BASE_VECTORIELLE)
        )

        # Récupération de la collection existante
        try:
            self.collection = self.client_chroma.get_collection(NOM_COLLECTION)
            logger.info(f"    Collection ChromaDB : {self.collection.count()} chunks")
        except Exception as e:
            logger.error(
                f" Collection '{NOM_COLLECTION}' introuvable !\n"
                "   → Lancez d'abord : python src/ingestion/vectoriser.py"
            )
            raise RuntimeError("Base vectorielle non initialisée") from e

        # Modèle d'embeddings (même que lors de la vectorisation !)
        self.modele_embeddings = SentenceTransformer(MODELE_EMBEDDINGS)

        # ─── Chargement de tous les documents pour BM25 ──────────────────
        # BM25 nécessite d'avoir tous les textes en mémoire
        logger.info("   📚 Chargement des documents pour BM25...")
        self._charger_index_bm25()

        logger.info("    Récupérateur Hybride prêt !")

    def _charger_index_bm25(self):
        """
        Charge tous les textes depuis ChromaDB pour construire l'index BM25.
        BM25 a besoin de TOUS les documents pour calculer les fréquences de mots.
        """
        from rank_bm25 import BM25Okapi
        import nltk

        # Téléchargement silencieux des ressources NLTK (tokenisation)
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            nltk.download("punkt", quiet=True)
            nltk.download("punkt_tab", quiet=True)

        # Récupération de TOUS les chunks depuis ChromaDB
        nb_total = self.collection.count()
        if nb_total == 0:
            raise RuntimeError("La base vectorielle est vide !")

        # Récupération par lots (ChromaDB a une limite par requête)
        tous_les_textes = []
        toutes_les_metadonnees = []
        tous_les_ids = []
        taille_lot = 500

        for debut in range(0, nb_total, taille_lot):
            lot = self.collection.get(
                limit=taille_lot,
                offset=debut,
                include=["documents", "metadatas"]
            )
            tous_les_textes.extend(lot["documents"])
            toutes_les_metadonnees.extend(lot["metadatas"])
            tous_les_ids.extend(lot["ids"])

        # Stockage pour référence ultérieure
        self.tous_les_textes = tous_les_textes
        self.toutes_les_metadonnees = toutes_les_metadonnees
        self.tous_les_ids = tous_les_ids

        # Construction de l'index BM25
        # Tokenisation : découpage de chaque texte en liste de mots (en minuscule)
        corpus_tokenise = [
            texte.lower().split()
            for texte in tous_les_textes
        ]
        self.index_bm25 = BM25Okapi(corpus_tokenise)

        logger.debug(f"    Index BM25 construit : {len(tous_les_textes)} documents")

    def _recherche_dense(self, requete: str, nb_resultats: int) -> List[Dict]:
        """
        Recherche sémantique via les embeddings dans ChromaDB.
        
        Transforme la requête en vecteur et cherche les chunks
        dont le vecteur est le plus proche (similarité cosinus).
        
        Args:
            requete: La question ou le texte hypothétique (HyDE)
            nb_resultats: Combien de résultats retourner
            
        Returns:
            Liste de dicts avec texte, métadonnées et score de similarité
        """
        # Génération du vecteur pour la requête
        vecteur_requete = self.modele_embeddings.encode(requete).tolist()

        # Recherche des chunks les plus proches dans ChromaDB
        resultats = self.collection.query(
            query_embeddings=[vecteur_requete],
            n_results=min(nb_resultats, self.collection.count()),
            include=["documents", "metadatas", "distances"]
        )

        # Formatage des résultats
        documents_recuperes = []
        if resultats["documents"] and resultats["documents"][0]:
            for texte, meta, distance in zip(
                resultats["documents"][0],
                resultats["metadatas"][0],
                resultats["distances"][0]
            ):
                # Conversion distance → score de similarité (0 à 1)
                # ChromaDB retourne des distances (0=identique, 2=opposé)
                score_similarite = max(0, 1 - distance / 2)

                documents_recuperes.append({
                    "texte": texte,
                    "source": meta.get("source_url", ""),
                    "titre": meta.get("source_titre", ""),
                    "type_source": meta.get("source_type", ""),
                    "score_dense": score_similarite,
                    "methode": "dense"
                })

        return documents_recuperes

    def _recherche_bm25(self, requete: str, nb_resultats: int) -> List[Dict]:
        """
        Recherche par mots-clés via BM25 (algorithme classique de RI).
        
        BM25 (Best Match 25) est une évolution de TF-IDF qui tient compte
        de la longueur des documents pour éviter le biais vers les longs docs.
        
        Formule BM25 simplifiée :
        score(D,Q) = Σ IDF(qi) × f(qi,D)×(k1+1) / (f(qi,D) + k1×(1-b+b×|D|/avgdl))
        
        Args:
            requete: La question en texte brut
            nb_resultats: Nombre de résultats à retourner
            
        Returns:
            Liste de dicts avec texte, métadonnées et score BM25
        """
        # Tokenisation de la requête (mêmes termes qu'à l'indexation)
        mots_requete = requete.lower().split()

        # Calcul des scores BM25 pour tous les documents
        scores_bm25 = self.index_bm25.get_scores(mots_requete)

        # Tri des indices par score décroissant
        indices_tries = sorted(
            range(len(scores_bm25)),
            key=lambda i: scores_bm25[i],
            reverse=True
        )[:nb_resultats]

        # Formatage des résultats
        documents_recuperes = []
        score_max = max(scores_bm25) if max(scores_bm25) > 0 else 1  # Évite division par 0

        for rang, idx in enumerate(indices_tries):
            if scores_bm25[idx] <= 0:
                break  # Les scores nuls ne sont pas pertinents

            meta = self.toutes_les_metadonnees[idx]
            documents_recuperes.append({
                "texte": self.tous_les_textes[idx],
                "source": meta.get("source_url", ""),
                "titre": meta.get("source_titre", ""),
                "type_source": meta.get("source_type", ""),
                "score_bm25": scores_bm25[idx] / score_max,  # Normalisation 0-1
                "methode": "bm25"
            })

        return documents_recuperes

    def _fusionner_rrf(
        self,
        resultats_dense: List[Dict],
        resultats_bm25: List[Dict],
        k: int = 60
    ) -> List[Dict]:
        """
        Fusionne deux listes de résultats avec l'algorithme RRF.
        
        RRF (Reciprocal Rank Fusion) :
        - Attribue un score à chaque document basé sur son RANG dans chaque liste
        - score_rrf(doc) = 1/(k + rang_dense) + 1/(k + rang_bm25)
        - k=60 est empiriquement optimal (recommandé par Cormack et al. 2009)
        - Documents présents dans les deux listes → score boosté
        - Documents absents d'une liste → score partiel
        
        Avantage du RRF : robuste aux différences d'échelles entre les scores.
        
        Args:
            resultats_dense: Résultats de la recherche sémantique
            resultats_bm25: Résultats de la recherche BM25
            k: Constante de lissage (60 par défaut)
            
        Returns:
            Liste fusionnée et triée par score RRF décroissant
        """
        # Dictionnaire pour accumuler les scores RRF par document
        # Clé : texte du document (truncated), Valeur : dict avec score et infos
        scores_rrf = {}

        # ─── Contribution de la recherche dense ──────────────────────────
        for rang, doc in enumerate(resultats_dense):
            cle = doc["texte"][:100]  # Clé basée sur les 100 premiers chars
            if cle not in scores_rrf:
                scores_rrf[cle] = {"doc": doc, "score_rrf": 0.0}
            # Formule RRF : 1/(k + rang+1) (rang commence à 0 donc +1)
            scores_rrf[cle]["score_rrf"] += 1.0 / (k + rang + 1)

        # ─── Contribution de la recherche BM25 ───────────────────────────
        for rang, doc in enumerate(resultats_bm25):
            cle = doc["texte"][:100]
            if cle not in scores_rrf:
                scores_rrf[cle] = {"doc": doc, "score_rrf": 0.0}
            scores_rrf[cle]["score_rrf"] += 1.0 / (k + rang + 1)

        # ─── Tri par score RRF décroissant ────────────────────────────────
        docs_fusionnes = sorted(
            scores_rrf.values(),
            key=lambda x: x["score_rrf"],
            reverse=True
        )

        # Ajout du score RRF à chaque document et retour
        resultats_finaux = []
        for item in docs_fusionnes:
            doc = item["doc"].copy()
            doc["score_rrf"] = item["score_rrf"]
            resultats_finaux.append(doc)

        return resultats_finaux

    def rechercher(self, requete: str, nb_dense: int = None, nb_bm25: int = None) -> List[Dict]:
        """
        Lance la recherche hybride complète (Dense + BM25 + RRF).
        
        Args:
            requete: La question ou texte hypothétique
            nb_dense: Nombre de résultats dense (défaut: paramètre global)
            nb_bm25: Nombre de résultats BM25 (défaut: paramètre global)
            
        Returns:
            Liste fusionnée de documents triés par pertinence RRF
        """
        nb_dense = nb_dense or NOMBRE_DOCS_DENSE
        nb_bm25 = nb_bm25 or NOMBRE_DOCS_BM25

        logger.debug(f"🔍 Recherche hybride : '{requete[:60]}...'")

        # Recherche dense (sémantique)
        resultats_dense = self._recherche_dense(requete, nb_dense)
        logger.debug(f"   Dense : {len(resultats_dense)} résultats")

        # Recherche BM25 (mots-clés)
        resultats_bm25 = self._recherche_bm25(requete, nb_bm25)
        logger.debug(f"   BM25  : {len(resultats_bm25)} résultats")

        # Fusion RRF
        resultats_fusionnes = self._fusionner_rrf(resultats_dense, resultats_bm25)
        logger.debug(f"   RRF   : {len(resultats_fusionnes)} résultats fusionnés")

        return resultats_fusionnes


# ════════════════════════════════════════════════════════════════════════════
# CLASSE 2 : RE-CLASSEUR (Re-ranker)
# Améliore la précision finale avec un cross-encoder
# ════════════════════════════════════════════════════════════════════════════

class ReClasseur:
    """
    Re-classe les documents récupérés avec un modèle cross-encoder.
    
    POURQUOI ?
    Les embeddings bi-encodeurs (utilisés dans la recherche dense) sont rapides
    mais peu précis : ils calculent séparément le vecteur de la question et
    celui du document, puis comparent.
    
    Le cross-encoder est plus lent mais BEAUCOUP plus précis :
    il prend en entrée SIMULTANÉMENT la question ET le document,
    permettant une analyse fine de la pertinence.
    
    On l'utilise seulement sur les TOP-N résultats (pas sur toute la base)
    pour garder une vitesse acceptable.
    
    ANALOGIE : 
    - Bi-encodeur = regarder rapidement des résumés de livres
    - Cross-encoder = lire attentivement les premiers chapitres
    """

    def __init__(self):
        """Charge le modèle cross-encoder pour le re-ranking."""
        logger.info(f" Chargement du modèle de re-ranking : {MODELE_RERANKING}")
        logger.info("   (Premier lancement : téléchargement ~80 Mo...)")

        from sentence_transformers import CrossEncoder
        self.modele = CrossEncoder(MODELE_RERANKING)
        logger.info("    Modèle de re-ranking chargé !")

    def reclasser(self, question: str, documents: List[Dict], nb_final: int = None) -> List[Dict]:
        """
        Re-classe les documents selon leur pertinence par rapport à la question.
        
        Le cross-encoder prend des paires (question, document) et attribue
        un score de 0 à 1 indiquant la pertinence.
        
        Args:
            question: La question originale de l'utilisateur
            documents: Liste de documents à re-classer
            nb_final: Nombre de documents à garder après re-ranking
            
        Returns:
            Les nb_final meilleurs documents triés par pertinence décroissante
        """
        nb_final = nb_final or NOMBRE_DOCS_FINAL

        if not documents:
            return []

        logger.debug(f" Re-ranking de {len(documents)} documents...")

        # ─── Préparation des paires (question, texte) pour le cross-encoder
        paires_question_doc = [
            (question, doc["texte"])
            for doc in documents
        ]

        # ─── Calcul des scores de pertinence par le cross-encoder ────────
        # Le modèle analyse chaque paire et donne un score de pertinence
        scores_pertinence = self.modele.predict(paires_question_doc)

        # ─── Attribution des scores aux documents ────────────────────────
        for doc, score in zip(documents, scores_pertinence):
            # Normalisation du score en probabilité (0-1) via sigmoid
            doc["score_reranking"] = float(1 / (1 + 2.71828 ** (-score)))

        # ─── Tri par score de re-ranking décroissant ─────────────────────
        documents_reclasses = sorted(
            documents,
            key=lambda d: d["score_reranking"],
            reverse=True
        )

        # ─── Sélection des meilleurs résultats ───────────────────────────
        meilleurs = documents_reclasses[:nb_final]

        logger.debug(
            f"    Top scores re-ranking : "
            + ", ".join(f"{d['score_reranking']:.2f}" for d in meilleurs)
        )

        return meilleurs


# ════════════════════════════════════════════════════════════════════════════
# CLASSE 3 : AGENT RAG HYBRIDE COMPLET
# Orchestre tout le pipeline
# ════════════════════════════════════════════════════════════════════════════

class AgentRAGHybride:
    """
    Agent IA complet implémentant le pipeline RAG Hybride avancé (2026).
    
    Pipeline complet :
    Question utilisateur
        │
        ▼ (Étape 1)
    HyDE : génération d'un document hypothétique
        │
        ▼ (Étape 2)
    Recherche Hybride (Dense + BM25 + RRF)
        │
        ▼ (Étape 3)
    Re-ranking (Cross-encoder)
        │
        ▼ (Étape 4)
    Construction du prompt contextualisé
        │
        ▼ (Étape 5)
    Génération de la réponse (LLM Groq)
        │
        ▼
    Réponse finale avec sources + score de confiance
    """

    def __init__(self):
        """Initialise tous les composants du pipeline RAG."""
        logger.info(" Initialisation de l'Agent RAG Hybride IFOAD...")

        # ─── Vérification de la clé API ──────────────────────────────────
        if not CLE_API_GROQ:
            raise ValueError(
                " CLE_API_GROQ manquante !\n"
                "   → Créez config/.env et ajoutez votre clé Groq\n"
                "   → Obtenez-la gratuitement sur https://console.groq.com"
            )

        # ─── Initialisation du client Groq (LLM) ─────────────────────────
        from groq import Groq
        self.client_groq = Groq(api_key=CLE_API_GROQ)
        logger.info(f"    Client Groq initialisé (modèle : {MODELE_LLM})")

        # ─── Initialisation du récupérateur hybride ───────────────────────
        self.recuperateur = RecuperateurHybride()

        # ─── Initialisation du re-classeur ────────────────────────────────
        self.reclasseur = ReClasseur()

        # ─── Historique de la conversation (pour le contexte multi-tours) ─
        self.historique_conversation = []

        logger.info(" Agent RAG Hybride prêt à répondre !")

    # ────────────────────────────────────────────────────────────────────────
    # ÉTAPE 1 : HyDE - Génération du Document Hypothétique
    # ────────────────────────────────────────────────────────────────────────

    def _generer_document_hypothetique(self, question: str) -> str:
        """
        HyDE (Hypothetical Document Embeddings) : génère un faux document
        qui RESSEMBLERAIT à la réponse idéale, pour améliorer la recherche.
        
        POURQUOI HyDE ?
        Problème : "Quelles sont les dates des examens ?" 
        → Vecteur de la QUESTION ≠ vecteur des RÉPONSES dans la base
        
        Solution HyDE :
        → On génère un mini-document fictif : 
          "Les examens du premier semestre 2025-2026 se déroulent du 26 Janvier 
          au 7 Février 2026 sur le campus de l'UJKZ..."
        → Ce faux document a un vecteur BEAUCOUP plus proche des vrais documents
        → La recherche est bien meilleure !
        
        On utilise un appel LLM RAPIDE avec un contexte minimal.
        
        Args:
            question: La question de l'utilisateur
            
        Returns:
            Un court document hypothétique (2-4 phrases)
        """
        logger.debug(" HyDE : Génération du document hypothétique...")

        # Prompt minimal pour générer rapidement un document hypothétique
        prompt_hyde = (
            f"Tu es expert de l'IFOAD-UJKZ (Burkina Faso). "
            f"Génère un COURT extrait de document officiel (3-4 phrases) "
            f"qui répondrait à cette question : '{question}'\n"
            f"Réponds directement avec l'extrait, sans introduction ni explication."
        )

        try:
            reponse = self.client_groq.chat.completions.create(
                model=MODELE_LLM,
                messages=[{"role": "user", "content": prompt_hyde}],
                max_tokens=200,     # Court : juste assez pour un document hypothétique
                temperature=0.3,    # Peu de créativité : on veut quelque chose de factuel
            )
            doc_hypothetique = reponse.choices[0].message.content.strip()
            logger.debug(f"    Document hypothétique : '{doc_hypothetique[:80]}...'")
            return doc_hypothetique

        except Exception as e:
            # En cas d'erreur, on utilise la question originale (fallback)
            logger.warning(f"  HyDE échoué : {e} → Utilisation de la question directement")
            return question

    # ────────────────────────────────────────────────────────────────────────
    # ÉTAPE 4 : Construction du Prompt Contextualisé
    # ────────────────────────────────────────────────────────────────────────

    def _construire_prompt(self, question: str, documents: List[Dict]) -> str:
        """
        Construit le prompt final à envoyer au LLM avec le contexte récupéré.
        
        Le prompt inclut :
        1. Le contexte : les documents pertinents trouvés
        2. La question : ce que l'utilisateur demande
        3. Des instructions : comment répondre (avec sources, en français, etc.)
        
        Args:
            question: La question de l'utilisateur
            documents: Les documents pertinents récupérés par le RAG
            
        Returns:
            Le prompt complet formaté pour le LLM
        """
        # ─── Construction du bloc de contexte ────────────────────────────
        if not documents:
            contexte = "Aucun document pertinent trouvé dans la base de connaissances."
        else:
            blocs_contexte = []
            for idx, doc in enumerate(documents, start=1):
                source = doc.get("titre", doc.get("source", "Source inconnue"))
                score = doc.get("score_reranking", doc.get("score_rrf", 0))

                bloc = (
                    f"[Document {idx}] (Source: {source[:60]}, "
                    f"Pertinence: {score:.0%})\n"
                    f"{doc['texte']}"
                )
                blocs_contexte.append(bloc)

            contexte = "\n\n---\n\n".join(blocs_contexte)

        # ─── Prompt final structuré ───────────────────────────────────────
        prompt = f"""CONTEXTE (documents officiels IFOAD-UJKZ) :
{contexte}

---

QUESTION DE L'ÉTUDIANT : {question}

---

INSTRUCTIONS :
- Réponds UNIQUEMENT en te basant sur le CONTEXTE ci-dessus
- Si le contexte ne contient pas l'information, dis-le clairement
- Cite les sources sous forme [Document N]
- Réponds en français, de façon claire et structurée
- Pour les dates/frais/procédures : sois précis et exhaustif
- Si tu n'es pas sûr, recommande de contacter directement l'IFOAD"""

        return prompt

    # ────────────────────────────────────────────────────────────────────────
    # ÉTAPE 5 : Génération de la Réponse
    # ────────────────────────────────────────────────────────────────────────

    def _generer_reponse(self, prompt: str, question: str) -> str:
        """
        Envoie le prompt au LLM Groq et récupère la réponse.
        
        L'historique de conversation est maintenu pour les échanges multi-tours.
        
        Args:
            prompt: Le prompt contextualisé
            question: La question originale (pour l'historique)
            
        Returns:
            La réponse textuelle du LLM
        """
        # ─── Construction des messages pour l'API Groq ───────────────────
        messages = [
            # Message système : définit la personnalité et les règles de l'agent
            {"role": "system", "content": PROMPT_SYSTEME},
        ]

        # Ajout de l'historique récent (max 3 derniers échanges pour éviter
        # de dépasser la limite de tokens du contexte)
        for echange in self.historique_conversation[-3:]:
            messages.append({"role": "user", "content": echange["question"]})
            messages.append({"role": "assistant", "content": echange["reponse"]})

        # Ajout du prompt actuel
        messages.append({"role": "user", "content": prompt})

        # ─── Appel à l'API Groq ──────────────────────────────────────────
        try:
            completion = self.client_groq.chat.completions.create(
                model=MODELE_LLM,
                messages=messages,
                max_tokens=1500,    # Assez pour une réponse détaillée
                temperature=0.1,    # Très peu de créativité : on veut la précision
                top_p=0.9,          # Noyau de probabilité pour la diversité lexicale
            )
            reponse = completion.choices[0].message.content.strip()
            return reponse

        except Exception as e:
            logger.error(f" Erreur API Groq : {e}")
            return (
                f"Désolé, une erreur s'est produite lors de la génération "
                f"de la réponse : {str(e)}\n\n"
                f"Veuillez réessayer ou contacter directement l'IFOAD."
            )

    # ────────────────────────────────────────────────────────────────────────
    # DÉTECTION D'HALLUCINATION
    # ────────────────────────────────────────────────────────────────────────

    def _calculer_confiance(self, documents: List[Dict]) -> float:
        """
        Calcule un score de confiance basé sur la qualité des documents récupérés.
        
        Si les scores de re-ranking sont bas, c'est que les documents trouvés
        ne sont pas très pertinents → risque d'hallucination plus élevé.
        
        Args:
            documents: Les documents sélectionnés pour la réponse
            
        Returns:
            Score de confiance entre 0 (faible) et 1 (élevé)
        """
        if not documents:
            return 0.0

        # Moyenne des scores de re-ranking
        scores = [d.get("score_reranking", 0) for d in documents]
        confiance_moyenne = sum(scores) / len(scores)
        return confiance_moyenne

    # ────────────────────────────────────────────────────────────────────────
    # MÉTHODE PRINCIPALE : Répondre à une question
    # ────────────────────────────────────────────────────────────────────────

    def repondre(self, question: str) -> Dict:
        """
        Pipeline complet : de la question à la réponse finale.
        
        Exécute les 5 étapes du RAG Hybride dans l'ordre.
        
        Args:
            question: La question de l'utilisateur en français
            
        Returns:
            Dictionnaire contenant :
            - "reponse" : la réponse textuelle
            - "sources" : les documents utilisés
            - "confiance" : score de confiance (0-1)
            - "peut_repondre" : True si confiance > seuil
        """
        logger.info(f"❓ Question : '{question[:70]}...'")

        # ─── ÉTAPE 1 : HyDE ──────────────────────────────────────────────
        # Génération d'un document hypothétique pour améliorer la recherche
        doc_hypothetique = self._generer_document_hypothetique(question)

        # ─── ÉTAPE 2 : Recherche Hybride (Dense + BM25 + RRF) ────────────
        # On combine : question originale ET document hypothétique
        # pour maximiser la couverture
        requete_enrichie = f"{question} {doc_hypothetique}"
        documents_candidats = self.recuperateur.rechercher(requete_enrichie)

        # ─── ÉTAPE 3 : Re-ranking ─────────────────────────────────────────
        # On note plus précisément les candidats par rapport à la VRAIE question
        documents_finals = self.reclasseur.reclasser(
            question=question,
            documents=documents_candidats,
            nb_final=NOMBRE_DOCS_FINAL
        )

        # ─── Calcul du score de confiance ────────────────────────────────
        confiance = self._calculer_confiance(documents_finals)
        peut_repondre = confiance >= SEUIL_CONFIANCE

        logger.info(f"    Confiance : {confiance:.0%} ({' OK' if peut_repondre else ' Faible'})")

        # ─── ÉTAPE 4 : Construction du Prompt ─────────────────────────────
        if peut_repondre:
            prompt = self._construire_prompt(question, documents_finals)
        else:
            # Score de confiance trop bas : on prévient l'utilisateur
            logger.warning("  Confiance trop faible → réponse prudente")
            prompt = self._construire_prompt(question, documents_finals)
            prompt += (
                "\n\nIMPORTANT : Les documents trouvés semblent peu pertinents "
                "pour cette question. Précise clairement que tu ne trouves pas "
                "cette information dans ta base et recommande de contacter l'IFOAD."
            )

        # ─── ÉTAPE 5 : Génération de la Réponse ──────────────────────────
        reponse_texte = self._generer_reponse(prompt, question)

        # ─── Mise à jour de l'historique ─────────────────────────────────
        self.historique_conversation.append({
            "question": question,
            "reponse": reponse_texte
        })
        # Garde seulement les 5 derniers échanges (limite mémoire)
        if len(self.historique_conversation) > 5:
            self.historique_conversation = self.historique_conversation[-5:]

        # ─── Préparation des sources pour l'affichage ────────────────────
        sources_affichage = []
        for doc in documents_finals:
            sources_affichage.append({
                "titre": doc.get("titre", "Sans titre")[:80],
                "url": doc.get("source", ""),
                "type": doc.get("type_source", ""),
                "pertinence": f"{doc.get('score_reranking', 0):.0%}",
                "extrait": doc["texte"][:200] + "..."
            })

        logger.info(f"    Réponse générée ({len(reponse_texte)} caractères)")

        return {
            "reponse": reponse_texte,
            "sources": sources_affichage,
            "confiance": confiance,
            "peut_repondre": peut_repondre,
            "nb_documents_utilises": len(documents_finals),
        }

    def reinitialiser_historique(self):
        """Remet à zéro l'historique de conversation (nouvelle session)."""
        self.historique_conversation = []
        logger.info(" Historique de conversation réinitialisé")


# ════════════════════════════════════════════════════════════════════════════
# TEST RAPIDE DU PIPELINE
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Test rapide du pipeline RAG.
    Lancer avec : python src/agent/pipeline_rag.py
    """
    print("\n" + "=" * 60)
    print(" TEST DU PIPELINE RAG HYBRIDE")
    print("=" * 60)

    # Questions de test
    questions_test = [
        "Quelles sont les formations disponibles à l'IFOAD ?",
        "Quelles sont les dates des examens du premier semestre ?",
        "Comment s'inscrire à l'IFOAD ? Quels documents fournir ?",
        "Quels sont les frais de scolarité ?",
    ]

    try:
        agent = AgentRAGHybride()

        for question in questions_test:
            print(f"\n❓ QUESTION : {question}")
            print("-" * 50)

            resultat = agent.repondre(question)

            print(f" Confiance    : {resultat['confiance']:.0%}")
            print(f" Documents    : {resultat['nb_documents_utilises']}")
            print(f"\n RÉPONSE :\n{resultat['reponse'][:500]}...")
            print(f"\n SOURCES :")
            for src in resultat["sources"][:2]:
                print(f"   • {src['titre']} ({src['pertinence']})")

            print("\n" + "=" * 60)

    except Exception as e:
        print(f" Erreur : {e}")
        print("\n Assurez-vous d'avoir :")
        print("   1. Configuré config/.env avec votre clé Groq")
        print("   2. Lancé python src/collecte/scraper_ujkz.py")
        print("   3. Lancé python src/ingestion/vectoriser.py")
