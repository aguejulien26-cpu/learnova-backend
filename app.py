from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json

# OpenAI
from openai import OpenAI

app = Flask(__name__)
CORS(app, origins="*")

# Clé OpenAI depuis variable d'environnement Render
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# ── HELPER IA ────────────────────────────────────────────────
def ask_gpt(system_prompt, user_prompt, json_mode=False):
    try:
        kwargs = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    except Exception as e:
        return None

# ── ROUTES ───────────────────────────────────────────────────

@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "Learnova Backend OpenAI est en ligne !",
        "version": "2.0"
    })

@app.route("/api/ask-ai", methods=["POST"])
def ask_ai():
    """L'apprenant pose une question à l'IA pendant un cours ou live"""
    data = request.json or {}
    question = data.get("question", "")
    course_title = data.get("course_title", "ce cours")
    course_context = data.get("course_context", "")

    if not question:
        return jsonify({"error": "Question manquante"}), 400

    system = f"""Tu es un professeur IA expert et pédagogue sur le sujet : "{course_title}".
Contexte du cours : {course_context}

Règles :
- Réponds en français, de façon claire et pédagogique
- Sois précis, concis (3-5 phrases max)
- Donne des exemples concrets si possible
- Tu t'adresses à un apprenant, sois encourageant
- Si tu ne sais pas, dis-le honnêtement"""

    answer = ask_gpt(system, question)
    if not answer:
        answer = "Excellente question ! Ce concept est fondamental. Je t'invite à explorer le contenu du cours pour approfondir ta compréhension."

    return jsonify({"answer": answer})


@app.route("/api/teach", methods=["POST"])
def teach():
    """L'IA génère du contenu d'enseignement pour le live"""
    data = request.json or {}
    topic = data.get("topic", "ce sujet")
    teach_type = data.get("type", "lesson")
    level = data.get("level", "Tous niveaux")

    if teach_type == "lesson":
        system = f"""Tu es un professeur IA expert qui enseigne en direct.
Sujet : {topic} | Niveau : {level}

Génère une leçon d'introduction engageante (5-8 phrases).
Utilise **texte en gras** pour les concepts importants.
Utilise `code` pour les termes techniques.
Commence directement par le contenu, pas de formule de politesse."""

        content = ask_gpt(system, f"Génère la leçon d'introduction pour : {topic}")
        if not content:
            content = f"**{topic}** est un sujet passionnant ! Aujourd'hui nous allons explorer les concepts fondamentaux ensemble. Posez-moi vos questions à tout moment."
        return jsonify({"content": content})

    elif teach_type == "challenge":
        system = """Tu es un professeur IA qui crée des challenges QCM engageants.
Génère un challenge QCM en JSON avec exactement ce format :
{
  "titre": "Challenge rapide !",
  "question": "La question du challenge",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct": 1,
  "explication": "Explication courte de la bonne réponse"
}
correct est l'index (0-3) de la bonne réponse.
La question doit être liée au sujet."""

        result = ask_gpt(system, f"Crée un challenge QCM sur : {topic}", json_mode=True)
        try:
            data_r = json.loads(result)
            return jsonify(data_r)
        except:
            return jsonify({
                "titre": "Challenge rapide !",
                "question": f"Qu'est-ce qui est le plus important pour maîtriser {topic} ?",
                "options": ["Mémoriser la théorie", "Pratiquer régulièrement", "Lire des livres", "Regarder des vidéos"],
                "correct": 1,
                "explication": "La pratique régulière est la clé de l'apprentissage efficace."
            })

    return jsonify({"content": f"Contenu sur {topic}"})


@app.route("/api/generate-session-plan", methods=["POST"])
def generate_session_plan():
    """L'admin crée une session → l'IA génère le plan complet"""
    data = request.json or {}
    subject = data.get("subject", "Formation")
    format_type = data.get("format", "session unique")
    level = data.get("level", "Tous niveaux")

    system = """Tu es un expert en formation qui crée des plans de session pédagogiques.
Génère un plan de session en JSON avec ce format exact :
{
  "plan": [
    {"time": "00:00", "topic": "Nom du module", "type": "lesson"},
    {"time": "00:20", "topic": "Nom du module", "type": "lesson"},
    {"time": "00:45", "topic": "Challenge collectif", "type": "challenge"},
    {"time": "01:00", "topic": "Pause", "type": "break"},
    {"time": "01:10", "topic": "Module avancé", "type": "lesson"},
    {"time": "01:50", "topic": "Quiz final", "type": "quiz"}
  ]
}
Types possibles : lesson, challenge, quiz, break
Adapte le plan au format et au sujet donné."""

    result = ask_gpt(system,
        f"Crée un plan de session sur '{subject}', format: {format_type}, niveau: {level}",
        json_mode=True)

    try:
        plan_data = json.loads(result)
        return jsonify(plan_data)
    except:
        # Fallback
        return jsonify({"plan": [
            {"time": "00:00", "topic": f"Introduction à {subject}", "type": "lesson"},
            {"time": "00:20", "topic": "Concepts fondamentaux", "type": "lesson"},
            {"time": "00:45", "topic": "Challenge QCM", "type": "challenge"},
            {"time": "01:00", "topic": "Pause", "type": "break"},
            {"time": "01:10", "topic": "Approfondissement", "type": "lesson"},
            {"time": "01:50", "topic": "Quiz final", "type": "quiz"}
        ]})


