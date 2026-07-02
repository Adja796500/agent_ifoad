"""
============================================================
INTERFACE UTILISATEUR - Application Streamlit Agent IFOAD
============================================================
Version avec design joyeux et moderne
============================================================
"""

import sys
from pathlib import Path
from datetime import datetime
import random

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
    page_title="🎓 Assistant IFOAD-UJKZ",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS Personnalisé pour un design joyeux ──────────────────────────────
st.markdown("""
<style>
    /* Fond général */
    .stApp {
       background: linear-gradient(135deg, #BBDEFB 0%, #A5D6A7 100%);
        min-height: 100vh;
        position: relative;
    }
    
    /* Amélioration de la lisibilité avec une superposition légère */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(255, 255, 255, 0.08);
        z-index: 0;
        pointer-events: none;
    }
    
    /* Cartes de messages */
    .main > div {
        background: rgba(255,255,255,0.95);
        border-radius: 20px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        backdrop-filter: blur(10px);
    }
    
   /* En-tête avec couleurs IFOAD */
.custom-header {
    background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 50%, #388E3C 100%);
    padding: 25px 20px;
    border-radius: 20px;
    color: white !important;
    text-align: center;
    margin-bottom: 30px;
    box-shadow: 0 10px 30px rgba(46, 125, 50, 0.4);
    border: 2px solid rgba(165, 214, 167, 0.3);
}

.custom-header h1,
.custom-header p {
    color: white !important;
}
    
    /* Badges de confiance */
    .confiance-elevee {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        padding: 10px 20px;
        border-radius: 30px;
        display: inline-block;
        font-weight: bold;
        color: #2d3436;
    }
    
    .confiance-moyenne {
        background: linear-gradient(135deg, #ffeaa7 0%, #fdcb6e 100%);
        padding: 10px 20px;
        border-radius: 30px;
        display: inline-block;
        font-weight: bold;
        color: #2d3436;
    }
    
    .confiance-faible {
        background: linear-gradient(135deg, #fd79a8 0%, #e17055 100%);
        padding: 10px 20px;
        border-radius: 30px;
        display: inline-block;
        font-weight: bold;
        color: white;
    }
    
    /* Boutons personnalisés */
    .stButton > button {
        background: linear-gradient(135deg, #a8e6cf 0%, #dcedc1 100%);
        border: none;
        border-radius: 30px;
        padding: 10px 20px;
        font-weight: bold;
        color: #2d3436;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(168,230,207,0.4);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(168,230,207,0.6);
    }
    
    /* Sidebar personnalisée */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2d3436 0%, #636e72 100%);
    }
    
    section[data-testid="stSidebar"] * {
        color: white !important;
    }
    
    section[data-testid="stSidebar"] .stButton > button {
        background: linear-gradient(135deg, #fd79a8 0%, #e17055 100%);
        color: white !important;
    }
    
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: linear-gradient(135deg, #e17055 0%, #d63031 100%);
    }
    
    /* Zone de saisie */
    .stChatInputContainer {
        background: rgba(255,255,255,0.9);
        border-radius: 30px;
        padding: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    
    /* Messages */
    [data-testid="stChatMessage"] {
        background: white;
        border-radius: 15px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    
    [data-testid="stChatMessage"]:hover {
        box-shadow: 0 6px 25px rgba(0,0,0,0.1);
        transform: translateY(-2px);
        transition: all 0.3s ease;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: linear-gradient(135deg, #dfe6e9 0%, #b2bec3 100%);
        border-radius: 30px !important;
        font-weight: bold;
        color: #2d3436;
    }
    
    /* Métriques */
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        color: #fd79a8 !important;
    }
    
    /* Animations */
    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
        100% { transform: translateY(0px); }
    }
    
    .floating {
        animation: float 3s ease-in-out infinite;
    }
</style>
""", unsafe_allow_html=True)

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
    if "nb_questions" not in st.session_state:
        st.session_state.nb_questions = 0
    if "question_suggeree" not in st.session_state:
        st.session_state.question_suggeree = ""
    if "emojis" not in st.session_state:
        st.session_state.emojis = ["🌟", "✨", "🌈", "🎉", "💫", "🌸", "🌺", "🌻", "🌷", "🌹"]


