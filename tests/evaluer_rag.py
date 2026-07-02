"""
============================================================
MODULE D'ÉVALUATION DU SYSTÈME RAG - Nouveauté 2026
============================================================
Ce script évalue la QUALITÉ et la ROBUSTESSE du système RAG
selon les critères imposés par le projet :

1. PERTINENCE DES DOCUMENTS RÉCUPÉRÉS
   → L'agent cherche-t-il dans les bons endroits ?
   → Métriques : Precision@K, Recall@K, MRR

2. TAUX D'HALLUCINATION
   → L'agent sait-il dire "je ne sais pas" ?
   → Test avec des questions hors-domaine
   → Test avec des questions sur des faits inventés

3. QUALITÉ DES RÉPONSES
   → Les réponses sont-elles fidèles aux sources ?
   → Métriques : ROUGE-L, Faithfulness Score

USAGE :
    python tests/evaluer_rag.py

SORTIE :
    Un rapport d'évaluation complet en JSON et console
============================================================
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

from loguru import logger

# ─── Ajout du chemin racine ─────────────────────────────────────────────────
RACINE = Path(__file__).parent.parent
sys.path.insert(0, str(RACINE))

# ─── Logs ───────────────────────────────────────────────────────────────────
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO"
)


# ════════════════════════════════════════════════════════════════════════════
# JEUX DE TEST
# ════════════════════════════════════════════════════════════════════════════

# ─── Questions avec réponses de référence (ground truth) ────────────────────
# Ces questions devraient être bien répondues par l'agent
QUESTIONS_DANS_DOMAINE = [
    {
        "question": "Quelles formations sont disponibles à l'IFOAD-UJKZ ?",
        "mots_cles_attendus": ["Master", "IFOAD", "Licence", "formation"],
        "doit_repondre": True,
        "categorie": "formations"
    },
    {
        "question": "Quelles sont les dates des examens du premier semestre 2025-2026 ?",
        "mots_cles_attendus": ["Janvier", "Février", "2026", "examen"],
        "doit_repondre": True,
        "categorie": "calendrier"
    },
    {
        "question": "Quels documents faut-il fournir pour s'inscrire à l'IFOAD ?",
        "mots_cles_attendus": ["CNIB", "diplôme", "photo", "lettre", "CV"],
        "doit_repondre": True,
        "categorie": "inscription"
    },
    {
        "question": "Quels sont les frais d'inscription à l'IFOAD ?",
        "mots_cles_attendus": ["FCFA", "frais", "paiement"],
        "doit_repondre": True,
        "categorie": "frais"
    },
    {
        "question": "Comment contacter le secrétariat de l'IFOAD ?",
        "mots_cles_attendus": ["email", "téléphone", "contact", "ifoad@"],
        "doit_repondre": True,
        "categorie": "contact"
    },
    {
        "question": "Quand ont lieu les regroupements présentiel ?",
        "mots_cles_attendus": ["Novembre", "Janvier", "Avril", "regroupement"],
        "doit_repondre": True,
        "categorie": "calendrier"
    },
    {
        "question": "Quels sont les débouchés professionnels du Master IFOAD ?",
        "mots_cles_attendus": ["ingénieur", "développeur", "data", "consultant"],
        "doit_repondre": True,
        "categorie": "formations"
    },
]

# ─── Questions HORS DOMAINE ──────────────────────────────────────────────────
# L'agent NE DOIT PAS inventer des réponses pour ces questions
# Il doit dire "je ne sais pas" ou recommander de contacter l'IFOAD
QUESTIONS_HORS_DOMAINE = [
    {
        "question": "Quel est le cours de l'euro par rapport au FCFA aujourd'hui ?",
        "doit_repondre": False,
        "categorie": "hors_domaine_finance"
    },
    {
        "question": "Qui a gagné la Coupe d'Afrique des Nations 2026 ?",
        "doit_repondre": False,
        "categorie": "hors_domaine_sport"
    },
    {
        "question": "Comment préparer du tô (plat burkinabè) ?",
        "doit_repondre": False,
        "categorie": "hors_domaine_cuisine"
    },
]

# ─── Questions avec FAITS INVENTÉS (test d'hallucination) ───────────────────
# L'agent NE DOIT PAS confirmer ces informations fausses
QUESTIONS_PIEGES = [
    {
        "question": "Est-ce que l'IFOAD propose une formation en médecine ?",
        "reponse_incorrecte_contient": ["médecine", "oui", "propose"],
        "doit_repondre": False,
        "categorie": "information_fausse"
    },
    {
        "question": "Les frais d'inscription à l'IFOAD sont de 10 000 FCFA, c'est bien ça ?",
        "reponse_incorrecte_contient": ["oui", "correct", "exact", "10 000"],
        "doit_repondre": True,  # Doit répondre, mais corriger l'information
        "categorie": "information_fausse"
    },
    {
        "question": "L'IFOAD est basé à Bobo-Dioulasso, n'est-ce pas ?",
        "reponse_incorrecte_contient": ["oui", "correct", "Bobo"],
        "doit_repondre": True,  # Doit corriger
        "categorie": "information_fausse"
    },
]


# ════════════════════════════════════════════════════════════════════════════
# MÉTRIQUES D'ÉVALUATION
# ════════════════════════════════════════════════════════════════════════════

class CalculateurMetriques:
    """
    Calcule les métriques de qualité du système RAG.
    
    Métriques implémentées :
    
    1. Precision@K : Parmi les K documents récupérés, quelle fraction
       contient les mots-clés attendus ?
       → Precision@5 = 3/5 si 3 docs sur 5 sont pertinents
    
    2. MRR (Mean Reciprocal Rank) : À quelle position apparaît
       le PREMIER document pertinent ?
       → MRR = 1/rang du premier doc pertinent
       → Si le 1er doc est pertinent : MRR = 1/1 = 1.0
       → Si le 3ème doc est le premier pertinent : MRR = 1/3 = 0.33
    
    3. Faithfulness (Fidélité) : La réponse est-elle fidèle aux sources ?
       → Mesurée par chevauchement de mots-clés
    
    4. Taux d'hallucination : Quand l'agent ne sait pas, le dit-il ?
    """

    @staticmethod
    def precision_at_k(
        documents_recuperes: List[Dict],
        mots_cles_attendus: List[str],
        k: int = 5
    ) -> float:
        """
        Calcule la précision parmi les K premiers documents.
        
        Un document est considéré "pertinent" s'il contient
        au moins un des mots-clés attendus.
        
        Args:
            documents_recuperes: Documents retournés par le RAG
            mots_cles_attendus: Mots-clés qui devraient apparaître
            k: Nombre de documents à considérer
            
        Returns:
            Score entre 0 et 1
        """
        if not documents_recuperes or not mots_cles_attendus:
            return 0.0

        # Limite à K documents
        top_k = documents_recuperes[:k]

        nb_pertinents = 0
        for doc in top_k:
            texte_doc = doc.get("texte", "").lower()
            # Document pertinent si au moins un mot-clé est présent
            if any(mot.lower() in texte_doc for mot in mots_cles_attendus):
                nb_pertinents += 1

        return nb_pertinents / len(top_k)

    @staticmethod
    def mrr(
        documents_recuperes: List[Dict],
        mots_cles_attendus: List[str]
    ) -> float:
        """
        Calcule le Mean Reciprocal Rank (MRR).
        
        Mesure à quelle position le premier document pertinent apparaît.
        Plus le MRR est proche de 1, mieux c'est (premier résultat pertinent).
        
        Args:
            documents_recuperes: Documents retournés par le RAG
            mots_cles_attendus: Mots-clés attendus
            
        Returns:
            Score MRR entre 0 et 1
        """
        for rang, doc in enumerate(documents_recuperes, start=1):
            texte_doc = doc.get("texte", "").lower()
            if any(mot.lower() in texte_doc for mot in mots_cles_attendus):
                return 1.0 / rang
        return 0.0

    @staticmethod
    def score_faithfulness(reponse: str, documents: List[Dict]) -> float:
        """
        Évalue si la réponse est fidèle aux documents sources.
        
        Méthode simplifiée : compte combien de mots importants de la réponse
        apparaissent aussi dans les documents sources.
        
        Args:
            reponse: La réponse générée par l'agent
            documents: Les documents utilisés comme contexte
            
        Returns:
            Score de fidélité entre 0 et 1
        """
        if not reponse or not documents:
            return 0.0

        # Mots "importants" : longs de plus de 4 lettres (filtre les mots vides)
        mots_reponse = set(
            mot.lower().strip(".,;:!?\"'()")
            for mot in reponse.split()
            if len(mot) > 4
        )

        # Texte combiné de tous les documents sources
        texte_sources = " ".join(
            doc.get("texte", "").lower()
            for doc in documents
        )

        if not mots_reponse:
            return 0.0

        # Proportion de mots de la réponse présents dans les sources
        nb_mots_dans_sources = sum(
            1 for mot in mots_reponse
            if mot in texte_sources
        )

        return nb_mots_dans_sources / len(mots_reponse)

    @staticmethod
    def detecter_refus(reponse: str) -> bool:
        """
        Détecte si l'agent a bien reconnu qu'il ne pouvait pas répondre.
        
        Cherche des formulations typiques d'un refus poli / aveu d'ignorance.
        
        Args:
            reponse: La réponse générée
            
        Returns:
            True si l'agent a bien exprimé son incertitude
        """
        marqueurs_refus = [
            "je ne dispose pas",
            "je n'ai pas cette information",
            "n'est pas dans ma base",
            "je vous recommande de contacter",
            "je ne sais pas",
            "information non disponible",
            "je ne trouve pas",
            "contactez directement",
            "n'est pas dans les documents",
            "cette information n'est pas",
        ]

        reponse_minuscule = reponse.lower()
        return any(marqueur in reponse_minuscule for marqueur in marqueurs_refus)


# ════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE D'ÉVALUATION
# ════════════════════════════════════════════════════════════════════════════

class EvaluateurRAG:
    """
    Évalue le système RAG Hybride sur un ensemble de questions de test.
    
    Génère un rapport complet avec :
    - Métriques de récupération (Precision@K, MRR)
    - Score de fidélité des réponses
    - Taux de détection d'hallucination
    - Statistiques globales
    """

    def __init__(self):
        """Initialise l'évaluateur et charge l'agent RAG."""
        logger.info(" Initialisation de l'Évaluateur RAG...")

        # Chargement de l'agent
        from src.agent.pipeline_rag import AgentRAGHybride
        self.agent = AgentRAGHybride()

        # Calculateur de métriques
        self.metriques = CalculateurMetriques()

        # Résultats de l'évaluation
        self.resultats = []

        logger.info(" Évaluateur prêt !")

    def evaluer_question(self, config_question: dict) -> dict:
        """
        Évalue le système sur une seule question et calcule les métriques.
        
        Args:
            config_question: Dict avec question, mots_cles_attendus, doit_repondre
            
        Returns:
            Dict avec la question, la réponse et toutes les métriques calculées
        """
        question = config_question["question"]
        categorie = config_question.get("categorie", "inconnu")
        doit_repondre = config_question.get("doit_repondre", True)
        mots_cles = config_question.get("mots_cles_attendus", [])

        logger.info(f"    Évaluation : '{question[:60]}...'")

        # ─── Chronométrage ───────────────────────────────────────────────
        temps_debut = time.time()
        resultat_agent = self.agent.repondre(question)
        temps_reponse = time.time() - temps_debut

        reponse = resultat_agent["reponse"]
        sources = resultat_agent["sources"]
        confiance = resultat_agent["confiance"]

        # ─── Reconstruction des docs pour les métriques ──────────────────
        # Les sources sont des résumés, on les utilise tels quels
        docs_pour_metriques = [
            {"texte": src.get("extrait", "")}
            for src in sources
        ]

        # ─── Calcul des métriques ─────────────────────────────────────────
        precision_5 = self.metriques.precision_at_k(docs_pour_metriques, mots_cles, k=5) if mots_cles else None
        mrr_score = self.metriques.mrr(docs_pour_metriques, mots_cles) if mots_cles else None
        faithfulness = self.metriques.score_faithfulness(reponse, docs_pour_metriques)
        a_refuse = self.metriques.detecter_refus(reponse)

        # ─── Jugement : comportement correct ? ───────────────────────────
        if doit_repondre:
            # L'agent DOIT répondre → correct s'il n'a PAS refusé
            comportement_correct = not a_refuse and confiance > 0.2
        else:
            # L'agent NE DOIT PAS répondre → correct s'il a refusé
            comportement_correct = a_refuse or confiance < 0.3

        # ─── Détection d'affirmation de pièges ───────────────────────────
        reponses_incorrectes = config_question.get("reponse_incorrecte_contient", [])
        a_tombe_dans_piege = False
        if reponses_incorrectes:
            reponse_min = reponse.lower()
            a_tombe_dans_piege = all(
                mot.lower() in reponse_min
                for mot in reponses_incorrectes[:2]  # Vérifie les 2 premiers
            )

        resultat = {
            "question": question,
            "categorie": categorie,
            "reponse": reponse[:300] + "..." if len(reponse) > 300 else reponse,
            "doit_repondre": doit_repondre,
            "a_refuse": a_refuse,
            "comportement_correct": comportement_correct,
            "a_tombe_dans_piege": a_tombe_dans_piege,
            "confiance_agent": confiance,
            "precision_at_5": precision_5,
            "mrr": mrr_score,
            "faithfulness": faithfulness,
            "temps_reponse_sec": round(temps_reponse, 2),
            "nb_sources": len(sources),
        }

        statut = "correct" if comportement_correct else "incorrect"
        logger.info(
            f"      {statut} | Confiance: {confiance:.0%} | "
            f"Fidélité: {faithfulness:.0%} | "
            f"Temps: {temps_reponse:.1f}s"
        )

        return resultat

    def executer_evaluation_complete(self) -> dict:
        """
        Exécute l'évaluation complète sur tous les jeux de test.
        
        Returns:
            Rapport d'évaluation complet avec toutes les métriques
        """
        logger.info("=" * 60)
        logger.info(" DÉBUT DE L'ÉVALUATION DU SYSTÈME RAG")
        logger.info("=" * 60)

        # ─── Évaluation des questions dans le domaine ────────────────────
        logger.info("\n TEST 1 : Questions dans le domaine IFOAD")
        resultats_dans_domaine = []
        for question_config in QUESTIONS_DANS_DOMAINE:
            res = self.evaluer_question(question_config)
            resultats_dans_domaine.append(res)
            self.resultats.append(res)

        # ─── Évaluation des questions hors domaine ───────────────────────
        logger.info("\n TEST 2 : Questions HORS domaine (test refus)")
        resultats_hors_domaine = []
        for question_config in QUESTIONS_HORS_DOMAINE:
            res = self.evaluer_question(question_config)
            resultats_hors_domaine.append(res)
            self.resultats.append(res)

        # ─── Évaluation des questions pièges ─────────────────────────────
        logger.info("\n TEST 3 : Questions pièges (test anti-hallucination)")
        resultats_pieges = []
        for question_config in QUESTIONS_PIEGES:
            res = self.evaluer_question(question_config)
            resultats_pieges.append(res)
            self.resultats.append(res)

        # ─── Calcul des statistiques globales ────────────────────────────
        rapport = self._calculer_statistiques_globales(
            resultats_dans_domaine,
            resultats_hors_domaine,
            resultats_pieges
        )

        # ─── Sauvegarde du rapport ────────────────────────────────────────
        self._sauvegarder_rapport(rapport)

        # ─── Affichage du résumé ──────────────────────────────────────────
        self._afficher_resume(rapport)

        return rapport

    def _calculer_statistiques_globales(
        self,
        dans_domaine: list,
        hors_domaine: list,
        pieges: list
    ) -> dict:
        """
        Calcule les statistiques globales à partir de tous les résultats.
        
        Args:
            dans_domaine: Résultats des questions dans le domaine
            hors_domaine: Résultats des questions hors domaine
            pieges: Résultats des questions pièges
            
        Returns:
            Dictionnaire de rapport complet
        """

        def moyenne(liste, cle):
            """Calcule la moyenne d'une métrique sur une liste de résultats."""
            valeurs = [r[cle] for r in liste if r.get(cle) is not None]
            return sum(valeurs) / len(valeurs) if valeurs else 0.0

        def taux_correct(liste):
            """Calcule le taux de comportements corrects."""
            if not liste:
                return 0.0
            return sum(1 for r in liste if r["comportement_correct"]) / len(liste)

        # ─── Métriques par catégorie ──────────────────────────────────────
        stats_dans_domaine = {
            "nb_questions": len(dans_domaine),
            "taux_comportement_correct": taux_correct(dans_domaine),
            "precision_at_5_moyenne": moyenne(dans_domaine, "precision_at_5"),
            "mrr_moyen": moyenne(dans_domaine, "mrr"),
            "faithfulness_moyen": moyenne(dans_domaine, "faithfulness"),
            "confiance_moyenne": moyenne(dans_domaine, "confiance_agent"),
            "temps_reponse_moyen": moyenne(dans_domaine, "temps_reponse_sec"),
        }

        stats_hors_domaine = {
            "nb_questions": len(hors_domaine),
            "taux_refus_correct": taux_correct(hors_domaine),
            "confiance_moyenne": moyenne(hors_domaine, "confiance_agent"),
        }

        stats_pieges = {
            "nb_questions": len(pieges),
            "taux_piege_evite": taux_correct(pieges),
            "taux_hallucination": 1 - taux_correct(pieges),
            "nb_pieges_tombes": sum(1 for r in pieges if r.get("a_tombe_dans_piege")),
        }

        # ─── Score global (note sur 100) ──────────────────────────────────
        # Pondération :
        # - Qualité réponses domaine : 40%
        # - Refus hors domaine : 30%
        # - Résistance aux pièges : 30%
        score_global = (
            stats_dans_domaine["taux_comportement_correct"] * 40 +
            stats_hors_domaine["taux_refus_correct"] * 30 +
            stats_pieges["taux_piege_evite"] * 30
        )

        return {
            "date_evaluation": datetime.now().isoformat(),
            "score_global_sur_100": round(score_global, 1),
            "dans_domaine": stats_dans_domaine,
            "hors_domaine": stats_hors_domaine,
            "pieges": stats_pieges,
            "resultats_detailles": self.resultats,
        }

    def _sauvegarder_rapport(self, rapport: dict):
        """Sauvegarde le rapport d'évaluation en JSON."""
        dossier_rapports = RACINE / "docs" / "rapports_evaluation"
        dossier_rapports.mkdir(parents=True, exist_ok=True)

        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        chemin_rapport = dossier_rapports / f"evaluation_rag_{horodatage}.json"

        with open(chemin_rapport, "w", encoding="utf-8") as f:
            json.dump(rapport, f, ensure_ascii=False, indent=2)

        logger.info(f" Rapport sauvegardé : {chemin_rapport}")

    def _afficher_resume(self, rapport: dict):
        """Affiche un résumé coloré et lisible du rapport d'évaluation."""
        print("\n" + "=" * 65)
        print(" RAPPORT D'ÉVALUATION DU SYSTÈME RAG HYBRIDE IFOAD")
        print("=" * 65)

        score = rapport["score_global_sur_100"]
        mention = (
            "Excellent" if score >= 80 else
            "Bien" if score >= 60 else
            "Passable" if score >= 40 else
            "À améliorer"
        )

        print(f"\n SCORE GLOBAL : {score}/100 → {mention}")

        # Questions dans le domaine
        dd = rapport["dans_domaine"]
        print(f"\n QUESTIONS DANS LE DOMAINE ({dd['nb_questions']} questions) :")
        print(f"   Comportement correct  : {dd['taux_comportement_correct']:.0%}")
        print(f"   Precision@5           : {dd['precision_at_5_moyenne']:.0%}")
        print(f"   MRR                   : {dd['mrr_moyen']:.3f}")
        print(f"   Fidélité sources      : {dd['faithfulness_moyen']:.0%}")
        print(f"   Confiance moyenne     : {dd['confiance_moyenne']:.0%}")
        print(f"   Temps moyen/réponse   : {dd['temps_reponse_moyen']:.1f}s")

        # Questions hors domaine
        hd = rapport["hors_domaine"]
        print(f"\n QUESTIONS HORS DOMAINE ({hd['nb_questions']} questions) :")
        print(f"   Taux de refus correct : {hd['taux_refus_correct']:.0%}")
        print(f"   Confiance moyenne     : {hd['confiance_moyenne']:.0%}")

        # Résistance aux pièges
        p = rapport["pieges"]
        print(f"\n RÉSISTANCE AUX PIÈGES ({p['nb_questions']} questions) :")
        print(f"   Taux d'évitement      : {p['taux_piege_evite']:.0%}")
        print(f"   Taux d'hallucination  : {p['taux_hallucination']:.0%}")
        print(f"   Pièges tombés         : {p['nb_pieges_tombes']}/{p['nb_questions']}")

        print("\n" + "=" * 65)
        print(f" Évaluation : {rapport['date_evaluation'][:19]}")
        print("=" * 65)


# ════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Lancement : python tests/evaluer_rag.py
    """
    print("\n Démarrage de l'évaluation du système RAG IFOAD-UJKZ...")
    print(" Cela peut prendre plusieurs minutes selon la vitesse de l'API Groq.\n")

    try:
        evaluateur = EvaluateurRAG()
        rapport = evaluateur.executer_evaluation_complete()
        print(f"\n Évaluation terminée ! Score : {rapport['score_global_sur_100']}/100")

    except Exception as e:
        logger.error(f" Erreur lors de l'évaluation : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