@app.route("/api/generate-quiz", methods=["POST"])
def generate_quiz():
    """Génère un quiz complet pour un cours"""
    data = request.json or {}
    subject = data.get("subject", "ce cours")
    level = data.get("level", "Débutant")
    num = min(int(data.get("num_questions", 5)), 10)

    system = f"""Tu es un expert qui crée des quiz pédagogiques.
Génère exactement {num} questions QCM sur "{subject}" (niveau {level}).
Format JSON exact :
{{
  "quiz": [
    {{
      "question": "La question ?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct": 1,
      "explication": "Explication de la bonne réponse"
    }}
  ]
}}
correct est l'index (0-3) de la bonne réponse.
Les questions doivent couvrir différents aspects du sujet."""

    result = ask_gpt(system,
        f"Génère {num} questions de quiz sur : {subject}",
        json_mode=True)

    try:
        quiz_data = json.loads(result)
        if "quiz" in quiz_data and len(quiz_data["quiz"]) > 0:
            return jsonify(quiz_data)
    except:
        pass

    # Fallback
    return jsonify({"quiz": [
        {
            "question": f"Quel est le concept le plus important de {subject} ?",
            "options": ["La théorie pure", "La pratique régulière", "Les diplômes", "La mémoire"],
            "correct": 1,
            "explication": "La pratique régulière est toujours la clé de la maîtrise."
        },
        {
            "question": f"Comment progresser efficacement en {subject} ?",
            "options": ["Lire seulement", "Pratiquer et expérimenter", "Mémoriser", "Copier"],
            "correct": 1,
            "explication": "Pratiquer et expérimenter permet une vraie compréhension."
        }
    ]})


@app.route("/api/analyze-pdf", methods=["POST"])
def analyze_pdf():
    """Analyse un PDF uploadé et génère résumé + chapitres + quiz"""
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    file = request.files["file"]
    title = request.form.get("title", "Cours")
    level = request.form.get("level", "Débutant")

    # Lire le PDF
    try:
        import PyPDF2
        import io
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        text = ""
        for i, page in enumerate(pdf_reader.pages):
            if i >= 20:  # Max 20 pages
                break
            text += page.extract_text() + "\n"
        text = text[:8000]  # Max 8000 chars pour GPT
    except Exception as e:
        text = f"Cours sur le sujet : {title}"

    system = """Tu es un expert pédagogue qui analyse des documents PDF.
Génère une analyse complète en JSON avec ce format exact :
{
  "resume": "Résumé en 2-3 phrases",
  "duree_totale": "2h30",
  "concepts_cles": ["Concept 1", "Concept 2", "Concept 3"],
  "objectifs": ["Objectif 1", "Objectif 2"],
  "chapitres": [
    {
      "titre": "Chapitre 1",
      "lecons": ["Leçon 1.1", "Leçon 1.2"],
      "duree_minutes": 30
    }
  ],
  "quiz": [
    {
      "question": "Question ?",
      "options": ["A", "B", "C", "D"],
      "correct": 0,
      "explication": "Explication"
    }
  ]
}
Génère 3-5 chapitres et exactement 10 questions de quiz.
Base-toi sur le contenu du document."""

    result = ask_gpt(system,
        f"Analyse ce document '{title}' (niveau {level}) :\n\n{text}",
        json_mode=True)

    try:
        analysis = json.loads(result)
        return jsonify(analysis)
    except:
        return jsonify({
            "resume": f"Ce cours couvre les fondamentaux de {title}.",
            "duree_totale": "2h",
            "concepts_cles": [title, "Pratique", "Théorie"],
            "objectifs": [f"Comprendre {title}", "Appliquer les concepts"],
            "chapitres": [
                {"titre": "Introduction", "lecons": ["Présentation", "Objectifs"], "duree_minutes": 20},
                {"titre": "Contenu principal", "lecons": ["Concepts clés", "Exemples pratiques"], "duree_minutes": 60},
                {"titre": "Conclusion", "lecons": ["Résumé", "Prochaines étapes"], "duree_minutes": 20}
            ],
            "quiz": [
                {"question": f"Qu'est-ce que {title} ?", "options": ["Définition A", "Définition B", "Définition C", "Définition D"], "correct": 0, "explication": f"{title} est un domaine important à maîtriser."}
            ]
        })


@app.route("/api/community-moderate", methods=["POST"])
def moderate():
    """Modération automatique des posts communauté"""
    data = request.json or {}
    text = data.get("text", "")

    system = """Tu es un modérateur de communauté éducative.
Analyse ce texte et réponds en JSON :
{"approved": true/false, "reason": "raison si refusé"}
Refuse si : spam, insultes, contenu inapproprié, hors-sujet."""

    result = ask_gpt(system, text, json_mode=True)
    try:
        return jsonify(json.loads(result))
    except:
        return jsonify({"approved": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