# ════════════════════════════════════════════════════════════════════════════
# CHARGEMENT AGENT (mis en cache - chargé une seule fois)
# ════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def charger_agent():
    """
    Charge l'agent RAG Hybride une seule fois grâce au cache Streamlit.
    Les modèles lourds (embeddings, reranker) ne sont chargés qu'au 1er lancement.
    """
    try:
        from src.agent.pipeline_rag import AgentRAGHybride
        return AgentRAGHybride()
    except Exception as e:
        return None, str(e)


# ════════════════════════════════════════════════════════════════════════════
# VÉRIFICATION CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════

def verifier_configuration() -> bool:
    """Vérifie que la clé API et la base vectorielle sont prêtes."""
    ok = True

    if not CLE_API_GROQ or CLE_API_GROQ == "votre_cle_groq_ici":
        st.error(
            "🚀 **Clé API Groq manquante !**\n\n"
            "1️⃣ Allez sur [console.groq.com](https://console.groq.com)\n"
            "2️⃣ Créez un compte gratuit (sans carte bancaire)\n"
            "3️⃣ API Keys → Create API Key → copiez la clé `gsk_...`\n"
            "4️⃣ Ouvrez `config/.env` et remplacez `votre_cle_groq_ici` par votre clé\n"
            "5️⃣ Relancez l'application"
        )
        ok = False

    chemin_base = RACINE / "data" / "vectorielle"
    base_vide = not chemin_base.exists() or not any(chemin_base.iterdir()) if chemin_base.exists() else True
    if base_vide:
        st.warning(
            "🗄️ **Base vectorielle vide !**\n\n"
            "Lancez ces commandes dans l'ordre :\n"
            "```\npython src/collecte/scraper_ujkz.py\n"
            "python src/ingestion/vectoriser.py\n```"
        )
        ok = False

    if ok:
        st.success("✅ Toutes les configurations sont prêtes !")

    return ok


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR JOYEUSE
# ════════════════════════════════════════════════════════════════════════════

