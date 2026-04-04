"""
LEARNOVA BACKEND V4
===================================
IA intelligente avec :
- Contexte complet du cours injecté à chaque appel
- Historique de conversation (mémoire)
- Temperature variée selon le type de réponse
- Anti-répétition (seed aléatoire)
- Analyse PDF → cours complet
- Génération de plan de session
- Génération de quiz
- Challenges QCM en live
- Transitions entre modules
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import os, json, random, io

from openai import OpenAI

# ── INIT ──────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, origins="*", methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL  = "gpt-4o-mini"

# ── HELPER GPT ────────────────────────────────────────────────
def gpt(system: str, messages: list, temperature: float = 0.8,
        max_tokens: int = 1000, json_mode: bool = False) -> str | None:
    try:
        kwargs = {
            "model":       MODEL,
            "messages":    [{"role": "system", "content": system}] + messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

    except Exception as e:
        print(f"[GPT ERROR] {e}")
        return None


def build_course_context(data: dict) -> str:
    """Construit un bloc de contexte complet pour l'IA à partir des données du cours."""
    parts = []

    if data.get("course_title"):
        parts.append(f"Cours : {data['course_title']}")
    if data.get("course_context"):
        parts.append(f"Description : {data['course_context']}")
    if data.get("current_module"):
        parts.append(f"Module actuel : {data['current_module']}")
    if data.get("level"):
        parts.append(f"Niveau : {data['level']}")

    chapitres = data.get("chapitres", [])
    if chapitres:
        titres = [c.get("titre", "") for c in chapitres[:5] if c.get("titre")]
        if titres:
            parts.append(f"Chapitres du cours : {' | '.join(titres)}")

    concepts = data.get("concepts_cles", [])
    if concepts:
        parts.append(f"Concepts clés : {', '.join(concepts[:8])}")

    objectifs = data.get("objectifs", [])
    if objectifs:
        parts.append(f"Objectifs : {'; '.join(objectifs[:3])}")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def home():
    return jsonify({
        "status":   "ok",
        "message":  "Learnova Backend V4 — IA intelligente active !",
        "model":    MODEL,
        "routes": [
            "POST /api/ask-ai",
            "POST /api/teach",
            "POST /api/generate-session-plan",
            "POST /api/generate-quiz",
            "POST /api/analyze-pdf",
            "POST /api/transition",
            "POST /api/community-moderate",
        ]
    })


