"""
============================================================
INTERFACE UTILISATEUR - Application Streamlit Agent IFOAD
============================================================
Version corrigée v2 - Correction AttributeError tuple
============================================================
"""

import sys
from pathlib import Path
from datetime import datetime

import streamlit as st

# ─── Ajout du chemin racine ─────────────────────────────────────────────────
RACINE = Path(__file__).parent.parent.parent
sys.path.insert(0, str(RACINE))

from config.parametres import (
    CLE_API_GROQ,
    MODELE_LLM,
    NOMBRE_DOCS_FINAL,
)

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURATION PAGE (doit être le 1er appel Streamlit)
# ════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Assistant IFOAD-UJKZ",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════════════════════════════════════════
# INITIALISATION SESSION
# ════════════════════════════════════════════════════════════════════════════

def initialiser_session():
    """Initialise les variables de session si elles n'existent pas."""
    if "messages_chat" not in st.session_state:
        st.session_state.messages_chat = []
    if "agent_rag" not in st.session_state:
        st.session_state.agent_rag = None
    if "agent_charge" not in st.session_state:
        st.session_state.agent_charge = False
    if "erreur_chargement" not in st.session_state:
        st.session_state.erreur_chargement = ""
    if "nb_questions" not in st.session_state:
        st.session_state.nb_questions = 0
    if "question_suggeree" not in st.session_state:
        st.session_state.question_suggeree = ""


# ════════════════════════════════════════════════════════════════════════════
# CHARGEMENT AGENT
# ════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def charger_agent():
    """
    Charge l'agent RAG Hybride une seule fois grâce au cache Streamlit.

    CORRECTION : ne retourne JAMAIS un tuple.
    Lève une exception en cas d'erreur → capturée proprement dans main().
    """
    from src.agent.pipeline_rag import AgentRAGHybride
    return AgentRAGHybride()


# ════════════════════════════════════════════════════════════════════════════
# VÉRIFICATION CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

def verifier_configuration() -> bool:
    """Vérifie que la clé API et la base vectorielle sont prêtes."""
    ok = True

    if not CLE_API_GROQ or CLE_API_GROQ == "votre_cle_groq_ici":
        st.error(
            "🔑 **Clé API Groq manquante !**\n\n"
            "1. Allez sur [console.groq.com](https://console.groq.com)\n"
            "2. Créez un compte gratuit (sans carte bancaire)\n"
            "3. API Keys → Create API Key → copiez la clé `gsk_...`\n"
            "4. Ouvrez `config/.env` et remplacez `votre_cle_groq_ici` par votre clé\n"
            "5. Relancez l'application"
        )
        ok = False

    chemin_base = RACINE / "data" / "vectorielle"
    if chemin_base.exists():
        base_vide = not any(chemin_base.iterdir())
    else:
        base_vide = True

    if base_vide:
        st.error(
            "🗄️ **Base vectorielle vide !**\n\n"
            "Lancez ces commandes dans l'ordre :\n"
            "```\npython src/collecte/scraper_ujkz.py\n"
            "python src/ingestion/vectoriser.py\n```"
        )
        ok = False

    return ok


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════

def afficher_sidebar():
    """Panneau latéral : statut, questions suggérées, actions."""
    with st.sidebar:
        st.title("🎓 IFOAD-UJKZ")
        st.caption("Assistant IA Intelligent")
        st.divider()

        # ─── Statut ──────────────────────────────────────────────────────
        st.subheader("⚙️ Statut")
        if st.session_state.agent_charge:
            st.success("✅ Agent opérationnel")
            st.caption(f"Modèle : `{MODELE_LLM}`")
            st.caption(f"Docs/réponse : `{NOMBRE_DOCS_FINAL}`")
        elif st.session_state.erreur_chargement:
            st.error("❌ Erreur de chargement")
            with st.expander("Voir l'erreur"):
                st.code(st.session_state.erreur_chargement)
        else:
            st.warning("⏳ En cours de chargement...")

        st.divider()

        # ─── Questions suggérées ──────────────────────────────────────────
        st.subheader("💡 Questions fréquentes")

        questions = [
            "📚 Quelles formations propose l'IFOAD ?",
            "📝 Comment s'inscrire à l'IFOAD ?",
            "📅 Quelles sont les dates des examens ?",
            "💰 Quels sont les frais de scolarité ?",
            "📋 Quels documents pour le dossier ?",
            "📞 Comment contacter l'IFOAD ?",
            "🎓 Quels sont les débouchés du Master ?",
            "🗓️ Quand commencent les cours ?",
        ]

        for idx, q in enumerate(questions):
            if st.button(q, key=f"sidebar_q_{idx}", use_container_width=True):
                st.session_state.question_suggeree = q
                st.rerun()

        st.divider()

        # ─── Stats ───────────────────────────────────────────────────────
        st.subheader("📊 Session")
        st.metric("Questions posées", st.session_state.nb_questions)

        st.divider()

        # ─── Actions ─────────────────────────────────────────────────────
        if st.button("🗑️ Nouvelle conversation", use_container_width=True):
            st.session_state.messages_chat = []
            st.session_state.nb_questions = 0
            if st.session_state.agent_rag is not None:
                st.session_state.agent_rag.reinitialiser_historique()
            st.rerun()

        st.divider()
        st.caption(
            "Projet Data Science 2026\n"
            "Master 1 IFOAD — UJKZ\n"
            "Dr Delwende D. A. Sawadogo"
        )


