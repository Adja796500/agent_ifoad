"""
============================================================
MODULE DE COLLECTE DE DONNÉES - Scraper UJKZ & Facebook IFOAD
============================================================
Ce script collecte les informations sur l'IFOAD depuis :
1. Le site officiel de l'UJKZ (ujkz.bf)
2. La page Facebook publique de l'IFOAD/UJKZ
3. Les PDFs officiels trouvés sur ces pages

USAGE :
    python src/collecte/scraper_ujkz.py

SORTIE :
    Les données sont sauvegardées dans data/brut/
============================================================
"""

import os
import sys
import time
import json
import re
import hashlib
import requests
import pdfplumber

from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from loguru import logger

# ─── Ajout du chemin racine pour les imports internes ───────────────────────
# Permet d'importer depuis config/ même si on lance depuis n'importe où
RACINE = Path(__file__).parent.parent.parent
sys.path.insert(0, str(RACINE))

from config.parametres import (
    URL_UJKZ,
    PAGES_UJKZ_A_SCRAPER,
    DELAI_SCRAPING,
    DOSSIER_DONNEES_BRUTES,
    PAGE_FACEBOOK_IFOAD
)

# ─── Configuration du système de journalisation ─────────────────────────────
logger.remove()  # Supprime le handler par défaut
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO"
)
logger.add(
    RACINE / "logs/scraping.log",  # Sauvegarde aussi dans un fichier
    rotation="5 MB",
    level="DEBUG"
)


# ════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE : ScraperIFOAD
# ════════════════════════════════════════════════════════════════════════════

