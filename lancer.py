"""
============================================================
SCRIPT DE LANCEMENT GRAPHIQUE — Agent IFOAD-UJKZ
============================================================
Ce script guide l'utilisateur à travers toutes les étapes
du projet avec une interface graphique.

USAGE :
    python lancer.py              → Interface graphique
============================================================
"""

import sys
import os
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime

# ─── Racine du projet ───────────────────────────────────────────────────────
RACINE = Path(__file__).parent

# ─── Fonctions originales (inchangées) ─────────────────────────────────────
def afficher_banniere():
    """Affiche la bannière ASCII art du projet."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║             AGENT IA ASSISTANT IFOAD-UJKZ                    ║
║         Projet Data Science 2026 — Master 1 IFOAD            ║
║         Université Joseph Ki-Zerbo, Burkina Faso             ║
╠══════════════════════════════════════════════════════════════╣
║  Architecture : RAG Hybride (HyDE + Dense + BM25 + RRF)      ║
║  Outils : Groq API + ChromaDB + sentence-transformers        ║
╚══════════════════════════════════════════════════════════════╝
    """)


def verifier_configuration() -> bool:
    """
    Vérifie que les prérequis sont installés et configurés.

    Returns:
        True si tout est OK, False sinon
    """
    print("\n🔍 Vérification de la configuration...")
    tout_ok = True

    # ─── Vérification Python ─────────────────────────────────────────────
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f" Python 3.10+ requis (version actuelle : {version.major}.{version.minor})")
        tout_ok = False
    else:
        print(f" Python {version.major}.{version.minor} détecté")

    # ─── Vérification du fichier .env ────────────────────────────────────
    chemin_env = RACINE / "config" / ".env"
    if not chemin_env.exists():
        print(" Fichier config/.env manquant !")
        print("   → Exécutez : cp config/.env.exemple config/.env")
        print("   → Puis ajoutez votre clé Groq dans config/.env")
        tout_ok = False
    else:
        # Vérifie si la clé Groq est renseignée
        with open(chemin_env) as f:
            contenu = f.read()
        if "votre_cle_groq_ici" in contenu or "CLE_API_GROQ=" not in contenu:
            print(" Clé Groq non configurée dans config/.env")
            print("   → Obtenez votre clé gratuite sur : https://console.groq.com")
            tout_ok = False
        else:
            print(" Fichier .env configuré")

    # ─── Vérification des dépendances ─────────────────────────────────────
    try:
        import chromadb
        import sentence_transformers
        import groq
        import streamlit
        import rank_bm25
        print(" Dépendances Python installées")
    except ImportError as e:
        print(f" Dépendance manquante : {e}")
        print("   → Exécutez : pip install -r requirements.txt")
        tout_ok = False

    return tout_ok


def etape_1_collecter():
    """Lance la collecte des données depuis UJKZ et Facebook."""
    print("\n" + "="*55)
    print(" ÉTAPE 1 : COLLECTE DES DONNÉES")
    print("="*55)
    print("Sources : Site UJKZ + Page Facebook IFOAD + PDFs")
    print("Durée estimée : 2-5 minutes\n")

    script = RACINE / "src" / "collecte" / "scraper_ujkz.py"
    resultat = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(RACINE)
    )

    if resultat.returncode == 0:
        print("\n Étape 1 terminée avec succès !")
        return True
    else:
        print("\n Erreur lors de la collecte. Vérifiez les logs.")
        return False


def etape_2_vectoriser():
    """Lance la vectorisation des données collectées."""
    print("\n" + "="*55)
    print(" ÉTAPE 2 : VECTORISATION DES DONNÉES")
    print("="*55)
    print("Modèle : paraphrase-multilingual-mpnet-base-v2")
    print("Base : ChromaDB (locale)")
    print("Durée estimée : 3-10 minutes (téléchargement du modèle au 1er lancement)\n")

    # Vérification que des données brutes existent
    dossier_brut = RACINE / "data" / "brut"
    if not dossier_brut.exists() or not list(dossier_brut.glob("*.json")):
        print(" Aucune donnée brute trouvée !")
        print("   → Lancez d'abord l'Étape 1 (collecte)")
        return False

    script = RACINE / "src" / "ingestion" / "vectoriser.py"
    resultat = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(RACINE)
    )

    if resultat.returncode == 0:
        print("\n Étape 2 terminée avec succès !")
        return True
    else:
        print("\n Erreur lors de la vectorisation. Vérifiez les logs.")
        return False