# ── ROUTE : ask-ai ─────────────────────────────────────────────
@app.route("/api/ask-ai", methods=["POST"])
def ask_ai():
    """
    L'apprenant pose une question pendant le cours ou le live.
    L'IA reçoit le contexte complet du cours + l'historique.
    """
    d = request.json or {}

    question = d.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question manquante"}), 400

    ctx   = build_course_context(d)
    history = d.get("history", [])
    seed  = random.randint(1000, 9999)
    course_title = d.get("course_title", "ce cours")
    level = d.get("level", "Tous niveaux")

    system = f"""Tu es un professeur IA expert, pédagogue et bienveillant sur Learnova.

CONTEXTE DU COURS :
{ctx}

RÈGLES ABSOLUES :
1. Réponds DIRECTEMENT et PRÉCISÉMENT à la question posée — pas de hors-sujet
2. Adapte ta réponse au niveau "{level}" de l'apprenant
3. Utilise des exemples concrets liés au cours "{course_title}"
4. Format : **gras** pour les points importants, `code` pour le technique
5. Longueur : 3-6 phrases max, sauf si la question nécessite plus de détails
6. Sois encourageant et précis — jamais vague ni générique
7. Si tu ne sais pas → dis-le et oriente vers une ressource
8. Ne répète JAMAIS tes réponses précédentes (seed anti-répétition: {seed})

Tu t'adresses à l'apprenant directement, à la 2ème personne. Commence directement ta réponse, sans formule d'intro."""

    # Construire les messages avec l'historique
    messages = []
    for msg in history[-8:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    answer = gpt(system, messages, temperature=0.82, max_tokens=600)

    if not answer or len(answer) < 10:
        answer = (
            f"Excellente question sur **{course_title}** ! "
            "Ce point est important. Peux-tu préciser ce que tu n'as pas compris ?"
        )

    return jsonify({"answer": answer, "question": question})


# ── ROUTE : teach ─────────────────────────────────────────────
@app.route("/api/teach", methods=["POST"])
def teach():
    """
    Génère du contenu d'enseignement (leçon ou challenge QCM)
    adapté au module et au cours fourni par l'admin.
    """
    d           = request.json or {}
    topic       = d.get("topic", "ce sujet")
    teach_type  = d.get("type", "lesson")
    level       = d.get("level", "Tous niveaux")
    course_data = d.get("course_data", {})
    seed        = random.randint(1000, 9999)

    course_title = course_data.get("titre", topic)

    # ── Leçon ──────────────────────────────────────────────────
    if teach_type == "lesson":

        chaps_str = ""
        if course_data.get("chapitres"):
            chaps_str = "\n".join([
                f"- {c.get('titre', '')}: {', '.join(c.get('lecons', [])[:2])}"
                for c in course_data["chapitres"][:4]
            ])

        concepts_str = ""
        if course_data.get("concepts_cles"):
            concepts_str = ", ".join(course_data["concepts_cles"][:6])

        system = f"""Tu es un professeur IA expert qui enseigne en direct sur Learnova.

Cours : {course_title}
Module actuel : {topic}
Niveau : {level}
{f"Plan du cours :\n{chaps_str}" if chaps_str else ""}
{f"Concepts clés : {concepts_str}" if concepts_str else ""}
{f"Description : {course_data.get('description', '')}" if course_data.get('description') else ""}

Génère une leçon d'introduction engageante et structurée pour ce module.
- Commence par une accroche captivante (une question ou une affirmation forte)
- Explique le concept principal clairement avec un exemple concret lié à "{course_title}"
- Donne 2-3 points clés à retenir
- Termine par un encouragement à poser des questions

Format :
- Utilise **gras** pour les concepts importants
- Utilise `code` pour les éléments techniques
- 6-10 phrases maximum
- Ton : enthousiaste, expert, bienveillant
- Seed anti-répétition : {seed} (varie chaque leçon)"""

        content = gpt(
            system,
            [{"role": "user", "content": f"Enseigne le module : {topic}"}],
            temperature=0.85, max_tokens=800
        )

        if not content:
            content = (
                f"Explorons maintenant **{topic}** — un module essentiel dans {course_title}. "
                "Ce concept est fondamental pour progresser. "
                "Voici ce que tu vas maîtriser : les bases, les applications pratiques et les erreurs à éviter. "
                "Pose tes questions à tout moment !"
            )

        return jsonify({"content": content, "type": "lesson", "topic": topic})

    # ── Challenge / Quiz QCM ───────────────────────────────────
    elif teach_type in ("challenge", "quiz"):

        system = f"""Tu crées des challenges QCM engageants et variés pour Learnova.

Cours : {course_title}
Module : {topic}
Niveau : {level}

Génère un challenge QCM unique en JSON strict :
{{
  "titre": "Challenge — [nom court accrocheur]",
  "question": "Question précise et liée directement au module ?",
  "options": ["Option A complète", "Option B complète", "Option C complète", "Option D complète"],
  "correct": 1,
  "explication": "Explication claire de la bonne réponse en 2-3 phrases pédagogiques."
}}

RÈGLES :
- La question doit être directement liée à "{topic}" dans le contexte de "{course_title}"
- 4 options plausibles, une seule correcte
- "correct" = index 0, 1, 2 ou 3 de la bonne option
- L'explication doit apprendre quelque chose de concret
- Varie la difficulté et le style (question directe, application, analyse)
- Seed : {seed}"""

        result = gpt(
            system,
            [{"role": "user", "content": f"Challenge sur : {topic}"}],
            temperature=0.9, max_tokens=500, json_mode=True
        )

        try:
            ch = json.loads(result)
            if ch.get("question") and ch.get("options") and len(ch["options"]) == 4:
                return jsonify(ch)
        except Exception:
            pass

        # Fallback
        return jsonify({
            "titre":       f"Challenge — {topic}",
            "question":    f"Quel est le concept le plus important dans '{topic}' ?",
            "options":     ["La théorie seule suffit", "La pratique régulière", "Mémoriser par cœur", "Regarder des vidéos"],
            "correct":     1,
            "explication": "La pratique régulière est toujours la clé de la maîtrise d'un sujet. La théorie sans pratique ne suffit pas."
        })

    return jsonify({"error": "Type non reconnu"}), 400


# ── ROUTE : generate-session-plan ─────────────────────────────
@app.route("/api/generate-session-plan", methods=["POST"])
def generate_session_plan():
    """
    L'admin crée une session → l'IA génère le programme complet
    en utilisant les données du cours lié si disponible.
    """
    d           = request.json or {}
    subject     = d.get("subject", "Formation")
    fmt         = d.get("format", "session unique")
    level       = d.get("level", "Tous niveaux")
    course_data = d.get("course_data", {})

    # Extraire les chapitres du cours lié
    chaps_str = ""
    if course_data.get("chapitres"):
        chaps_str = "\n".join([
            f"- {c.get('titre', '')}"
            for c in course_data["chapitres"][:7]
        ])

    concepts_str = ""
    if course_data.get("concepts_cles"):
        concepts_str = ", ".join(course_data["concepts_cles"][:6])

    system = f"""Tu es un expert en ingénierie pédagogique qui conçoit des plans de formation pour Learnova.

Sujet de la session : {subject}
Format : {fmt}
Niveau : {level}
{f"Chapitres du cours lié :\n{chaps_str}" if chaps_str else ""}
{f"Concepts clés : {concepts_str}" if concepts_str else ""}

Génère un plan de session réaliste, dynamique et engageant en JSON :
{{
  "plan": [
    {{"time": "00:00", "topic": "Nom précis du module", "type": "lesson"}},
    ...
  ]
}}

Types disponibles :
- "lesson" : enseignement magistral par l'IA
- "challenge" : QCM interactif (challenge rapide)
- "quiz" : évaluation complète
- "break" : pause

Adapte le nombre d'étapes selon le format "{fmt}" :
- "1h/jour" → 5 étapes sur 1h
- "2h/semaine" → 6-7 étapes sur 2h
- "session unique" → 6-8 étapes sur 2h
- "30h/mois" → 8-10 étapes sur plusieurs semaines

IMPORTANT :
- Les topics doivent être SPÉCIFIQUES à "{subject}", jamais génériques
- Si des chapitres du cours sont fournis, utilise-les comme topics
- Alterne leçons et challenges pour maintenir l'engagement
- Termine toujours par un quiz d'évaluation"""

    result = gpt(
        system,
        [{"role": "user", "content": f"Plan pour : {subject}"}],
        temperature=0.7, max_tokens=1000, json_mode=True
    )

    try:
        data = json.loads(result)
        if data.get("plan") and len(data["plan"]) > 0:
            return jsonify(data)
    except Exception:
        pass

    # Fallback adapté au sujet
    fallbacks = {
        "1h/jour": [
            {"time": "00:00", "topic": f"Introduction à {subject}", "type": "lesson"},
            {"time": "00:15", "topic": f"Fondamentaux de {subject}", "type": "lesson"},
            {"time": "00:35", "topic": "Challenge QCM", "type": "challenge"},
            {"time": "00:45", "topic": f"Approfondissement {subject}", "type": "lesson"},
            {"time": "00:55", "topic": "Quiz de clôture", "type": "quiz"},
        ],
        "session unique": [
            {"time": "00:00", "topic": f"Introduction & objectifs — {subject}", "type": "lesson"},
            {"time": "00:20", "topic": f"Module 1 — Fondations de {subject}", "type": "lesson"},
            {"time": "00:50", "topic": "Challenge #1", "type": "challenge"},
            {"time": "01:00", "topic": "Pause", "type": "break"},
            {"time": "01:10", "topic": f"Module 2 — Approfondissement {subject}", "type": "lesson"},
            {"time": "01:40", "topic": "Challenge #2", "type": "challenge"},
            {"time": "01:55", "topic": "Quiz de certification", "type": "quiz"},
        ],
    }

    plan = fallbacks.get(fmt, fallbacks["session unique"])
    return jsonify({"plan": plan})


# ── ROUTE : generate-quiz ─────────────────────────────────────
@app.route("/api/generate-quiz", methods=["POST"])
def generate_quiz():
    """
    Génère un quiz complet (N questions) pour un cours.
    Utilisé par l'admin depuis l'interface.
    """
    d           = request.json or {}
    subject     = d.get("subject", "ce cours")
    level       = d.get("level", "Débutant")
    num         = min(int(d.get("num_questions", 5)), 10)
    course_data = d.get("course_data", {})
    seed        = random.randint(1000, 9999)

    chaps_str = ""
    if course_data.get("chapitres"):
        chaps_str = "\n".join([
            f"- {c.get('titre', '')}: {', '.join([str(l) if isinstance(l,str) else l.get('titre','') for l in c.get('lecons', [])[:3]])}"
            for c in course_data["chapitres"][:5]
        ])

    system = f"""Tu es un expert en évaluation pédagogique pour Learnova.

Cours : {subject}
Niveau : {level}
{f"Contenu du cours :\n{chaps_str}" if chaps_str else ""}

Génère exactement {num} questions QCM progressives et variées en JSON strict :
{{
  "quiz": [
    {{
      "question": "Question précise ?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct": 0,
      "explication": "Explication pédagogique complète de la bonne réponse."
    }}
  ]
}}

RÈGLES :
- Questions progressives : facile → difficile
- Chaque question teste un concept DIFFÉRENT du cours
- 4 options plausibles, une seule correcte
- "correct" = index 0-3 de la bonne option
- L'explication doit apprendre quelque chose d'utile (pas juste confirmer)
- Varie le style : définition, application, comparaison, analyse
- Seed : {seed}"""

    result = gpt(
        system,
        [{"role": "user", "content": f"Génère {num} questions sur : {subject}"}],
        temperature=0.8, max_tokens=2500, json_mode=True
    )

    try:
        quiz_data = json.loads(result)
        if quiz_data.get("quiz") and len(quiz_data["quiz"]) > 0:
            return jsonify(quiz_data)
    except Exception:
        pass

    return jsonify({
        "quiz": [{
            "question":    f"Quel est le concept fondamental de '{subject}' ?",
            "options":     ["La mémorisation", "La pratique régulière", "La lecture seule", "Les diplômes"],
            "correct":     1,
            "explication": "La pratique régulière est la base de tout apprentissage efficace et durable."
        }]
    })


# ── ROUTE : analyze-pdf ───────────────────────────────────────
@app.route("/api/analyze-pdf", methods=["POST"])
def analyze_pdf():
    """
    Analyse un PDF uploadé par l'admin et génère :
    - Résumé
    - Durée estimée
    - Concepts clés
    - Objectifs pédagogiques
    - Chapitres avec leçons
    - Quiz complet (10 questions)
    """
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    file  = request.files["file"]
    title = request.form.get("title", "Cours")
    level = request.form.get("level", "Débutant")

    # ── Extraction du texte PDF ───────────────────────────────
    text = ""
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        for i, page in enumerate(reader.pages):
            if i >= 25:
                break
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception:
                continue
        text = text[:10000]
    except Exception as e:
        print(f"[PDF ERROR] {e}")
        text = f"Document sur le sujet : {title}"

    if not text.strip():
        text = f"Document pédagogique sur le sujet : {title}"

    # ── Analyse IA ────────────────────────────────────────────
    system = f"""Tu es un expert en ingénierie pédagogique qui analyse des documents de formation pour Learnova.

Titre du cours : {title}
Niveau cible : {level}

Analyse ce document et génère une structure pédagogique COMPLÈTE en JSON strict :
{{
  "resume": "Résumé en 2-3 phrases percutantes qui donnent envie d'apprendre",
  "duree_totale": "Xh30",
  "concepts_cles": ["Concept 1", "Concept 2", "Concept 3", "Concept 4", "Concept 5"],
  "objectifs": [
    "L'apprenant sera capable de ...",
    "L'apprenant saura ...",
    "L'apprenant pourra ..."
  ],
  "chapitres": [
    {{
      "titre": "Chapitre 1 — Titre précis basé sur le contenu",
      "lecons": ["Leçon 1.1 — Titre précis", "Leçon 1.2 — Titre précis", "Leçon 1.3 — Titre précis"],
      "duree_minutes": 30
    }}
  ],
  "quiz": [
    {{
      "question": "Question précise basée sur le contenu réel ?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct": 0,
      "explication": "Explication pédagogique complète."
    }}
  ]
}}

IMPÉRATIF :
- 3 à 6 chapitres cohérents basés sur le CONTENU RÉEL du document
- Exactement 10 questions de quiz basées sur le contenu réel
- Les concepts et objectifs doivent correspondre exactement au document
- Durée réaliste : 1h pour 15-20 pages, 3h pour 50+ pages
- Les titres de chapitres et leçons doivent être spécifiques, pas génériques"""

    result = gpt(
        system,
        [{"role": "user", "content": f"Analyse ce document :\n\n{text}"}],
        temperature=0.6, max_tokens=3500, json_mode=True
    )

    try:
        analysis = json.loads(result)

        # Vérifications minimales
        if not analysis.get("chapitres") or len(analysis["chapitres"]) == 0:
            raise ValueError("Pas de chapitres générés")
        if not analysis.get("quiz") or len(analysis["quiz"]) == 0:
            raise ValueError("Pas de quiz généré")

        # S'assurer qu'on a bien 10 questions
        quiz = analysis.get("quiz", [])
        if len(quiz) < 10:
            print(f"[QUIZ] Seulement {len(quiz)} questions générées")

        return jsonify(analysis)

    except Exception as e:
        print(f"[PDF PARSE ERROR] {e}")

    # ── Fallback ─────────────────────────────────────────────
    return jsonify({
        "resume":       f"Ce cours couvre les fondamentaux de {title} avec une approche progressive et pratique.",
        "duree_totale": "3h",
        "concepts_cles": [title, "Fondamentaux", "Pratique", "Application", "Maîtrise"],
        "objectifs": [
            f"Comprendre les bases de {title}",
            f"Appliquer les concepts de {title}",
            "Maîtriser les techniques avancées"
        ],
        "chapitres": [
            {
                "titre":          "Introduction et fondamentaux",
                "lecons":         ["Présentation générale", "Concepts de base", "Premiers pas pratiques"],
                "duree_minutes":  40
            },
            {
                "titre":          "Contenu principal",
                "lecons":         ["Concepts clés approfondis", "Exemples pratiques", "Exercices guidés"],
                "duree_minutes":  70
            },
            {
                "titre":          "Applications avancées",
                "lecons":         ["Cas pratiques réels", "Techniques avancées", "Projet final"],
                "duree_minutes":  70
            }
        ],
        "quiz": [
            {
                "question":    f"Quelle est la définition principale de '{title}' ?",
                "options":     ["Définition A", "Définition B", "Définition C", "Définition D"],
                "correct":     0,
                "explication": f"{title} est un domaine qui mérite une attention particulière."
            }
        ]
    })


# ── ROUTE : transition ────────────────────────────────────────
@app.route("/api/transition", methods=["POST"])
def generate_transition():
    """
    Génère une phrase de transition entre les modules du live.
    Utilisée automatiquement pendant la session.
    """
    d           = request.json or {}
    from_module = d.get("from", "")
    to_module   = d.get("to", "")
    course      = d.get("course", "")
    step_number = d.get("step", 1)
    seed        = random.randint(1000, 9999)

    system = f"""Tu es un animateur de formation dynamique et enthousiaste sur Learnova.
Génère UNE SEULE phrase de transition courte (15-25 mots maximum) entre deux modules.
- Crée de l'enthousiasme pour la prochaine étape
- Mentionne brièvement ce qui vient d'être appris
- Annonce la suite de façon positive
- Ton dynamique, positif et motivant
- Seed : {seed}"""

    msg = f"Transition de '{from_module}' vers '{to_module}' dans le cours '{course}' (étape {step_number})"
    result = gpt(system, [{"role": "user", "content": msg}], temperature=0.9, max_tokens=80)

    transition = result or f"Excellent travail ! Passons maintenant à : **{to_module}** !"
    return jsonify({"transition": transition})


# ── ROUTE : community-moderate ────────────────────────────────
@app.route("/api/community-moderate", methods=["POST"])
def community_moderate():
    """
    Modération automatique des posts de la communauté.
    Accepte ou refuse un contenu selon les règles de la plateforme.
    """
    d    = request.json or {}
    text = d.get("text", "").strip()

    if not text:
        return jsonify({"approved": False, "reason": "Contenu vide"})

    system = """Tu es un modérateur bienveillant d'une communauté éducative sur Learnova.

Analyse ce texte et réponds en JSON strict :
{"approved": true/false, "reason": "raison si refusé (vide si approuvé)"}

REFUSE uniquement si :
- Spam évident ou publicité non sollicitée
- Insultes graves ou langage haineux
- Contenu totalement hors-sujet (non éducatif)
- Désinformation manifeste

ACCEPTE tout le reste :
- Questions (même basiques)
- Critiques constructives
- Avis négatifs sur un cours (si respectueux)
- Discussions techniques
- Partage de ressources
- Expériences personnelles

Sois indulgent. L'objectif est une communauté ouverte et bienveillante."""

    result = gpt(
        system,
        [{"role": "user", "content": text}],
        temperature=0.3, max_tokens=100, json_mode=True
    )

    try:
        return jsonify(json.loads(result))
    except Exception:
        return jsonify({"approved": True, "reason": ""})


# ── MAIN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[LEARNOVA] Backend V4 démarré sur le port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