# ════════════════════════════════════════════════════════════════════════════
# AFFICHAGE RÉPONSE ET SOURCES
# ════════════════════════════════════════════════════════════════════════════

def afficher_badge_confiance(confiance: float):
    """Affiche un indicateur coloré selon le score de confiance."""
    if confiance >= 0.7:
        st.success(f"🟢 Confiance élevée : {confiance:.0%}")
    elif confiance >= 0.4:
        st.warning(f"🟡 Confiance moyenne : {confiance:.0%}")
    else:
        st.error(f"🔴 Confiance faible : {confiance:.0%}")


def afficher_sources(sources: list):
    """Affiche les sources utilisées dans un expander."""
    if not sources:
        return
    with st.expander(f"📚 Sources utilisées ({len(sources)} documents)"):
        for idx, src in enumerate(sources, 1):
            icones = {
                "ujkz_web": "🌐", "ujkz_pdf": "📄",
                "ujkz_demo": "📋", "facebook_ifoad": "📱",
                "facebook_demo": "📱", "curriculum_master": "🎓",
            }
            icone = icones.get(src.get("type", ""), "📄")
            st.markdown(
                f"**{icone} [{idx}] {src.get('titre', 'Sans titre')}**  \n"
                f"Pertinence : `{src.get('pertinence', '?')}` · "
                f"Type : `{src.get('type', '?')}`  \n"
                f"*\"{src.get('extrait', '')}\"*"
            )
            url = src.get("url", "")
            if url and url.startswith("http"):
                st.markdown(f"[🔗 Voir la source]({url})")
            st.divider()


# ════════════════════════════════════════════════════════════════════════════
# TRAITEMENT D'UNE QUESTION
# ════════════════════════════════════════════════════════════════════════════

def traiter_question(question: str, agent):
    """
    Envoie la question à l'agent et affiche la réponse.
    CORRECTION : vérifie que agent est valide avant d'appeler .repondre()
    """
    # ─── Sécurité : vérifie que l'agent est un objet valide ─────────────
    if agent is None or isinstance(agent, tuple):
        st.error(
            "❌ L'agent IA n'est pas correctement chargé.\n\n"
            "Vérifiez les erreurs dans la sidebar et relancez l'application."
        )
        return

    # ─── Message utilisateur ─────────────────────────────────────────────
    with st.chat_message("user", avatar="👤"):
        st.markdown(question)

    # ─── Réponse de l'agent ──────────────────────────────────────────────
    with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("🔍 Recherche dans la base de connaissances IFOAD..."):
            try:
                resultat = agent.repondre(question)
            except Exception as e:
                st.error(f"❌ Erreur lors de la génération de la réponse : {e}")
                return

        # Affichage de la réponse
        st.markdown(resultat["reponse"])

        # Badge de confiance
        afficher_badge_confiance(resultat["confiance"])

        # Avertissement si confiance trop faible
        if not resultat["peut_repondre"]:
            st.info(
                "ℹ️ Information non trouvée dans la base. "
                "Contactez l'IFOAD directement :\n"
                "- 📧 ifoad@ujkz.bf\n"
                "- 📞 (+226) 25 30 70 64"
            )

        # Sources
        afficher_sources(resultat["sources"])

    # ─── Sauvegarde dans l'historique ────────────────────────────────────
    st.session_state.messages_chat.append({
        "role": "user", "contenu": question
    })
    st.session_state.messages_chat.append({
        "role": "assistant",
        "contenu": resultat["reponse"],
        "sources": resultat["sources"],
        "confiance": resultat["confiance"],
        "peut_repondre": resultat["peut_repondre"],
    })
    st.session_state.nb_questions += 1


