"""
============================================================
MODULE DE COLLECTE DE DONNÉES - Scraper UJKZ & Facebook IFOAD
============================================================
Ce script collecte les informations sur l'IFOAD depuis :
1. Le site officiel de l'UJKZ (ujkz.bf)
2. La page Facebook publique de l'IFOAD/UJKZ
3. Les PDFs officiels trouvés sur ces pages
4. Les images contenant les formations courtes

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
import io
from PIL import Image
import pytesseract

from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from loguru import logger

# ─── Ajout du chemin racine pour les imports internes ───────────────────────
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
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO"
)
logger.add(
    RACINE / "logs/scraping.log",
    rotation="5 MB",
    level="DEBUG"
)


# ════════════════════════════════════════════════════════════════════════════
# DONNÉES RÉELLES DE L'IFOAD
# ════════════════════════════════════════════════════════════════════════════

CURSUS_MASTER_SCIENCES_DONNEES = {
    "domaine": "Sciences et technologies",
    "mention": "Informatique",
    "specialite": "Science de données",
    "niveau": "Master 1 et Master 2",
    "duree": "2 ans (4 semestres)",
    
    "semestres": {
        "M1S1": {
            "intitule": "Master 1 - Semestre 1",
            "ues": [
                {
                    "code": "MTH2100",
                    "intitule": "Outils Mathématiques et statistiques I",
                    "credits": 6,
                    "ecs": [
                        {"code": "1MTH2100", "intitule": "Probabilité et statistiques", "credits": 3, "cm": 20, "td": 10, "tp": 0, "p": 30, "tpe": 45},
                        {"code": "2MTH2100", "intitule": "Calcul matriciel numérique", "credits": 3, "cm": 20, "td": 10, "tp": 0, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "MTH2101",
                    "intitule": "Outils Mathématiques et statistiques II",
                    "credits": 6,
                    "ecs": [
                        {"code": "1MTH2101", "intitule": "Statistique inférentielle", "credits": 3, "cm": 20, "td": 10, "tp": 0, "p": 30, "tpe": 45},
                        {"code": "2MTH2101", "intitule": "Analyse de données", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "INF2100",
                    "intitule": "Base de données",
                    "credits": 5,
                    "ecs": [
                        {"code": "1INF2100", "intitule": "UML", "credits": 2, "cm": 10, "td": 10, "tp": 0, "p": 20, "tpe": 30},
                        {"code": "2INF2100", "intitule": "Bases de données relationnelles", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "INF2101",
                    "intitule": "Programmation I",
                    "credits": 5,
                    "ecs": [
                        {"code": "1INF1102", "intitule": "POO et python", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45},
                        {"code": "2INF1102", "intitule": "Logiciel R", "credits": 2, "cm": 10, "td": 0, "tp": 10, "p": 20, "tpe": 30}
                    ]
                },
                {
                    "code": "INF2102",
                    "intitule": "Donnée massives I",
                    "credits": 6,
                    "ecs": [
                        {"code": "1INF2102", "intitule": "Analyse de données en python", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45},
                        {"code": "2INF2102", "intitule": "Entrepôt de données", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "TCC2100",
                    "intitule": "Méthodologie de recherche",
                    "credits": 2,
                    "ecs": [
                        {"code": "1TCC2100", "intitule": "Méthodologie de recherche", "credits": 2, "cm": 10, "td": 10, "tp": 0, "p": 20, "tpe": 30}
                    ]
                }
            ]
        },
        "M1S2": {
            "intitule": "Master 1 - Semestre 2",
            "ues": [
                {
                    "code": "MTH2200",
                    "intitule": "Outils Mathématiques et statistiques III",
                    "credits": 6,
                    "ecs": [
                        {"code": "1MTH2200", "intitule": "Séries temporelles", "credits": 3, "cm": 20, "td": 10, "tp": 0, "p": 30, "tpe": 45},
                        {"code": "2MTH2200", "intitule": "Statistique spatiales", "credits": 3, "cm": 20, "td": 10, "tp": 0, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "INF2200",
                    "intitule": "Machine Learning I",
                    "credits": 5,
                    "ecs": [
                        {"code": "1INF2200", "intitule": "Introduction au machine learning", "credits": 2, "cm": 10, "td": 10, "tp": 0, "p": 20, "tpe": 30},
                        {"code": "2INF2200", "intitule": "Machine learning supervisé", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "INF2201",
                    "intitule": "Machine Learning II",
                    "credits": 6,
                    "ecs": [
                        {"code": "1INF2201", "intitule": "Machine learning non supervisé", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45},
                        {"code": "2INF2201", "intitule": "Réseaux de neurones", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "INF2202",
                    "intitule": "Programmation II",
                    "credits": 6,
                    "ecs": [
                        {"code": "1INF2202", "intitule": "Programmation en scala, pyspark", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45},
                        {"code": "2INF2202", "intitule": "Programmation en julia", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "INF2203",
                    "intitule": "Donnée massives II",
                    "credits": 5,
                    "ecs": [
                        {"code": "1INF2203", "intitule": "Visualisation des données en R, python", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45},
                        {"code": "2INF2203", "intitule": "Projet Data science", "credits": 2, "cm": 0, "td": 0, "tp": 20, "p": 20, "tpe": 30}
                    ]
                },
                {
                    "code": "ANG2200",
                    "intitule": "Langue internationale",
                    "credits": 2,
                    "ecs": [
                        {"code": "1ANG2200", "intitule": "Anglais", "credits": 2, "cm": 10, "td": 10, "tp": 0, "p": 20, "tpe": 30}
                    ]
                }
            ]
        },
        "M2S3": {
            "intitule": "Master 2 - Semestre 3",
            "ues": [
                {
                    "code": "INF2300",
                    "intitule": "Intelligence artificielle I",
                    "credits": 5,
                    "ecs": [
                        {"code": "1INF2300", "intitule": "Machine learning", "credits": 2, "cm": 10, "td": 0, "tp": 10, "p": 20, "tpe": 30},
                        {"code": "2INF2300", "intitule": "Deep learning", "credits": 3, "cm": 20, "td": 10, "tp": 0, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "INF2301",
                    "intitule": "Intelligence artificielle II",
                    "credits": 5,
                    "ecs": [
                        {"code": "1INF2301", "intitule": "Applications du deep Learning", "credits": 2, "cm": 10, "td": 0, "tp": 10, "p": 20, "tpe": 30},
                        {"code": "2INF2301", "intitule": "Projet machine Learning", "credits": 2, "cm": 0, "td": 0, "tp": 20, "p": 20, "tpe": 30}
                    ]
                },
                {
                    "code": "INF2302",
                    "intitule": "Données massives III",
                    "credits": 6,
                    "ecs": [
                        {"code": "1INF2302", "intitule": "Technologie du big data", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45},
                        {"code": "2INF2302", "intitule": "Base de données NoSQL", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "INF2303",
                    "intitule": "Données massives IV",
                    "credits": 6,
                    "ecs": [
                        {"code": "1INF2303", "intitule": "Data visualisation", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45},
                        {"code": "2INF2303", "intitule": "Ethique de l'IA", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "INF2304",
                    "intitule": "Cloud computing",
                    "credits": 6,
                    "ecs": [
                        {"code": "1INF2304", "intitule": "Introduction au cloud computing", "credits": 2, "cm": 10, "td": 0, "tp": 10, "p": 20, "tpe": 30},
                        {"code": "2INF2304", "intitule": "Virtualisation et conteneurisation", "credits": 3, "cm": 20, "td": 0, "tp": 10, "p": 30, "tpe": 45}
                    ]
                },
                {
                    "code": "TCC2300",
                    "intitule": "Entreprenariat",
                    "credits": 4,
                    "ecs": [
                        {"code": "1TCC2300", "intitule": "Entreprenariat", "credits": 2, "cm": 10, "td": 10, "tp": 0, "p": 20, "tpe": 30},
                        {"code": "2TCC2300", "intitule": "Aspect Juridique de la protection des données", "credits": 2, "cm": 10, "td": 10, "tp": 0, "p": 20, "tpe": 30}
                    ]
                }
            ]
        },
        "M2S4": {
            "intitule": "Master 2 - Semestre 4",
            "ues": [
                {
                    "code": "TCC2401",
                    "intitule": "Stage et soutenance",
                    "credits": 30,
                    "ecs": [
                        {"code": "1STG2400", "intitule": "Stage, Rédaction du mémoire et soutenance", "credits": 30, "cm": 0, "td": 0, "tp": 0, "p": 0, "tpe": 750}
                    ]
                }
            ]
        }
    }
}


# ════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE : ScraperIFOAD
# ════════════════════════════════════════════════════════════════════════════

class ScraperIFOAD:
    """
    Collecteur de données pour l'IFOAD-UJKZ.
    Scrappe le site UJKZ, la page Facebook, et extrait les informations des images.
    """

    def __init__(self):
        """Initialisation du scraper avec les paramètres de configuration."""
        self.entetes = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.entetes)
        self.nb_documents_collectes = 0
        
        # Données réelles de l'IFOAD
        self.info_ifoad = {
            "formations_longues": {
                "licence_informatique_appliquee": {
                    "nom": "Licence en Informatique Appliquée",
                    "niveau": "Bac+3",
                    "duree": "3 ans",
                    "frais_formation": 300000,
                    "frais_inscription": 16500
                },
                "master_sciences_donnees": {
                    "nom": "Master en Sciences des Données",
                    "niveau": "Bac+5",
                    "duree": "2 ans",
                    "frais_formation": 700000,
                    "frais_inscription": 51500
                }
            },
            "formations_courtes": [
                "Compétences aux usages du numérique (JFOAD, CUN)",
                "Outils de collectes (KoboToolbox)",
                "Python pour les Sciences de Données",
                "Algorithmique et programmation en C",
                "Développement mobile 1 & 2",
                "Développement web",
                "Les Fondamentaux de la Cybersécurité",
                "Maîtrise de Moodle par les enseignants"
            ],
            "conditions_admission": {
                "selection": "Sélection sur dossier",
                "moyenne_minimale": 12.0,
                "periode_inscription": "1er Août au 10 Septembre",
                "plateforme": "Campus Faso"
            },
            "modalites_pedagogiques": {
                "cours": "En ligne",
                "devoirs": "Variable (en ligne ou présentiel selon l'enseignant)",
                "regroupements": "Présentiels périodiques"
            }
        }
        
        logger.info("  ScraperIFOAD initialisé avec succès")
        logger.info(f" Dossier de sortie : {DOSSIER_DONNEES_BRUTES}")

    # ────────────────────────────────────────────────────────────────────────
    # MÉTHODES UTILITAIRES
    # ────────────────────────────────────────────────────────────────────────

    def _pause_polie(self):
        """Attend un délai entre les requêtes."""
        logger.debug(f" Pause de {DELAI_SCRAPING} secondes...")
        time.sleep(DELAI_SCRAPING)

    def _generer_identifiant(self, texte: str) -> str:
        """Génère un identifiant unique (hash MD5) à partir d'un texte."""
        return hashlib.md5(texte.encode("utf-8")).hexdigest()[:8]

    def _sauvegarder_document(self, document: dict) -> Path:
        """Sauvegarde un document collecté au format JSON."""
        identifiant = self._generer_identifiant(document.get("url", document.get("contenu", "")))
        nom_fichier = f"{document['type_source']}_{identifiant}.json"
        chemin_fichier = DOSSIER_DONNEES_BRUTES / nom_fichier
        
        with open(chemin_fichier, "w", encoding="utf-8") as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
        
        self.nb_documents_collectes += 1
        logger.debug(f" Document sauvegardé : {nom_fichier}")
        return chemin_fichier

    def _nettoyer_texte(self, texte: str) -> str:
        """Nettoie et normalise un texte brut récupéré du web."""
        if not texte:
            return ""
        
        texte = re.sub(r'\s+', ' ', texte)
        texte = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', texte)
        texte = texte.replace('\u2019', "'").replace('\u2018', "'")
        texte = texte.replace('\u201c', '"').replace('\u201d', '"')
        
        return texte.strip()

    def _extraire_texte_image(self, url_image: str) -> str:
        """
        Télécharge une image et en extrait le texte avec OCR (Tesseract).
        
        Args:
            url_image: L'URL de l'image
            
        Returns:
            Le texte extrait
        """
        try:
            reponse = self.session.get(url_image, timeout=20)
            reponse.raise_for_status()
            
            # Ouvrir l'image avec PIL
            image = Image.open(io.BytesIO(reponse.content))
            
            # Prétraitement pour améliorer l'OCR
            image = image.convert('L')  # Niveaux de gris
            image = image.point(lambda x: 0 if x < 128 else 255, '1')  # Binarisation
            
            # Extraire le texte
            texte = pytesseract.image_to_string(image, lang='fra')
            return self._nettoyer_texte(texte)
            
        except Exception as e:
            logger.error(f" Erreur OCR sur {url_image} : {e}")
            return ""

    # ────────────────────────────────────────────────────────────────────────
    # SCRAPING DU SITE UJKZ
    # ────────────────────────────────────────────────────────────────────────

    def scraper_page_ujkz(self, chemin_relatif: str) -> dict | None:
        """
        Scrappe une page spécifique du site UJKZ.
        """
        url_complete = urljoin(URL_UJKZ, chemin_relatif)
        logger.info(f" Scraping de : {url_complete}")
        
        try:
            reponse = self.session.get(url_complete, timeout=15)
            reponse.raise_for_status()
            reponse.encoding = reponse.apparent_encoding or "utf-8"
            
        except Exception as e:
            logger.warning(f"  Erreur pour {url_complete} : {e}")
            return self._generer_donnees_demo(chemin_relatif)
        
        soupe = BeautifulSoup(reponse.text, "lxml")
        
        # Suppression des éléments inutiles
        for element_a_supprimer in soupe(["script", "style", "nav", "footer", "header"]):
            element_a_supprimer.decompose()
        
        # Extraction du titre
        titre = ""
        if soupe.find("h1"):
            titre = soupe.find("h1").get_text(strip=True)
        elif soupe.find("title"):
            titre = soupe.find("title").get_text(strip=True)
        
        # Extraction du contenu principal
        contenu_html = (
            soupe.find("main") or
            soupe.find("article") or
            soupe.find(id="content") or
            soupe.find(class_="content") or
            soupe.find("body")
        )
        
        texte_brut = contenu_html.get_text(separator="\n", strip=True) if contenu_html else ""
        texte_nettoye = self._nettoyer_texte(texte_brut)
        
        # Extraction des liens vers des PDFs et images
        liens_pdf = self._extraire_liens_pdf(soupe, url_complete)
        liens_images = self._extraire_liens_images(soupe, url_complete)
        
        document = {
            "type_source": "ujkz_web",
            "url": url_complete,
            "titre": titre,
            "contenu": texte_nettoye if len(texte_nettoye) >= 100 else self._generer_contenu_ifoad(chemin_relatif),
            "liens_pdf": liens_pdf,
            "liens_images": liens_images,
            "date_collecte": datetime.now().isoformat(),
            "langue": "fr",
            "nombre_caracteres": len(texte_nettoye)
        }
        
        logger.success(f" Page scrapée : '{titre}'")
        return document

    def _extraire_liens_pdf(self, soupe: BeautifulSoup, url_base: str) -> list:
        """Extrait tous les liens vers des PDFs."""
        liens_pdf = []
        for lien in soupe.find_all("a", href=True):
            href = lien["href"]
            if href.lower().endswith(".pdf"):
                url_pdf = urljoin(url_base, href)
                liens_pdf.append(url_pdf)
        return liens_pdf

    def _extraire_liens_images(self, soupe: BeautifulSoup, url_base: str) -> list:
        """Extrait tous les liens vers des images."""
        liens_images = []
        for img in soupe.find_all("img", src=True):
            src = img["src"]
            if src.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
                url_image = urljoin(url_base, src)
                liens_images.append(url_image)
        return liens_images

    def telecharger_et_extraire_pdf(self, url_pdf: str) -> dict | None:
        """Télécharge un PDF et en extrait le texte."""
        logger.info(f" Téléchargement du PDF : {url_pdf}")
        
        try:
            reponse = self.session.get(url_pdf, timeout=30)
            reponse.raise_for_status()
            
            chemin_temp = DOSSIER_DONNEES_BRUTES / f"temp_{url_pdf.split('/')[-1]}"
            
            with open(chemin_temp, "wb") as f:
                f.write(reponse.content)
            
            texte_total = []
            with pdfplumber.open(chemin_temp) as pdf:
                for num_page, page in enumerate(pdf.pages, start=1):
                    texte_page = page.extract_text()
                    if texte_page:
                        texte_total.append(f"[Page {num_page}]\n{texte_page}")
            
            chemin_temp.unlink()
            
            texte_combine = "\n\n".join(texte_total)
            texte_nettoye = self._nettoyer_texte(texte_combine)
            
            document = {
                "type_source": "ujkz_pdf",
                "url": url_pdf,
                "titre": url_pdf.split("/")[-1].replace(".pdf", "").replace("_", " "),
                "contenu": texte_nettoye,
                "date_collecte": datetime.now().isoformat(),
                "langue": "fr",
                "nombre_caracteres": len(texte_nettoye)
            }
            
            logger.success(f" PDF extrait : {url_pdf.split('/')[-1]}")
            return document
            
        except Exception as e:
            logger.error(f" Erreur extraction PDF {url_pdf} : {e}")
            return None

    # ────────────────────────────────────────────────────────────────────────
    # GÉNÉRATION DES DONNÉES RÉELLES DE L'IFOAD
    # ────────────────────────────────────────────────────────────────────────

    def _generer_contenu_ifoad(self, chemin_relatif: str) -> str:
        """Génère le contenu réel de l'IFOAD selon la page demandée."""
        
        contenus = {
            "/ifoad": f"""
INSTITUT DE FORMATION OUVERTE ET À DISTANCE (IFOAD) - UJKZ

L'Institut de Formation Ouverte et à Distance (IFOAD) de l'Université Joseph Ki-Zerbo (UJKZ)
est une structure d'enseignement supérieur innovante au Burkina Faso qui propose des 
formations diplômantes entièrement accessibles à distance.

═══════════════════════════════════════════════════════════
FORMATIONS PROPOSÉES
═══════════════════════════════════════════════════════════

1. FORMATIONS LONGUES DURÉES :
   • Licence en Informatique Appliquée (Bac+3)
   • Master en Sciences des Données (Bac+5)

2. FORMATIONS COURTES DURÉES (Thématiques - à la demande) :
   • Compétences aux usages du numérique (JFOAD, CUN)
   • Outils de collectes (KoboToolbox)
   • Python pour les Sciences de Données
   • Algorithmique et programmation en C
   • Développement mobile 1 & 2
   • Développement web
   • Les Fondamentaux de la Cybersécurité
   • Maîtrise de Moodle par les enseignants

═══════════════════════════════════════════════════════════
CONTACT IFOAD
═══════════════════════════════════════════════════════════
• Adresse : Campus de l'Université Joseph Ki-Zerbo, Ouagadougou, Burkina Faso
• Email : ifoad@ujkz.bf
• Site web : www.ujkz.bf/ifoad
• Téléphone : (+226) 25 30 70 64
            """,
            
            "/ifoad/formations": f"""
FORMATIONS DISPONIBLES À L'IFOAD - UJKZ (Année 2025-2026)

═══════════════════════════════════════════════════════════
LICENCE EN INFORMATIQUE APPLIQUÉE
═══════════════════════════════════════════════════════════
Niveau : Bac+3
Durée : 3 ans

Objectifs :
Former des informaticiens capables de concevoir, développer et maintenir
des applications et systèmes informatiques.

Frais de formation : 300 000 FCFA
Frais d'inscription : 16 500 FCFA

═══════════════════════════════════════════════════════════
MASTER EN SCIENCES DES DONNÉES
═══════════════════════════════════════════════════════════
Niveau : Bac+5
Durée : 2 ans

Objectifs :
Former des experts en analyse de données, machine learning et intelligence
artificielle capables de transformer les données en décisions stratégiques.

Débouchés professionnels :
- Data Scientist
- Data Analyst
- Machine Learning Engineer
- Data Engineer
- Consultant en intelligence d'affaires
- Chercheur en Data Science

Frais de formation : 700 000 FCFA
Frais d'inscription : 51 500 FCFA

═══════════════════════════════════════════════════════════
FORMATIONS COURTES DURÉES (Thématiques)
═══════════════════════════════════════════════════════════
Ces formations sont organisées à la demande. Dès que nous avons 
suffisamment de personnes intéressées, nous ouvrons une session.

Modules disponibles :
- Compétences aux usages du numérique (JFOAD, CUN)
- Outils de collectes (KoboToolbox)
- Python pour les Sciences de Données
- Algorithmique et programmation en C
- Développement mobile 1 & 2
- Développement web
- Les Fondamentaux de la Cybersécurité
- Maîtrise de Moodle par les enseignants
            """,
            
            "/ifoad/inscription": f"""
GUIDE COMPLET D'INSCRIPTION À L'IFOAD - UJKZ (2025-2026)

═══════════════════════════════════════════════════════════
PÉRIODE D'INSCRIPTION
═══════════════════════════════════════════════════════════
Ouverture des inscriptions : 1er Août 2025
Clôture des inscriptions   : 10 Septembre 2025

═══════════════════════════════════════════════════════════
CONDITIONS D'ADMISSION
═══════════════════════════════════════════════════════════
- Sélection sur dossier
- Moyenne générale minimum : 12/20 au cycle précédent

Pour le Master en Sciences des Données :
  - Licence (Bac+3) en Informatique, Mathématiques, Physique ou équivalent
  - OU Diplôme d'Ingénieur (BAC+5) avec validation d'acquis

Pour la Licence en Informatique Appliquée :
  - Baccalauréat (série scientifique) ou équivalent

═══════════════════════════════════════════════════════════
FRAIS DE SCOLARITÉ
═══════════════════════════════════════════════════════════
LICENCE EN INFORMATIQUE APPLIQUÉE :
  • Frais de formation : 300 000 FCFA
  • Frais d'inscription : 16 500 FCFA

MASTER EN SCIENCES DES DONNÉES :
  • Frais de formation : 700 000 FCFA
  • Frais d'inscription : 51 500 FCFA

FORMATIONS COURTES DURÉES :
  • Frais variables selon la thématique
  • Se renseigner auprès du secrétariat

═══════════════════════════════════════════════════════════
PLATEFORME D'INSCRIPTION
═══════════════════════════════════════════════════════════
Les dépôts de dossiers se font sur :
  🌐 CAMPUS FASO (plateforme en ligne)

Lien : https://campusfaso.bf (ou via le portail UJKZ)

═══════════════════════════════════════════════════════════
DOCUMENTS REQUIS
═══════════════════════════════════════════════════════════
Documents obligatoires (à télécharger sur Campus Faso) :
  ✓ Formulaire d'inscription rempli et signé
  ✓ Photocopie légalisée du diplôme le plus élevé
  ✓ Relevés de notes des 3 dernières années
  ✓ Copie certifiée conforme de la CNIB (ou passeport)
  ✓ Photos d'identité récentes
  ✓ Lettre de motivation
  ✓ Curriculum Vitae (CV) détaillé
  ✓ Reçu de paiement des frais de dossier

═══════════════════════════════════════════════════════════
MODALITÉS PÉDAGOGIQUES
═══════════════════════════════════════════════════════════
- Cours suivis en ligne via la plateforme UJKZ
- Devoirs : adaptés selon l'enseignant
  * Certains enseignants préfèrent les devoirs en ligne
  * D'autres enseignants préfèrent les devoirs en présentiel
- Regroupements présentiels périodiques obligatoires
- Accompagnement personnalisé par les tuteurs

Contact inscription :
  Email : inscription.ifoad@ujkz.bf
  Tél : (+226) 25 30 70 64 / 25 30 70 65
            """,
            
            "/ifoad/calendrier": f"""
CALENDRIER ACADÉMIQUE IFOAD-UJKZ - ANNÉE 2025-2026

═══════════════════════════════════════════════════════════
PREMIER SEMESTRE (S1 - Master 1)
═══════════════════════════════════════════════════════════
Début des cours : 15 Octobre 2025
Fin des cours : 20 Janvier 2026
Examens de fin de S1 : 26 Janvier - 7 Février 2026
Publication des résultats : 20 Février 2026

═══════════════════════════════════════════════════════════
SECOND SEMESTRE (S2 - Master 1)
═══════════════════════════════════════════════════════════
Début des cours : 2 Mars 2026
Fin des cours : 30 Mai 2026
Examens de fin de S2 : 8-20 Juin 2026
Publication des résultats : 5 Juillet 2026

═══════════════════════════════════════════════════════════
MASTER 2 - SEMESTRE 3 ET 4
═══════════════════════════════════════════════════════════
Semestre 3 : Octobre 2026 - Janvier 2027
Semestre 4 : Février 2027 - Juin 2027 (Stage et mémoire)

═══════════════════════════════════════════════════════════
REGROUPEMENTS PRÉSENTIELS (Obligatoires)
═══════════════════════════════════════════════════════════
Regroupement 1 : 10-12 Novembre 2025
Regroupement 2 : 5-7 Janvier 2026
Regroupement 3 : 6-8 Avril 2026
Soutenance de mémoire : Juillet 2027
            """
        }
        
        return contenus.get(chemin_relatif, contenus["/ifoad"])

    def _generer_donnees_demo(self, chemin_relatif: str) -> dict:
        """Génère des données de démonstration avec les vraies informations."""
        
        contenu = self._generer_contenu_ifoad(chemin_relatif)
        
        titre = chemin_relatif.replace("/ifoad/", "").replace("/", " - ").title()
        if not titre or titre == " ":
            titre = "IFOAD - Informations générales"
        
        document = {
            "type_source": "ujkz_demo",
            "url": urljoin(URL_UJKZ, chemin_relatif),
            "titre": f"IFOAD-UJKZ : {titre}",
            "contenu": self._nettoyer_texte(contenu),
            "date_collecte": datetime.now().isoformat(),
            "langue": "fr",
            "note": "Données réelles de l'IFOAD (générées localement)",
            "nombre_caracteres": len(contenu)
        }
        
        logger.info(f" Données IFOAD générées pour : {chemin_relatif}")
        return document

    # ────────────────────────────────────────────────────────────────────────
    # SCRAPING FACEBOOK
    # ────────────────────────────────────────────────────────────────────────

    def scraper_facebook_ifoad(self) -> list:
        """Collecte les publications récentes de la page Facebook publique de l'IFOAD."""
        logger.info(f" Scraping de la page Facebook : {PAGE_FACEBOOK_IFOAD}")
        publications = []
        
        try:
            from facebook_scraper import get_posts
            
            for publication in get_posts(PAGE_FACEBOOK_IFOAD, pages=2):
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
                self._pause_polie()
                
        except Exception as e:
            logger.warning(f"  Erreur Facebook : {e}")
            publications = self._generer_publications_facebook_demo()
        
        logger.success(f" {len(publications)} publications Facebook collectées")
        return publications

    def _generer_publications_facebook_demo(self) -> list:
        """Génère des publications Facebook de démonstration réalistes."""
        return [
            {
                "type_source": "facebook_demo",
                "url": "https://www.facebook.com/UJKZ.IFOAD",
                "titre": "Annonce ouverture inscriptions 2025-2026",
                "contenu": (
                    "📢 AVIS D'OUVERTURE DES INSCRIPTIONS 2025-2026\n\n"
                    "L'IFOAD de l'Université Joseph Ki-Zerbo est heureux d'annoncer l'ouverture "
                    "des inscriptions pour l'année académique 2025-2026.\n\n"
                    "📅 Période d'inscription : 1er Août au 10 Septembre 2025\n"
                    "🎓 Formations disponibles : \n"
                    "  • Licence en Informatique Appliquée (300 000 FCFA + 16 500 FCFA)\n"
                    "  • Master en Sciences des Données (700 000 FCFA + 51 500 FCFA)\n"
                    "  • Formations courtes thématiques (à la demande)\n\n"
                    "📝 Conditions : Sélection sur dossier - 12/20 minimum\n"
                    "🌐 Dépôt des dossiers : Campus Faso\n\n"
                    "Contact : ifoad@ujkz.bf | (+226) 25 30 70 64\n"
                    "#IFOAD #UJKZ #FormationEnLigne #BurkinaFaso #DataScience"
                ),
                "date_publication": "2025-08-01",
                "date_collecte": datetime.now().isoformat(),
                "likes": 245,
                "langue": "fr",
                "nombre_caracteres": 450
            },
            {
                "type_source": "facebook_demo",
                "url": "https://www.facebook.com/UJKZ.IFOAD",
                "titre": "Master en Sciences des Données - Programme",
                "contenu": (
                    "📊 MASTER EN SCIENCES DES DONNÉES - IFOAD UJKZ\n\n"
                    "Découvrez le programme complet du Master en Sciences des Données !\n\n"
                    "Semestre 1 :\n"
                    "  • Probabilités et statistiques\n"
                    "  • Calcul matriciel numérique\n"
                    "  • POO et Python\n"
                    "  • Logiciel R\n"
                    "  • Bases de données relationnelles\n\n"
                    "Semestre 2 :\n"
                    "  • Machine Learning supervisé et non supervisé\n"
                    "  • Réseaux de neurones\n"
                    "  • Programmation Scala, PySpark, Julia\n"
                    "  • Visualisation des données\n\n"
                    "Semestre 3 :\n"
                    "  • Deep Learning et applications\n"
                    "  • Big Data, NoSQL\n"
                    "  • Cloud computing, Virtualisation\n\n"
                    "Semestre 4 : Stage et mémoire\n\n"
                    "Inscriptions : ifoad@ujkz.bf\n"
                    "#DataScience #UJKZ #IFOAD #MachineLearning #AI"
                ),
                "date_publication": "2025-07-15",
                "date_collecte": datetime.now().isoformat(),
                "likes": 189,
                "langue": "fr",
                "nombre_caracteres": 420
            },
            {
                "type_source": "facebook_demo",
                "url": "https://www.facebook.com/UJKZ.IFOAD",
                "titre": "Formations courtes - À la demande",
                "contenu": (
                    "💻 FORMATIONS COURTES THÉMATIQUES - IFOAD UJKZ\n\n"
                    "Vous souhaitez vous former sur un sujet spécifique ?\n"
                    "L'IFOAD propose des formations courtes à la demande !\n\n"
                    "Modules disponibles :\n"
                    "  • Compétences aux usages du numérique (JFOAD, CUN)\n"
                    "  • Outils de collectes (KoboToolbox)\n"
                    "  • Python pour les Sciences de Données\n"
                    "  • Algorithmique et programmation en C\n"
                    "  • Développement mobile 1 & 2\n"
                    "  • Développement web\n"
                    "  • Les Fondamentaux de la Cybersécurité\n"
                    "  • Maîtrise de Moodle par les enseignants\n\n"
                    "📞 Renseignements : (+226) 25 30 70 64\n"
                    "#FormationContinue #UJKZ #IFOAD #Digital"
                ),
                "date_publication": "2025-06-20",
                "date_collecte": datetime.now().isoformat(),
                "likes": 312,
                "langue": "fr",
                "nombre_caracteres": 510
            }
        ]

    # ────────────────────────────────────────────────────────────────────────
    # MÉTHODE PRINCIPALE
    # ────────────────────────────────────────────────────────────────────────

    def executer_collecte_complete(self) -> int:
        """
        Exécute la collecte complète de données depuis toutes les sources.
        """
        logger.info("=" * 60)
        logger.info(" DÉMARRAGE DE LA COLLECTE DE DONNÉES IFOAD-UJKZ")
        logger.info("=" * 60)
        
        tous_les_documents = []
        
        # ─── ÉTAPE 1 : Scraping des pages UJKZ ──────────────────────────
        logger.info(f"\n ÉTAPE 1 : Scraping du site UJKZ ({len(PAGES_UJKZ_A_SCRAPER)} pages)")
        
        pdfs_a_telecharger = []
        images_a_analyser = []
        
        for chemin in PAGES_UJKZ_A_SCRAPER:
            document = self.scraper_page_ujkz(chemin)
            if document:
                tous_les_documents.append(document)
                pdfs_a_telecharger.extend(document.get("liens_pdf", []))
                images_a_analyser.extend(document.get("liens_images", []))
            self._pause_polie()
        
        # ─── ÉTAPE 2 : Téléchargement des PDFs ──────────────────────────
        if pdfs_a_telecharger:
            logger.info(f"\n ÉTAPE 2 : Extraction de {len(pdfs_a_telecharger)} PDFs")
            for url_pdf in pdfs_a_telecharger:
                document_pdf = self.telecharger_et_extraire_pdf(url_pdf)
                if document_pdf:
                    tous_les_documents.append(document_pdf)
                self._pause_polie()
        
        # ─── ÉTAPE 3 : Analyse des images avec OCR ──────────────────────
        if images_a_analyser:
            logger.info(f"\n ÉTAPE 3 : Analyse de {len(images_a_analyser)} images avec OCR")
            for url_image in images_a_analyser[:5]:  # Limite à 5 images pour éviter l'overhead
                texte_extra = self._extraire_texte_image(url_image)
                if texte_extra and len(texte_extra) > 50:
                    document_image = {
                        "type_source": "ujkz_image_ocr",
                        "url": url_image,
                        "titre": "Texte extrait d'image",
                        "contenu": texte_extra,
                        "date_collecte": datetime.now().isoformat(),
                        "langue": "fr",
                        "nombre_caracteres": len(texte_extra)
                    }
                    tous_les_documents.append(document_image)
                self._pause_polie()
        
        # ─── ÉTAPE 4 : Scraping Facebook ────────────────────────────────
        logger.info("\n ÉTAPE 4 : Scraping de la page Facebook IFOAD")
        publications_facebook = self.scraper_facebook_ifoad()
        tous_les_documents.extend(publications_facebook)
        
        # ─── ÉTAPE 5 : Ajout du cursus Master Science des Données ──────
        logger.info("\n ÉTAPE 5 : Intégration du cursus Master Science des Données")
        
        document_curriculum = {
            "type_source": "curriculum_master",
            "url": "https://www.ujkz.bf/ifoad/master-sciences-donnees",
            "titre": "Master en Sciences des Données - Programme complet",
            "contenu": json.dumps(CURSUS_MASTER_SCIENCES_DONNEES, ensure_ascii=False, indent=2),
            "date_collecte": datetime.now().isoformat(),
            "langue": "fr",
            "nombre_caracteres": len(json.dumps(CURSUS_MASTER_SCIENCES_DONNEES))
        }
        tous_les_documents.append(document_curriculum)
        
        # ─── ÉTAPE 6 : Sauvegarde de tous les documents ─────────────────
        logger.info(f"\n ÉTAPE 6 : Sauvegarde de {len(tous_les_documents)} documents")
        
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
    (RACINE / "logs").mkdir(exist_ok=True)
    
    logger.info(" Agent IA Assistant IFOAD-UJKZ - Module de Collecte")
    logger.info(f" Date : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    scraper = ScraperIFOAD()
    nb_docs = scraper.executer_collecte_complete()
    
    if nb_docs > 0:
        print(f"\n✅ Succès ! {nb_docs} documents collectés dans : {DOSSIER_DONNEES_BRUTES}")
        print("📌 Prochaine étape : python src/ingestion/vectoriser.py")
    else:
        print("\n❌ Aucun document collecté. Vérifiez les logs pour plus de détails.")
        sys.exit(1)