def etape_3_interface():
    """Lance l'interface Streamlit."""
    print("\n" + "="*55)
    print(" ÉTAPE 3 : LANCEMENT DE L'INTERFACE")
    print("="*55)
    print("L'interface va s'ouvrir dans votre navigateur...")
    print("Arrêtez avec CTRL+C\n")

    script = RACINE / "src" / "interface" / "application.py"
    # CORRECTION : utilise "python -m streamlit" au lieu de "streamlit"
    # pour éviter l'erreur CommandNotFoundException sur Windows
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(script),
         "--server.port", "8501",
         "--browser.gatherUsageStats", "false"],
        cwd=str(RACINE)
    )


def etape_4_evaluer():
    """Lance l'évaluation du système RAG."""
    print("\n" + "="*55)
    print(" ÉTAPE 4 : ÉVALUATION DU SYSTÈME RAG")
    print("="*55)
    print("Tests : Pertinence + Anti-hallucination + Hors-domaine")
    print("Durée estimée : 5-15 minutes\n")

    script = RACINE / "tests" / "evaluer_rag.py"
    subprocess.run(
        [sys.executable, str(script)],
        cwd=str(RACINE)
    )


# ─── Interface Graphique ────────────────────────────────────────────────────

class InterfaceGraphique:
    """Interface graphique avec couleurs IFOAD."""

    # ─── Couleurs IFOAD ──────────────────────────────────────────────────
    COULEURS = {
        "vert_fonce": "#1B5E20",
        "vert_principal": "#2E7D32",
        "vert_moyen": "#388E3C",
        "vert_clair": "#A5D6A7",
        "vert_tres_clair": "#E8F5E9",
        "vert_texte": "#1B5E20",
        "blanc": "#FFFFFF",
        "gris_clair": "#F5F7FA",
        "gris_texte": "#546e7a",
        "vert_succes": "#43A047",
        "vert_info": "#2E7D32",
        "orange_warning": "#F57C00",
        "rouge_erreur": "#C62828",
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Agent IA Assistant IFOAD-UJKZ - Lanceur")
        self.root.geometry("850x700")
        self.root.resizable(True, True)

        # Configurer le style avec les couleurs IFOAD
        self.root.configure(bg=self.COULEURS["vert_tres_clair"])

        # Variable pour l'état
        self.processus_en_cours = False

        self.construire_interface()
        self.afficher_bienvenue()

    def construire_interface(self):
        """Construit l'interface graphique."""

        # ─── En-tête ──────────────────────────────────────────────────────
        cadre_entete = tk.Frame(
            self.root,
            bg=self.COULEURS["vert_fonce"],
            pady=20,
            padx=20
        )
        cadre_entete.pack(fill=tk.X)

        # Logo/icône
        tk.Label(
            cadre_entete,
            text="🤖",
            font=('Arial', 36),
            bg=self.COULEURS["vert_fonce"]
        ).pack()

        tk.Label(
            cadre_entete,
            text="AGENT IA ASSISTANT IFOAD-UJKZ",
            font=('Arial', 18, 'bold'),
            bg=self.COULEURS["vert_fonce"],
            fg=self.COULEURS["blanc"]
        ).pack()

        tk.Label(
            cadre_entete,
            text="Projet Data Science 2026 — Master 1 IFOAD",
            font=('Arial', 11),
            bg=self.COULEURS["vert_fonce"],
            fg=self.COULEURS["vert_clair"]
        ).pack()

        tk.Label(
            cadre_entete,
            text="Université Joseph Ki-Zerbo, Burkina Faso",
            font=('Arial', 10),
            bg=self.COULEURS["vert_fonce"],
            fg=self.COULEURS["vert_clair"]
        ).pack()

        # ─── Zone d'information ──────────────────────────────────────────
        cadre_info = tk.Frame(
            self.root,
            bg=self.COULEURS["vert_tres_clair"],
            padx=20,
            pady=10
        )
        cadre_info.pack(fill=tk.X)

        self.message_info = tk.Label(
            cadre_info,
            text="🌿 Choisissez une option ci-dessous pour commencer",
            font=('Arial', 11),
            bg=self.COULEURS["vert_tres_clair"],
            fg=self.COULEURS["vert_principal"],
            wraplength=750
        )
        self.message_info.pack()

        # ─── Menu des options ────────────────────────────────────────────
        cadre_menu = tk.Frame(
            self.root,
            bg=self.COULEURS["vert_tres_clair"],
            padx=30,
            pady=20
        )
        cadre_menu.pack(fill=tk.BOTH, expand=True)

        # Titre du menu
        tk.Label(
            cadre_menu,
            text="📋 QUE VOULEZ-VOUS FAIRE ?",
            font=('Arial', 15, 'bold'),
            bg=self.COULEURS["vert_tres_clair"],
            fg=self.COULEURS["vert_fonce"]
        ).pack(pady=(0, 20))

        # Grille des options
        frame_options = tk.Frame(
            cadre_menu,
            bg=self.COULEURS["vert_tres_clair"]
        )
        frame_options.pack()

        # Option 1 - Collecte
        btn1 = self.creer_option(
            frame_options,
            "1",
            "📥 Collecter les données",
            "Sources : Site UJKZ + Facebook + PDFs",
            self.COULEURS["vert_principal"],
            self.lancer_collecte
        )
        btn1.pack(pady=5, fill=tk.X, padx=10)

        # Option 2 - Vectorisation
        btn2 = self.creer_option(
            frame_options,
            "2",
            "🧠 Vectoriser les données",
            "Modèle : paraphrase-multilingual-mpnet-base-v2 | Base : ChromaDB",
            self.COULEURS["vert_moyen"],
            self.lancer_vectorisation
        )
        btn2.pack(pady=5, fill=tk.X, padx=10)

        # Option 3 - Interface
        btn3 = self.creer_option(
            frame_options,
            "3",
            "🌐 Lancer l'interface web",
            "Ouvrir Streamlit dans le navigateur",
            "#00897B",  # Vert-bleu
            self.lancer_interface
        )
        btn3.pack(pady=5, fill=tk.X, padx=10)

        # Option 4 - Évaluation
        btn4 = self.creer_option(
            frame_options,
            "4",
            "📊 Évaluer le système RAG",
            "Tests : Pertinence + Anti-hallucination + Hors-domaine",
            "#00695C",  # Vert foncé
            self.lancer_evaluation
        )
        btn4.pack(pady=5, fill=tk.X, padx=10)

        # Option 5 - Tout faire
        btn5 = self.creer_option(
            frame_options,
            "5",
            "⚡ Tout faire en séquence",
            "Exécute : 1 → 2 → 3 (Collecte + Vectorisation + Interface)",
            self.COULEURS["rouge_erreur"],
            self.lancer_tout
        )
        btn5.pack(pady=5, fill=tk.X, padx=10)

        # Option 6 - Vérification
        btn6 = self.creer_option(
            frame_options,
            "6",
            "🔍 Vérifier la configuration",
            "Vérifier Python, .env et dépendances",
            "#455A64",  # Gris-vert
            self.verifier_configuration
        )
        btn6.pack(pady=5, fill=tk.X, padx=10)

        # Option Quitter
        btn_quitter = tk.Button(
            cadre_menu,
            text="❌ Quitter",
            font=('Arial', 11, 'bold'),
            bg="#C62828",
            fg=self.COULEURS["blanc"],
            activebackground="#B71C1C",
            activeforeground=self.COULEURS["blanc"],
            relief=tk.RAISED,
            bd=2,
            padx=20,
            pady=10,
            cursor='hand2',
            command=self.quitter
        )
        btn_quitter.pack(pady=(20, 0))

        # ─── Zone de logs ────────────────────────────────────────────────
        cadre_logs = tk.LabelFrame(
            self.root,
            text="📋 Journal des opérations",
            font=('Arial', 10, 'bold'),
            bg=self.COULEURS["vert_tres_clair"],
            fg=self.COULEURS["vert_fonce"],
            padx=10,
            pady=10
        )
        cadre_logs.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.logs = scrolledtext.ScrolledText(
            cadre_logs,
            height=10,
            font=('Consolas', 9),
            bg='#1B2A1B',  # Vert très foncé pour le terminal
            fg='#A5D6A7',
            wrap=tk.WORD,
            insertbackground='#A5D6A7'
        )
        self.logs.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ─── Barre de status ─────────────────────────────────────────────
        self.status_bar = tk.Label(
            self.root,
            text="🌿 Prêt",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            bg=self.COULEURS["vert_tres_clair"],
            fg=self.COULEURS["vert_fonce"],
            font=('Arial', 9)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # ─── Barre de progression ────────────────────────────────────────
        self.progression = ttk.Progressbar(
            self.root,
            mode='indeterminate',
            length=800,
            style="green.Horizontal.TProgressbar"
        )
        # Non packée par défaut

        # Configurer le style de la barre de progression
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            "green.Horizontal.TProgressbar",
            background=self.COULEURS["vert_principal"],
            troughcolor=self.COULEURS["vert_tres_clair"],
            bordercolor=self.COULEURS["vert_clair"],
            lightcolor=self.COULEURS["vert_clair"],
            darkcolor=self.COULEURS["vert_fonce"]
        )

    def creer_option(self, parent, numero, titre, description, couleur, commande):
        """Crée un bouton d'option avec description."""
        frame = tk.Frame(
            parent,
            bg=self.COULEURS["blanc"],
            relief=tk.RAISED,
            bd=2,
            highlightthickness=1,
            highlightcolor=self.COULEURS["vert_clair"]
        )

        # Contenu du bouton
        bouton = tk.Button(
            frame,
            text=f"{numero}. {titre}",
            font=('Arial', 11, 'bold'),
            bg=couleur,
            fg=self.COULEURS["blanc"],
            activebackground=couleur,
            activeforeground=self.COULEURS["blanc"],
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor='hand2',
            command=commande,
            anchor='w'
        )
        bouton.pack(fill=tk.X)

        # Description
        desc = tk.Label(
            frame,
            text=f"   {description}",
            font=('Arial', 9),
            bg=self.COULEURS["blanc"],
            fg=self.COULEURS["gris_texte"],
            anchor='w'
        )
        desc.pack(fill=tk.X, padx=15, pady=(0, 5))

        return frame

    def log(self, message, niveau="INFO"):
        """Ajoute un message dans les logs avec couleurs."""
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Couleurs pour les logs
        couleurs = {
            "INFO": "#A5D6A7",
            "SUCCÈS": "#66BB6A",
            "ERREUR": "#EF5350",
            "AVERTISSEMENT": "#FFA726"
        }

        couleur = couleurs.get(niveau, "#A5D6A7")

        self.logs.insert(
            tk.END,
            f"[{timestamp}] {message}\n",
            (niveau,)
        )

        # Configuration des tags de couleur
        self.logs.tag_configure("INFO", foreground="#A5D6A7")
        self.logs.tag_configure("SUCCÈS", foreground="#66BB6A")
        self.logs.tag_configure("ERREUR", foreground="#EF5350")
        self.logs.tag_configure("AVERTISSEMENT", foreground="#FFA726")

        self.logs.see(tk.END)
        self.root.update()

    def afficher_bienvenue(self):
        """Affiche le message de bienvenue."""
        self.log("=" * 60, "INFO")
        self.log("🌿 AGENT IA ASSISTANT IFOAD-UJKZ", "SUCCÈS")
        self.log("=" * 60, "INFO")
        self.log("Bienvenue ! Choisissez une option dans le menu.", "INFO")
        self.log("Architecture : RAG Hybride (HyDE + Dense + BM25 + RRF)", "INFO")
        self.log("Université Joseph Ki-Zerbo - Burkina Faso", "INFO")
        self.log("=" * 60, "INFO")

    def set_message_info(self, message):
        """Met à jour le message d'information."""
        self.message_info.config(text=message)

    def activer_attente(self, message="Traitement en cours..."):
        """Active le mode attente."""
        self.processus_en_cours = True
        self.set_message_info(f"⏳ {message}")
        self.progression.pack(fill=tk.X, padx=20)
        self.progression.start(10)
        self.status_bar.config(text=message, bg="#FFF3E0")

    def desactiver_attente(self, message="Opération terminée"):
        """Désactive le mode attente."""
        self.processus_en_cours = False
        self.progression.stop()
        self.progression.pack_forget()
        self.status_bar.config(text=message, bg=self.COULEURS["vert_tres_clair"])

    def quitter(self):
        """Quitte l'application."""
        if messagebox.askyesno("Quitter", "Voulez-vous vraiment quitter ?"):
            self.root.quit()
            self.root.destroy()

    # ─── Fonctions de lancement ────────────────────────────────────────────

    def verifier_configuration(self):
        """Lance la vérification de configuration."""
        if self.processus_en_cours:
            return

        self.log("\n" + "=" * 60, "INFO")
        self.log("🔍 VÉRIFICATION DE LA CONFIGURATION", "INFO")

        class LogRedirect:
            def __init__(self, app):
                self.app = app
            def write(self, text):
                if text.strip():
                    self.app.log(text.strip(), "INFO")
            def flush(self):
                pass

        old_stdout = sys.stdout
        sys.stdout = LogRedirect(self)

        try:
            verifier_configuration()
        finally:
            sys.stdout = old_stdout

        self.log("=" * 60, "INFO")
        messagebox.showinfo(
            "Vérification terminée",
            "🌿 La vérification de la configuration est terminée.\n"
            "Consultez les logs pour plus de détails."
        )

    def lancer_collecte(self):
        """Lance la collecte des données."""
        if self.processus_en_cours:
            return

        self.activer_attente("Collecte des données en cours (2-5 minutes)...")

        def collecter():
            class LogRedirect:
                def __init__(self, app):
                    self.app = app
                def write(self, text):
                    if text.strip():
                        self.app.log(text.strip(), "INFO")
                def flush(self):
                    pass

            old_stdout = sys.stdout
            sys.stdout = LogRedirect(self)

            try:
                resultat = etape_1_collecter()
                if resultat:
                    self.root.after(0, lambda: self.log("✅ Étape 1 terminée avec succès !", "SUCCÈS"))
                    self.root.after(0, lambda: self.set_message_info("✅ Collecte terminée avec succès"))
                else:
                    self.root.after(0, lambda: self.log("❌ Échec de la collecte", "ERREUR"))
                    self.root.after(0, lambda: self.set_message_info("❌ Échec de la collecte"))
            finally:
                sys.stdout = old_stdout
                self.root.after(0, lambda: self.desactiver_attente())

        threading.Thread(target=collecter, daemon=True).start()

    def lancer_vectorisation(self):
        """Lance la vectorisation."""
        if self.processus_en_cours:
            return

        self.activer_attente("Vectorisation en cours (3-10 minutes)...")

        def vectoriser():
            class LogRedirect:
                def __init__(self, app):
                    self.app = app
                def write(self, text):
                    if text.strip():
                        self.app.log(text.strip(), "INFO")
                def flush(self):
                    pass

            old_stdout = sys.stdout
            sys.stdout = LogRedirect(self)

            try:
                resultat = etape_2_vectoriser()
                if resultat:
                    self.root.after(0, lambda: self.log("✅ Étape 2 terminée avec succès !", "SUCCÈS"))
                    self.root.after(0, lambda: self.set_message_info("✅ Vectorisation terminée"))
                else:
                    self.root.after(0, lambda: self.log("❌ Échec de la vectorisation", "ERREUR"))
                    self.root.after(0, lambda: self.set_message_info("❌ Échec de la vectorisation"))
            finally:
                sys.stdout = old_stdout
                self.root.after(0, lambda: self.desactiver_attente())

        threading.Thread(target=vectoriser, daemon=True).start()

    def lancer_interface(self):
        """Lance l'interface Streamlit."""
        if self.processus_en_cours:
            return

        self.log("\n" + "=" * 60, "INFO")
        self.log("🌐 LANCEMENT DE L'INTERFACE", "INFO")

        messagebox.showinfo(
            "Lancement de l'interface",
            "🌿 L'interface Streamlit va se lancer.\n"
            "Elle s'ouvrira automatiquement dans votre navigateur.\n\n"
            "⚠️ Ne fermez pas cette fenêtre pendant l'utilisation.\n"
            "Pour arrêter l'interface, fermez le terminal Streamlit."
        )

        self.activer_attente("Interface en cours d'exécution...")

        def demarrer_interface():
            class LogRedirect:
                def __init__(self, app):
                    self.app = app
                def write(self, text):
                    if text.strip():
                        self.app.log(text.strip(), "INFO")
                def flush(self):
                    pass

            old_stdout = sys.stdout
            sys.stdout = LogRedirect(self)

            try:
                etape_3_interface()
                self.root.after(0, lambda: self.log("ℹ️ Interface arrêtée", "INFO"))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"❌ Erreur : {str(e)}", "ERREUR"))
            finally:
                sys.stdout = old_stdout
                self.root.after(0, lambda: self.desactiver_attente("Interface arrêtée"))

        threading.Thread(target=demarrer_interface, daemon=True).start()

    def lancer_evaluation(self):
        """Lance l'évaluation du système RAG."""
        if self.processus_en_cours:
            return

        self.activer_attente("Évaluation en cours (5-15 minutes)...")

        def evaluer():
            class LogRedirect:
                def __init__(self, app):
                    self.app = app
                def write(self, text):
                    if text.strip():
                        self.app.log(text.strip(), "INFO")
                def flush(self):
                    pass

            old_stdout = sys.stdout
            sys.stdout = LogRedirect(self)

            try:
                etape_4_evaluer()
                self.root.after(0, lambda: self.log("✅ Évaluation terminée", "SUCCÈS"))
                self.root.after(0, lambda: self.set_message_info("✅ Évaluation terminée"))
                self.root.after(0, lambda: messagebox.showinfo(
                    "Évaluation terminée",
                    "🌿 L'évaluation du système RAG est terminée.\n"
                    "Consultez les logs pour les résultats détaillés."
                ))
            except Exception as e:
                self.root.after(0, lambda: self.log(f"❌ Erreur : {str(e)}", "ERREUR"))
            finally:
                sys.stdout = old_stdout
                self.root.after(0, lambda: self.desactiver_attente())

        threading.Thread(target=evaluer, daemon=True).start()

    def lancer_tout(self):
        """Lance toutes les étapes en séquence."""
        if self.processus_en_cours:
            return

        if not messagebox.askyesno(
            "Tout faire",
            "⚠️ Cette opération va exécuter :\n\n"
            "1. Collecte des données (2-5 min)\n"
            "2. Vectorisation (3-10 min)\n"
            "3. Lancement de l'interface\n\n"
            "Durée totale estimée : 10-20 minutes.\n\n"
            "🌿 Voulez-vous continuer ?"
        ):
            return

        self.log("\n" + "=" * 60, "INFO")
        self.log("🚀 LANCEMENT DE TOUTES LES ÉTAPES", "SUCCÈS")
        self.log("=" * 60, "INFO")

        self.activer_attente("Exécution séquentielle en cours...")

        def tout_lancer():
            class LogRedirect:
                def __init__(self, app):
                    self.app = app
                def write(self, text):
                    if text.strip():
                        self.app.log(text.strip(), "INFO")
                def flush(self):
                    pass

            old_stdout = sys.stdout
            sys.stdout = LogRedirect(self)

            try:
                self.root.after(0, lambda: self.log("📥 ÉTAPE 1: Collecte des données", "INFO"))
                resultat1 = etape_1_collecter()

                if not resultat1:
                    self.root.after(0, lambda: self.log("❌ Échec de la collecte. Arrêt.", "ERREUR"))
                    self.root.after(0, lambda: self.set_message_info("❌ Échec - Arrêt"))
                    return

                self.root.after(0, lambda: self.log("🧠 ÉTAPE 2: Vectorisation", "INFO"))
                resultat2 = etape_2_vectoriser()

                if not resultat2:
                    self.root.after(0, lambda: self.log("❌ Échec de la vectorisation. Arrêt.", "ERREUR"))
                    self.root.after(0, lambda: self.set_message_info("❌ Échec - Arrêt"))
                    return

                self.root.after(0, lambda: self.log("🌐 ÉTAPE 3: Lancement de l'interface", "INFO"))
                self.root.after(0, lambda: self.set_message_info("✅ Préparation terminée - Lancement de l'interface"))
                self.root.after(0, lambda: self.desactiver_attente("Toutes les étapes sont terminées"))

                # Lancer l'interface
                self.root.after(1000, self.lancer_interface)

            except Exception as e:
                self.root.after(0, lambda: self.log(f"❌ Erreur : {str(e)}", "ERREUR"))
            finally:
                sys.stdout = old_stdout

        threading.Thread(target=tout_lancer, daemon=True).start()


# ─── Point d'entrée ────────────────────────────────────────────────────────

def main():
    """Point d'entrée principal."""
    root = tk.Tk()
    app = InterfaceGraphique(root)
    root.mainloop()


if __name__ == "__main__":
    main()