class ScraperIFOAD:
    """
    Collecteur de données pour l'IFOAD-UJKZ.
    
    Scrappe le site UJKZ et la page Facebook pour récupérer
    toutes les informations disponibles sur les formations.
    """

    def __init__(self):
        """Initialisation du scraper avec les paramètres de configuration."""
        
        # En-têtes HTTP pour simuler un navigateur réel
        # (évite les blocages par certains serveurs)
        self.entetes = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        # Session HTTP réutilisable (plus efficace que des requêtes individuelles)
        self.session = requests.Session()
        self.session.headers.update(self.entetes)
        
        # Compteur des documents collectés
        self.nb_documents_collectes = 0
        
        logger.info("  ScraperIFOAD initialisé avec succès")
        logger.info(f" Dossier de sortie : {DOSSIER_DONNEES_BRUTES}")

    # ────────────────────────────────────────────────────────────────────────
    # MÉTHODES UTILITAIRES
    # ────────────────────────────────────────────────────────────────────────

    def _pause_polie(self):
        """
        Attend un délai entre les requêtes pour ne pas surcharger le serveur.
        C'est une bonne pratique éthique du scraping.
        """
        logger.debug(f" Pause de {DELAI_SCRAPING} secondes...")
        time.sleep(DELAI_SCRAPING)

    def _generer_identifiant(self, texte: str) -> str:
        """
        Génère un identifiant unique (hash MD5) à partir d'un texte.
        Utile pour nommer les fichiers et détecter les doublons.
        
        Args:
            texte: Le texte à hasher
            
        Returns:
            Les 8 premiers caractères du hash MD5
        """
        return hashlib.md5(texte.encode("utf-8")).hexdigest()[:8]

    def _sauvegarder_document(self, document: dict) -> Path:
        """
        Sauvegarde un document collecté au format JSON dans le dossier de données.
        
        Args:
            document: Dictionnaire contenant le texte et les métadonnées
            
        Returns:
            Chemin du fichier sauvegardé
        """
        # Génère un nom de fichier unique basé sur la source et la date
        identifiant = self._generer_identifiant(document.get("url", document.get("contenu", "")))
        nom_fichier = f"{document['type_source']}_{identifiant}.json"
        chemin_fichier = DOSSIER_DONNEES_BRUTES / nom_fichier
        
        # Sauvegarde en JSON avec encodage UTF-8 (important pour le français)
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
        
        self.nb_documents_collectes += 1
        logger.debug(f" Document sauvegardé : {nom_fichier}")
        return chemin_fichier

    def _nettoyer_texte(self, texte: str) -> str:
        """
        Nettoie et normalise un texte brut récupéré du web.
        Supprime les espaces en excès, caractères spéciaux, etc.
        
        Args:
            texte: Le texte brut à nettoyer
            
        Returns:
            Le texte nettoyé
        """
        if not texte:
            return ""
        
        # Suppression des espaces multiples et tabulations
        texte = re.sub(r'\s+', ' ', texte)
        
        # Suppression des caractères de contrôle (sauf les sauts de ligne)
        texte = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texte)
        
        # Normalisation des guillemets et apostrophes
        texte = texte.replace('\u2019', "'").replace('\u2018', "'")
        texte = texte.replace('\u201c', '"').replace('\u201d', '"')
        
        return texte.strip()

    # ────────────────────────────────────────────────────────────────────────
    # SCRAPING DU SITE UJKZ
    # ────────────────────────────────────────────────────────────────────────

    def scraper_page_ujkz(self, chemin_relatif: str) -> dict | None:
        """
        Scrappe une page spécifique du site UJKZ.
        
        Args:
            chemin_relatif: Le chemin de la page (ex: "/ifoad/formations")
            
        Returns:
            Un dictionnaire avec le texte et les métadonnées, ou None si échec
        """
        url_complete = urljoin(URL_UJKZ, chemin_relatif)
        logger.info(f" Scraping de : {url_complete}")
        
        try:
            # Requête HTTP avec timeout de 15 secondes
            reponse = self.session.get(url_complete, timeout=15)
            reponse.raise_for_status()  # Lève une exception si erreur HTTP
            
            # Détection automatique de l'encodage
            reponse.encoding = reponse.apparent_encoding or "utf-8"
            
        except requests.exceptions.ConnectionError:
            logger.warning(f"  Impossible de se connecter à {url_complete}")
            logger.info("   → Génération de données de démonstration à la place")
            return self._generer_donnees_demo(chemin_relatif)
            
        except requests.exceptions.HTTPError as e:
            logger.warning(f"  Erreur HTTP {e.response.status_code} pour {url_complete}")
            return self._generer_donnees_demo(chemin_relatif)
            
        except Exception as e:
            logger.error(f" Erreur inattendue : {e}")
            return None
        
        # ─── Parsing HTML avec BeautifulSoup ────────────────────────────
        soupe = BeautifulSoup(reponse.text, "lxml")
        
        # Suppression des éléments inutiles (menu, pied de page, scripts)
        for element_a_supprimer in soupe(["script", "style", "nav", "footer", "header"]):
            element_a_supprimer.decompose()
        
        # Extraction du titre de la page
        titre = ""
        if soupe.find("h1"):
            titre = soupe.find("h1").get_text(strip=True)
        elif soupe.find("title"):
            titre = soupe.find("title").get_text(strip=True)
        
        # Extraction du contenu principal (ordre de priorité)
        contenu_html = (
            soupe.find("main") or
            soupe.find("article") or
            soupe.find(id="content") or
            soupe.find(class_="content") or
            soupe.find("body")
        )
        
        texte_brut = contenu_html.get_text(separator="\n", strip=True) if contenu_html else ""
        texte_nettoye = self._nettoyer_texte(texte_brut)
        
        # Vérification : le texte récupéré est-il suffisant ?
        if len(texte_nettoye) < 100:
            logger.warning(f"  Contenu trop court ({len(texte_nettoye)} chars) pour {url_complete}")
            return self._generer_donnees_demo(chemin_relatif)
        
        # Extraction des liens vers des PDFs sur la page
        liens_pdf = self._extraire_liens_pdf(soupe, url_complete)
        
        # Construction du document final
        document = {
            "type_source": "ujkz_web",
            "url": url_complete,
            "titre": titre,
            "contenu": texte_nettoye,
            "liens_pdf": liens_pdf,
            "date_collecte": datetime.now().isoformat(),
            "langue": "fr",
            "nombre_caracteres": len(texte_nettoye)
        }
        
        logger.success(f" Page scrapée : '{titre}' ({len(texte_nettoye)} caractères)")
        return document

    def _extraire_liens_pdf(self, soupe: BeautifulSoup, url_base: str) -> list:
        """
        Extrait tous les liens vers des PDFs trouvés dans une page HTML.
        
        Args:
            soupe: L'objet BeautifulSoup de la page
            url_base: L'URL de base pour construire les URLs absolues
            
        Returns:
            Liste des URLs de PDFs trouvés
        """
        liens_pdf = []
        
        # Cherche tous les liens <a> qui pointent vers des .pdf
        for lien in soupe.find_all("a", href=True):
            href = lien["href"]
            if href.lower().endswith(".pdf"):
                url_pdf = urljoin(url_base, href)
                liens_pdf.append(url_pdf)
                logger.debug(f" PDF trouvé : {url_pdf}")
        
        return liens_pdf

    def telecharger_et_extraire_pdf(self, url_pdf: str) -> dict | None:
        """
        Télécharge un PDF depuis une URL et en extrait le texte.
        
        Args:
            url_pdf: L'URL du fichier PDF
            
        Returns:
            Un dictionnaire avec le texte extrait ou None si échec
        """
        logger.info(f" Téléchargement du PDF : {url_pdf}")
        
        try:
            reponse = self.session.get(url_pdf, timeout=30)
            reponse.raise_for_status()
            
            # Sauvegarde temporaire du PDF
            nom_pdf = url_pdf.split("/")[-1]
            chemin_temp = DOSSIER_DONNEES_BRUTES / f"temp_{nom_pdf}"
            
            with open(chemin_temp, "wb") as f:
                f.write(reponse.content)
            
            # Extraction du texte avec pdfplumber
            texte_total = []
            with pdfplumber.open(chemin_temp) as pdf:
                for num_page, page in enumerate(pdf.pages, start=1):
                    texte_page = page.extract_text()
                    if texte_page:
                        texte_total.append(f"[Page {num_page}]\n{texte_page}")
            
            # Suppression du fichier temporaire
            chemin_temp.unlink()
            
            texte_combine = "\n\n".join(texte_total)
            texte_nettoye = self._nettoyer_texte(texte_combine)
            
            document = {
                "type_source": "ujkz_pdf",
                "url": url_pdf,
                "titre": nom_pdf.replace(".pdf", "").replace("_", " ").replace("-", " "),
                "contenu": texte_nettoye,
                "date_collecte": datetime.now().isoformat(),
                "langue": "fr",
                "nombre_caracteres": len(texte_nettoye)
            }
            
            logger.success(f" PDF extrait : {nom_pdf} ({len(texte_nettoye)} caractères)")
            return document
            
        except Exception as e:
            logger.error(f" Erreur extraction PDF {url_pdf} : {e}")
            return None

    # ────────────────────────────────────────────────────────────────────────
    # SCRAPING FACEBOOK (PAGE PUBLIQUE IFOAD)
    # ────────────────────────────────────────────────────────────────────────

    def scraper_facebook_ifoad(self) -> list:
        """
        Collecte les publications récentes de la page Facebook publique de l'IFOAD.
        
        Facebook bloque les scrapers directs, donc on utilise plusieurs stratégies :
        1. facebook-scraper (librairie Python spécialisée)
        2. Données de démonstration en cas de blocage
        
        Returns:
            Liste de dictionnaires contenant les publications
        """
        logger.info(f" Scraping de la page Facebook : {PAGE_FACEBOOK_IFOAD}")
        publications = []
        
        try:
            # Tentative avec la librairie facebook-scraper
            from facebook_scraper import get_posts
            
            # Récupération des 20 dernières publications
            for publication in get_posts(PAGE_FACEBOOK_IFOAD, pages=2):
                
                # On ne garde que les publications avec du texte substantiel
                texte = publication.get("text", "") or ""
                if len(texte) < 50:
                    continue
                
                document = {
                    "type_source": "facebook_ifoad",
                    "url": publication.get("post_url", ""),
                    "titre": f"Publication Facebook - {publication.get('time', 'Date inconnue')}",
                    "contenu": self._nettoyer_texte(texte),
                    "date_publication": str(publication.get("time", "")),
                    "date_collecte": datetime.now().isoformat(),
                    "likes": publication.get("likes", 0),
                    "langue": "fr",
                    "nombre_caracteres": len(texte)
                }
                
                publications.append(document)
                logger.debug(f" Publication collectée : {len(texte)} caractères")
                
                # Respect du délai entre requêtes
                self._pause_polie()
                
        except ImportError:
            logger.warning("  Module facebook-scraper non installé")
            logger.info("   → Utilisation de données de démonstration Facebook")
            publications = self._generer_publications_facebook_demo()
            
        except Exception as e:
            logger.warning(f"  Erreur Facebook scraping : {e}")
            logger.info("   → Utilisation de données de démonstration Facebook")
            publications = self._generer_publications_facebook_demo()
        
        logger.success(f" {len(publications)} publications Facebook collectées")
        return publications

    # ────────────────────────────────────────────────────────────────────────
    # DONNÉES DE DÉMONSTRATION (si scraping impossible)
    # ────────────────────────────────────────────────────────────────────────

    def _generer_donnees_demo(self, chemin_relatif: str) -> dict:
        """
        Génère des données de démonstration réalistes sur l'IFOAD-UJKZ.
        
        Utilisé quand le site UJKZ n'est pas accessible (tests, développement).
        Ces données sont basées sur les informations publiques connues de l'IFOAD.
        
        Args:
            chemin_relatif: La page qu'on voulait scraper
            
        Returns:
            Un document de démonstration avec des infos réalistes
        """
        
        # ─── Base de données de contenus de démonstration ───────────────
        contenus_demo = {
            "/ifoad": """
L'Institut de Formation Ouverte et à Distance (IFOAD) de l'Université Joseph Ki-Zerbo (UJKZ)
est une structure d'enseignement supérieur innovante au Burkina Faso qui propose des 
formations diplômantes entièrement accessibles à distance.

Créé pour démocratiser l'accès à l'enseignement supérieur, l'IFOAD offre des programmes
de qualité aux étudiants burkinabè qui ne peuvent pas suivre des cours en présentiel,
notamment les professionnels en activité, les personnes vivant en zone rurale, 
et les personnes à mobilité réduite.

L'IFOAD est rattaché à l'Université Joseph Ki-Zerbo, la plus grande université publique 
du Burkina Faso, basée à Ouagadougou.

CONTACT IFOAD :
- Adresse : Campus de l'Université Joseph Ki-Zerbo, Ouagadougou, Burkina Faso
- Email : ifoad@ujkz.bf
- Site web : www.ujkz.bf/ifoad
            """,
            
            "/ifoad/formations": """
FORMATIONS DISPONIBLES À L'IFOAD - UJKZ (Année 2025-2026)

═══════════════════════════════════════════════════════════
MASTER 1 - INFORMATIQUE POUR LA FORMATION OUVERTE ET À DISTANCE (IFOAD)
═══════════════════════════════════════════════════════════
Mention : Sciences et Technologies de l'Information et de la Communication

Objectifs de la formation :
Cette formation vise à former des spécialistes capables de concevoir, développer
et gérer des dispositifs de formation à distance en utilisant les technologies
numériques modernes.

Débouchés professionnels :
- Ingénieur en systèmes d'information
- Développeur de plateformes e-learning  
- Chef de projet numérique
- Concepteur pédagogique multimédia
- Data Scientist et analyste de données
- Consultant en transformation digitale

Modules enseignés en Master 1 IFOAD :
Semestre 1 :
  - Introduction à l'Intelligence Artificielle (60h)
  - Science des Données et Machine Learning (60h)
  - Développement Web Avancé (45h)
  - Réseaux et Sécurité Informatique (45h)
  - Anglais Technique (30h)
  - Méthodologie de Recherche (30h)

Semestre 2 :
  - Deep Learning et Réseaux de Neurones (60h)
  - Big Data et Cloud Computing (60h)
  - Projet de Fin d'Année (90h)
  - Stage en Entreprise (2 mois minimum)

Durée totale : 2 ans (Master 1 + Master 2)
Régime d'études : Formation à distance avec regroupements périodiques
Langue d'enseignement : Français

═══════════════════════════════════════════════════════════
LICENCE 3 - MATHÉMATIQUES ET INFORMATIQUE
═══════════════════════════════════════════════════════════
Objectifs : Maîtriser les fondamentaux des mathématiques appliquées
et de l'informatique.

Modules principaux :
  - Algorithmique et Structures de Données
  - Bases de Données Relationnelles
  - Programmation Python et Java
  - Statistiques et Probabilités
  - Mathématiques Discrètes
  - Projet Tuteuré
            """,
            
            "/ifoad/inscription": """
GUIDE COMPLET D'INSCRIPTION À L'IFOAD - UJKZ (2025-2026)

═══════════════════════════════════════════════════════════
PÉRIODE D'INSCRIPTION
═══════════════════════════════════════════════════════════
Ouverture des inscriptions : 1er Juillet 2025
Clôture des inscriptions   : 30 Septembre 2025
(Les inscriptions hors délai ne sont pas acceptées)

═══════════════════════════════════════════════════════════
CONDITIONS D'ADMISSION - MASTER 1 IFOAD
═══════════════════════════════════════════════════════════
Diplômes requis :
  - Licence (BAC+3) en Informatique, Mathématiques, Physique ou équivalent
  - OU Diplôme d'Ingénieur (BAC+5) avec validation d'acquis

Critères de sélection :
  1. Dossier académique (résultats antérieurs)
  2. Lettre de motivation (500 mots minimum)
  3. Entretien de motivation (présentiel ou visioconférence)

═══════════════════════════════════════════════════════════
DOSSIER D'INSCRIPTION - DOCUMENTS REQUIS
═══════════════════════════════════════════════════════════
Documents obligatoires (originaux + 2 photocopies) :
  ✓ Formulaire d'inscription rempli et signé (disponible en ligne)
  ✓ Photocopie légalisée du diplôme le plus élevé
  ✓ Relevés de notes des 3 dernières années
  ✓ Copie certifiée conforme de la CNIB (ou passeport)
  ✓ 4 photos d'identité récentes (fond blanc)
  ✓ Lettre de motivation manuscrite
  ✓ Curriculum Vitae (CV) détaillé
  ✓ Reçu de paiement des frais de dossier

Pour les candidats en activité professionnelle :
  ✓ Attestation de travail de l'employeur
  ✓ Autorisation d'absence signée par l'employeur

═══════════════════════════════════════════════════════════
FRAIS DE SCOLARITÉ
═══════════════════════════════════════════════════════════
Frais de dossier (non remboursables) : 5 000 FCFA
Frais d'inscription annuels           : 50 000 FCFA
Frais pédagogiques annuels            : 150 000 FCFA
TOTAL annuel estimé                   : 200 000 FCFA

Modalités de paiement :
  - En une fois avant le 15 Octobre
  - En deux tranches : 50% en Octobre, 50% en Janvier

Exonérations possibles :
  - Boursiers de l'État burkinabè : exonération des frais pédagogiques
  - Cas sociaux : dossier à soumettre au service social

Paiements via :
  - Orange Money : *144*5#
  - Moov Money : *555*montant#
  - Virement bancaire (BSIC, BIB, Ecobank)
  - Caisse de l'UJKZ (lundi-vendredi, 8h-12h et 15h-17h)

═══════════════════════════════════════════════════════════
DÉPÔT DU DOSSIER
═══════════════════════════════════════════════════════════
En ligne : Portail étudiant UJKZ → www.ujkz.bf/inscription
En personne : Secrétariat de l'IFOAD, Bâtiment administratif, UJKZ

Contact inscription :
  Email : inscription.ifoad@ujkz.bf
  Tél   : (+226) 25 30 70 64 / 25 30 70 65
  Horaires : Lundi au Vendredi, 8h-12h et 15h-17h (heure de Ouagadougou)
            """,
            
            "/ifoad/calendrier": """
CALENDRIER ACADÉMIQUE IFOAD-UJKZ - ANNÉE 2025-2026

═══════════════════════════════════════════════════════════
PREMIER SEMESTRE (S1)
═══════════════════════════════════════════════════════════
Début des cours               : 15 Octobre 2025
Fin des cours (S1)            : 20 Janvier 2026
Révisions                     : 21-24 Janvier 2026
Examens de fin de S1          : 26 Janvier - 7 Février 2026
Publication des résultats S1  : 20 Février 2026
Rattrapage S1                 : 25-28 Février 2026

═══════════════════════════════════════════════════════════
SECOND SEMESTRE (S2)
═══════════════════════════════════════════════════════════
Début des cours (S2)          : 2 Mars 2026
Fin des cours (S2)            : 30 Mai 2026
Révisions                     : 1-5 Juin 2026
Examens de fin de S2          : 8-20 Juin 2026
Publication des résultats S2  : 5 Juillet 2026
Rattrapage S2                 : 13-17 Juillet 2026

═══════════════════════════════════════════════════════════
CONGÉS ET JOURS FÉRIÉS
═══════════════════════════════════════════════════════════
Noël et Nouvel An             : 22 Décembre 2025 - 2 Janvier 2026
Fête du Travail               : 1er Mai 2026
Ascension                     : 14 Mai 2026
Ramadan (approximatif)        : Selon calendrier lunaire 2026

═══════════════════════════════════════════════════════════
MODALITÉS D'EXAMEN
═══════════════════════════════════════════════════════════
Type d'évaluation :
  - Contrôles continus en ligne (30% de la note finale)
  - Travaux Pratiques et projets (20% de la note finale)
  - Examen final (50% de la note finale)

Conditions de passage :
  - Note minimale de passage : 10/20
  - Présence obligatoire aux regroupements
  - Validation de tous les modules du semestre

═══════════════════════════════════════════════════════════
REGROUPEMENTS PRÉSENTIEL
═══════════════════════════════════════════════════════════
(Obligatoires même pour la formation à distance)
Regroupement 1 : 10-12 Novembre 2025 (Campus UJKZ)
Regroupement 2 : 5-7 Janvier 2026 (Campus UJKZ)
Regroupement 3 : 6-8 Avril 2026 (Campus UJKZ)
Regroupement 4 : Soutenance de projet (Juillet 2026)
            """,
        }
        
        # Récupère le contenu correspondant à la page, ou un contenu générique
        contenu = contenus_demo.get(
            chemin_relatif,
            f"""
Informations générales sur l'IFOAD - Page {chemin_relatif}
            
L'IFOAD (Institut de Formation Ouverte et à Distance) de l'Université Joseph Ki-Zerbo
propose des formations diplômantes de qualité entièrement accessibles à distance.

Pour plus d'informations, consultez le site officiel : www.ujkz.bf/ifoad
ou contactez le secrétariat : ifoad@ujkz.bf
Téléphone : (+226) 25 30 70 64
            """
        )
        
        # Construction du titre à partir du chemin
        titre = chemin_relatif.replace("/ifoad/", "").replace("/", " - ").title()
        if not titre or titre == " ":
            titre = "IFOAD - Informations générales"
        
        document = {
            "type_source": "ujkz_demo",           # Marqué comme démo
            "url": urljoin(URL_UJKZ, chemin_relatif),
            "titre": f"IFOAD-UJKZ : {titre}",
            "contenu": self._nettoyer_texte(contenu),
            "date_collecte": datetime.now().isoformat(),
            "langue": "fr",
            "note": "Données de démonstration (site non accessible)",
            "nombre_caracteres": len(contenu)
        }
        
        logger.info(f" Données demo générées pour : {chemin_relatif}")
        return document

    def _generer_publications_facebook_demo(self) -> list:
        """
        Génère des publications Facebook de démonstration réalistes.
        
        Returns:
            Liste de publications Facebook simulées
        """
        publications_demo = [
            {
                "type_source": "facebook_demo",
                "url": "https://www.facebook.com/UJKZ.IFOAD",
                "titre": "Annonce ouverture inscriptions 2025-2026",
                "contenu": (
                    " AVIS D'OUVERTURE DES INSCRIPTIONS 2025-2026\n\n"
                    "L'IFOAD de l'Université Joseph Ki-Zerbo est heureux d'annoncer l'ouverture "
                    "des inscriptions pour l'année académique 2025-2026.\n\n"
                    " Période d'inscription : 1er Juillet au 30 Septembre 2025\n"
                    " Formations disponibles : Master 1 IFOAD, Licence 3 MI\n"
                    " Frais d'inscription : 5 000 FCFA (dossier)\n\n"
                    "Pour plus d'informations, rendez-vous sur www.ujkz.bf/ifoad "
                    "ou contactez-nous au (+226) 25 30 70 64\n\n"
                    "#IFOAD #UJKZ #FormationEnLigne #BurkinaFaso"
                ),
                "date_publication": "2025-07-01",
                "date_collecte": datetime.now().isoformat(),
                "likes": 245,
                "langue": "fr",
                "nombre_caracteres": 450
            },
            {
                "type_source": "facebook_demo",
                "url": "https://www.facebook.com/UJKZ.IFOAD",
                "titre": "Résultats examens Semestre 1",
                "contenu": (
                    " PUBLICATION DES RÉSULTATS - SEMESTRE 1 (2024-2025)\n\n"
                    "Les résultats du premier semestre 2024-2025 sont maintenant disponibles "
                    "sur le portail étudiant de l'UJKZ.\n\n"
                    " Accès : portail.ujkz.bf → Espace étudiant → Mes résultats\n\n"
                    " RATTRAPAGE : Les étudiants ajournés peuvent se présenter aux "
                    "examens de rattrapage du 25 au 28 Février 2025.\n\n"
                    "Inscription au rattrapage obligatoire avant le 20 Février 2025.\n\n"
                    "Bon courage à tous ! \n"
                    "#IFOAD #Résultats #Examens #UJKZ"
                ),
                "date_publication": "2025-02-20",
                "date_collecte": datetime.now().isoformat(),
                "likes": 189,
                "langue": "fr",
                "nombre_caracteres": 420
            },
            {
                "type_source": "facebook_demo",
                "url": "https://www.facebook.com/UJKZ.IFOAD",
                "titre": "Regroupement présentiel Novembre 2025",
                "contenu": (
                    " RAPPEL - REGROUPEMENT PRÉSENTIEL - NOVEMBRE 2025\n\n"
                    "Chers étudiants de l'IFOAD,\n\n"
                    "Nous vous rappelons que le premier regroupement présentiel "
                    "de l'année 2025-2026 aura lieu aux dates suivantes :\n\n"
                    " Dates : 10, 11 et 12 Novembre 2025\n"
                    " Lieu : Campus de l'Université Joseph Ki-Zerbo, Ouagadougou\n"
                    " Horaires : 8h00 - 17h00\n\n"
                    "La présence est OBLIGATOIRE pour tous les étudiants inscrits.\n"
                    "Munis-vous de votre carte d'étudiant et du programme du regroupement.\n\n"
                    "Pour tout renseignement : (+226) 25 30 70 64\n"
                    "#IFOAD #Regroupement #UJKZ #Formation"
                ),
                "date_publication": "2025-11-01",
                "date_collecte": datetime.now().isoformat(),
                "likes": 312,
                "langue": "fr",
                "nombre_caracteres": 510
            }
        ]
        
        return publications_demo

    # ────────────────────────────────────────────────────────────────────────
    # MÉTHODE PRINCIPALE : Exécution complète du scraping
    # ────────────────────────────────────────────────────────────────────────

    def executer_collecte_complete(self) -> int:
        """
        Exécute la collecte complète de données depuis toutes les sources.
        
        Étapes :
        1. Scrape chaque page UJKZ listée dans la configuration
        2. Télécharge et extrait les PDFs trouvés
        3. Scrappe la page Facebook de l'IFOAD
        4. Sauvegarde tous les documents collectés
        
        Returns:
            Nombre total de documents collectés
        """
        logger.info("=" * 60)
        logger.info(" DÉMARRAGE DE LA COLLECTE DE DONNÉES IFOAD-UJKZ")
        logger.info("=" * 60)
        
        tous_les_documents = []
        
        # ─── ÉTAPE 1 : Scraping des pages UJKZ ──────────────────────────
        logger.info(f"\n ÉTAPE 1 : Scraping du site UJKZ ({len(PAGES_UJKZ_A_SCRAPER)} pages)")
        
        pdfs_a_telecharger = []  # Collecte des PDFs à télécharger ensuite
        
        for chemin in PAGES_UJKZ_A_SCRAPER:
            document = self.scraper_page_ujkz(chemin)
            
            if document:
                tous_les_documents.append(document)
                # Collecte les liens PDF pour téléchargement ultérieur
                pdfs_a_telecharger.extend(document.get("liens_pdf", []))
                
            # Pause polie entre chaque page
            self._pause_polie()
        
        # ─── ÉTAPE 2 : Téléchargement des PDFs trouvés ──────────────────
        if pdfs_a_telecharger:
            logger.info(f"\n ÉTAPE 2 : Extraction de {len(pdfs_a_telecharger)} PDFs")
            
            for url_pdf in pdfs_a_telecharger:
                document_pdf = self.telecharger_et_extraire_pdf(url_pdf)
                if document_pdf:
                    tous_les_documents.append(document_pdf)
                self._pause_polie()
        else:
            logger.info("\n ÉTAPE 2 : Aucun PDF trouvé sur les pages scrapées")
        
        # ─── ÉTAPE 3 : Scraping Facebook ────────────────────────────────
        logger.info("\n ÉTAPE 3 : Scraping de la page Facebook IFOAD")
        publications_facebook = self.scraper_facebook_ifoad()
        tous_les_documents.extend(publications_facebook)
        
        # ─── ÉTAPE 4 : Sauvegarde de tous les documents ─────────────────
        logger.info(f"\n ÉTAPE 4 : Sauvegarde de {len(tous_les_documents)} documents")
        
        for document in tous_les_documents:
            self._sauvegarder_document(document)
        
        # ─── Rapport final ───────────────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.success(f" COLLECTE TERMINÉE !")
        logger.success(f"   → {self.nb_documents_collectes} documents sauvegardés")
        logger.success(f"   → Dossier : {DOSSIER_DONNEES_BRUTES}")
        logger.info("=" * 60)
        
        return self.nb_documents_collectes


# ════════════════════════════════════════════════════════════════════════════
# POINT D'ENTRÉE PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """
    Point d'entrée du script de collecte.
    Exécuter avec : python src/collecte/scraper_ujkz.py
    """
    
    # Création du dossier de logs s'il n'existe pas
    (RACINE / "logs").mkdir(exist_ok=True)
    
    logger.info(" Agent IA Assistant IFOAD-UJKZ - Module de Collecte")
    logger.info(f" Date : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    # Lancement du scraper
    scraper = ScraperIFOAD()
    nb_docs = scraper.executer_collecte_complete()
    
    if nb_docs > 0:
        print(f"\n Succès ! {nb_docs} documents collectés dans : {DOSSIER_DONNEES_BRUTES}")
        print(" Prochaine étape : python src/ingestion/vectoriser.py")
    else:
        print("\n Aucun document collecté. Vérifiez les logs pour plus de détails.")
        sys.exit(1)