def afficher_historique():
    """Réaffiche tous les messages précédents de la conversation."""
    for msg in st.session_state.messages_chat:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg["contenu"])
        else:
            with st.chat_message("assistant", avatar="🎓"):
                st.markdown(msg["contenu"])
                afficher_badge_confiance(msg.get("confiance", 0))
                if not msg.get("peut_repondre", True):
                    st.info(
                        "ℹ️ Contactez l'IFOAD : ifoad@ujkz.bf | (+226) 25 30 70 64"
                    )
                afficher_sources(msg.get("sources", []))


# ════════════════════════════════════════════════════════════════════════════
# APPLICATION PRINCIPALE
# ════════════════════════════════════════════════════════════════════════════

def main():
    """Point d'entrée principal de l'application Streamlit."""

    initialiser_session()

    # ─── En-tête ─────────────────────────────────────────────────────────
    st.title("🎓 Assistant IFOAD-UJKZ")
    st.caption(
        "Agent IA intelligent · Université Joseph Ki-Zerbo · Burkina Faso  \n"
        "Architecture : RAG Hybride (HyDE + Dense + BM25 + RRF + Re-ranking)"
    )
    st.divider()

    # ─── Sidebar ─────────────────────────────────────────────────────────
    afficher_sidebar()

    # ─── Vérification config ──────────────────────────────────────────────
    if not verifier_configuration():
        st.stop()

    # ─── Chargement de l'agent ────────────────────────────────────────────
    if not st.session_state.agent_charge:
        with st.spinner("⏳ Chargement de l'agent IA... (1-2 min au 1er lancement)"):
            try:
                # CORRECTION : charger_agent() lève une exception si erreur,
                # jamais un tuple → plus d'AttributeError
                agent = charger_agent()

                if agent is None or isinstance(agent, tuple):
                    raise ValueError(
                        "Chargement invalide. Vérifiez la base vectorielle."
                    )

                st.session_state.agent_rag = agent
                st.session_state.agent_charge = True
                st.session_state.erreur_chargement = ""

            except Exception as e:
                st.session_state.erreur_chargement = str(e)
                st.error(
                    f"❌ **Impossible de charger l'agent IA**\n\n"
                    f"Erreur : `{e}`\n\n"
                    f"**Solutions :**\n"
                    f"1. Vérifiez `config/.env` → clé Groq correcte ?\n"
                    f"2. Relancez : `python src/ingestion/vectoriser.py`\n"
                    f"3. Redémarrez Streamlit"
                )
                st.stop()

        st.rerun()

    agent = st.session_state.agent_rag

    # ─── Message de bienvenue ─────────────────────────────────────────────
    if not st.session_state.messages_chat:
        with st.chat_message("assistant", avatar="🎓"):
            st.markdown("""
👋 **Bonjour ! Je suis votre Assistant IA de l'IFOAD-UJKZ.**

Je peux vous aider avec :
- 📚 Les **formations disponibles** (Master 1 IFOAD, Licence MI...)
- 📝 Les **modalités d'inscription** et documents requis
- 📅 Le **calendrier académique** (cours, examens, regroupements)
- 💰 Les **frais de scolarité** et modalités de paiement
- 📞 Les **contacts** du secrétariat IFOAD

**Comment puis-je vous aider aujourd'hui ?**
            """)
    else:
        afficher_historique()

    # ─── Traitement question suggérée ─────────────────────────────────────
    if st.session_state.question_suggeree:
        q = st.session_state.question_suggeree
        st.session_state.question_suggeree = ""
        traiter_question(q, agent)
        st.rerun()

    # ─── Zone de saisie ──────────────────────────────────────────────────
    question = st.chat_input(
        "Posez votre question sur l'IFOAD-UJKZ... (ex: Comment s'inscrire ?)"
    )
    if question:
        traiter_question(question.strip(), agent)
        st.rerun()


if __name__ == "__main__":
    main()