def afficher_sidebar():
    """Panneau latéral coloré avec questions suggérées."""
    with st.sidebar:
        # En-tête décoré avec logo
        st.markdown(f"""
        <div style="text-align: center; padding: 10px;">
            <img src="agent_ifoad\logo.png" 
                 style="
                     width: 100px; 
                     height: auto;
                     margin-bottom: 15px;
                     filter: drop-shadow(0 4px 10px rgba(0,0,0,0.3));
                     border-radius: 15px;
                     background: rgba(255,255,255,0.95);
                     padding: 8px;
                     transition: transform 0.3s ease;
                 "
                 onmouseover="this.style.transform='scale(1.05)'"
                 onmouseout="this.style.transform='scale(1)'">
            <h2 style="color: white; margin: 0; text-shadow: 0 2px 8px rgba(0,0,0,0.3);">IFOAD-UJKZ</h2>
            <p style="color: #C8E6C9; font-size: 0.9rem; margin-top: 5px;">🤖 Assistant IA Intelligent</p>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ─── Statut ──────────────────────────────────────────────────────
        st.markdown("###  Statut")
        if st.session_state.agent_charge:
            st.success("✅ Agent opérationnel")
            st.caption(f"🤖 Modèle : `{MODELE_LLM}`")
            st.caption(f"📚 Docs/réponse : `{NOMBRE_DOCS_FINAL}`")
        else:
            st.info("⏳ En cours de chargement...")

        st.divider()

        # ─── Questions suggérées ──────────────────────────────────────────
        st.markdown("### Questions populaires")

        questions = [
            " Quelles formations propose l'IFOAD ?",
            "Comment s'inscrire à l'IFOAD ?",
            " Quelles sont les dates des examens ?",
            " Quels sont les frais de scolarité ?",
            " Quels documents pour le dossier ?",
            " Comment contacter l'IFOAD ?",
            " Quels sont les débouchés du Master ?",
            " Quand commencent les cours ?",
        ]

        for idx, q in enumerate(questions):
            key = f"q_side_{idx}"
            if st.button(q, key=key, use_container_width=True):
                st.session_state.question_suggeree = q
                st.rerun()

        st.divider()

        # ─── Stats ───────────────────────────────────────────────────────
        st.markdown("### 📊 Session")

        # Utiliser des colonnes pour les métriques
        col1, col2 = st.columns(2)
        with col1:
            st.metric("💬 Questions", st.session_state.nb_questions)
        with col2:
            st.metric("😊 Humeur", random.choice(["🌟", "✨", "🌈"]))

        st.divider()

        # ─── Actions ─────────────────────────────────────────────────────
        if st.button("🔄 Nouvelle conversation", use_container_width=True):
            st.session_state.messages_chat = []
            st.session_state.nb_questions = 0
            if st.session_state.agent_rag:
                st.session_state.agent_rag.reinitialiser_historique()
            st.rerun()

        st.divider()

        # Pied de page
        st.markdown("""
        <div style="text-align: center; font-size: 0.8rem; color: #b2bec3;">
            🎓 Projet Data Science 2026<br>
            Master 1 IFOAD — UJKZ<br>
            Dr Delwende D. A. Sawadogo
        </div>
        """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# AFFICHAGE RÉPONSE ET SOURCES
# ════════════════════════════════════════════════════════════════════════════

def afficher_badge_confiance(confiance: float):
    """Affiche un indicateur coloré et joyeux selon le score de confiance."""
    if confiance >= 0.7:
        st.markdown(f"""
        <div class="confiance-elevee">
            🌟 Confiance élevée : {confiance:.0%}
        </div>
        """, unsafe_allow_html=True)
    elif confiance >= 0.4:
        st.markdown(f"""
        <div class="confiance-moyenne">
            🌤️ Confiance moyenne : {confiance:.0%}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="confiance-faible">
            ⚠️ Confiance faible : {confiance:.0%}
        </div>
        """, unsafe_allow_html=True)


def afficher_sources(sources: list):
    """Affiche les sources utilisées dans un expander coloré."""
    if not sources:
        return

    with st.expander(f"📚 Sources utilisées ({len(sources)} documents)"):
        for idx, src in enumerate(sources, 1):
            # Icônes joyeuses selon le type
            icones = {
                "ujkz_web": "🌐",
                "ujkz_pdf": "📄",
                "ujkz_demo": "🎯",
                "facebook_ifoad": "📱",
                "facebook_demo": "💬",
            }
            icone = icones.get(src.get("type", ""), "📎")

            # Couleur aléatoire joyeuse
            couleurs = ["#fd79a8", "#a8e6cf", "#ffeaa7", "#74b9ff", "#a29bfe"]
            color = random.choice(couleurs)

            st.markdown(f"""
            <div style="
                background: {color}20;
                border-radius: 15px;
                padding: 15px;
                margin: 10px 0;
                border-left: 5px solid {color};
            ">
                <b>{icone} [{idx}] {src.get('titre', 'Sans titre')}</b><br>
                📊 Pertinence : <code>{src.get('pertinence', '?')}</code><br>
                📂 Type : <code>{src.get('type', '?')}</code><br>
                <i>"{src.get('extrait', '')[:200]}..."</i>
            </div>
            """, unsafe_allow_html=True)

            url = src.get("url", "")
            if url and url.startswith("http"):
                st.markdown(f"[🔗 Voir la source]({url})")
            st.divider()


# ════════════════════════════════════════════════════════════════════════════
# TRAITEMENT D'UNE QUESTION
# ════════════════════════════════════════════════════════════════════════════

def traiter_question(question: str, agent):
    """Envoie la question à l'agent et affiche la réponse avec style."""

    # ─── Message utilisateur ─────────────────────────────────────────────
    with st.chat_message("user", avatar="👤"):
        st.markdown(question)

    # ─── Réponse de l'agent ──────────────────────────────────────────────
    with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("🔍 Recherche dans la base de connaissances IFOAD..."):
            resultat = agent.repondre(question)

        # Animation de chargement
        st.balloons()

        # Affichage de la réponse dans un cadre coloré
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            border-radius: 15px;
            padding: 20px;
            margin: 10px 0;
        ">
            {resultat['reponse']}
        </div>
        """, unsafe_allow_html=True)

        # Badge de confiance
        afficher_badge_confiance(resultat["confiance"])

        # Avertissement si confiance trop faible
        if not resultat["peut_repondre"]:
            st.info(
                "Je n'ai pas trouvé cette information dans ma base.\n\n"
                "📞 Contactez l'IFOAD directement :\n"
                "- ✉️ ifoad@ujkz.bf\n"
                "- 📱 (+226) 25 30 70 64\n\n"
                "🔄 Vous pouvez aussi reformuler votre question !"
            )

        # Sources
        afficher_sources(resultat["sources"])

        # Message d'encouragement
        if st.session_state.nb_questions % 5 == 0 and st.session_state.nb_questions > 0:
            st.success("🌟 Vous êtes une source d'inspiration ! Continuez à poser des questions !")

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
    """Réaffiche tous les messages précédents de la conversation avec style."""
    for msg in st.session_state.messages_chat:
        if msg["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg["contenu"])
        else:
            with st.chat_message("assistant", avatar="🎓"):
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                    border-radius: 15px;
                    padding: 20px;
                    margin: 10px 0;
                ">
                    {msg['contenu']}
                </div>
                """, unsafe_allow_html=True)

                afficher_badge_confiance(msg.get("confiance", 0))

                if not msg.get("peut_repondre", True):
                    st.info(
                        "🌸 Contactez l'IFOAD : ifoad@ujkz.bf | (+226) 25 30 70 64"
                    )

                afficher_sources(msg.get("sources", []))


# ════════════════════════════════════════════════════════════════════════════
# APPLICATION PRINCIPALE
# ════════════════════════════════════════════════════════════════════════════

def main():
    """Point d'entrée principal de l'application Streamlit."""

    initialiser_session()

    # ─── En-tête joyeux ─────────────────────────────────────────────────
    st.markdown("""
    <div class="custom-header floating">
        <h1 style="font-size: 2.5rem; margin: 0;">🎓 Assistant IFOAD-UJKZ</h1>
        <p style="font-size: 1.1rem; margin: 10px 0 0 0; opacity: 0.95;">
            🤖 Agent IA intelligent · Université Joseph Ki-Zerbo · Burkina Faso
        </p>
        <p style="font-size: 0.9rem; margin: 5px 0 0 0; opacity: 0.85;">
            🌟 Architecture : RAG Hybride (HyDE + Dense + BM25 + RRF + Re-ranking)
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ─── Sidebar ─────────────────────────────────────────────────────────
    afficher_sidebar()

    # ─── Vérification config ──────────────────────────────────────────────
    if not verifier_configuration():
        st.stop()

    # ─── Chargement de l'agent ────────────────────────────────────────────
    if not st.session_state.agent_charge:
        with st.spinner("🚀 Chargement de l'agent IA... (1-2 min au 1er lancement)"):
            agent = charger_agent()

        if agent is None:
            st.error("😢 Impossible de charger l'agent. Vérifiez les logs.")
            st.stop()

        st.session_state.agent_rag = agent
        st.session_state.agent_charge = True
        st.balloons()  # Célébration du chargement
        st.rerun()

    agent = st.session_state.agent_rag

    # ─── Message de bienvenue (si conversation vide) ──────────────────────

    if not st.session_state.messages_chat:
        with st.chat_message("assistant", avatar="🎓"):
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #F5F5DC 0%, #D4E9D6 100%);
                border-radius: 15px;
                padding: 20px;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            ">
                <h3 style="color: #2d3436; margin-top: 0;">👋 Bonjour ! Je suis votre Assistant IA de l'IFOAD-UJKZ !</h3>

                Je peux vous aider avec :
               
                1. Les formations disponibles (Master 1 IFOAD, Licence MI...)
                2. Les modalités d'inscription et documents requis
                3. Le calendrier académique  (cours, examens, regroupements)
                4. Les frais de scolarité  et modalités de paiement
                5. Les contacts du secrétariat IFOAD
                    Comment puis-je vous aider aujourd'hui ?
               
            </div>
            """, unsafe_allow_html=True)
    else:
        # Réaffiche l'historique
        afficher_historique()

    # ─── Traitement question suggérée (clic sidebar) ──────────────────────
    if st.session_state.question_suggeree:
        q = st.session_state.question_suggeree
        st.session_state.question_suggeree = ""
        traiter_question(q, agent)
        st.rerun()

    # ─── Zone de saisie ──────────────────────────────────────────────────
    question = st.chat_input(
        "💭 Posez votre question sur l'IFOAD-UJKZ... (ex: Comment s'inscrire ?)"
    )
    if question:
        traiter_question(question.strip(), agent)
        st.rerun()


if __name__ == "__main__":
    main()