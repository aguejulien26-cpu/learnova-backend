# ============================================================
# LEARNOVA — Backend Python (app.py)
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import PyPDF2
import os
import io
import json

app = Flask(__name__)
CORS(app, origins=["*"])

client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", "")
)

# ── TEST ─────────────────────────────────────────────────────
@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status":  "ok",
        "message": "Learnova Backend est en ligne sur Render !",
        "version": "1.0"
    })

# ── ANALYSER UN PDF ──────────────────────────────────────────
@app.route('/api/analyze-pdf', methods=['POST'])
def analyze_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    fichier = request.files['file']
    titre   = request.form.get('title', 'Cours sans titre')
    niveau  = request.form.get('level', 'Débutant')

    try:
        contenu_pdf = fichier.read()
        lecteur_pdf = PyPDF2.PdfReader(io.BytesIO(contenu_pdf))
        texte_complet = ""
        for numero_page, page in enumerate(lecteur_pdf.pages):
            texte_page = page.extract_text()
            if texte_page:
                texte_complet += f"\n[Page {numero_page + 1}]\n{texte_page}"
        nb_pages = len(lecteur_pdf.pages)
        texte_pour_ia = texte_complet[:6000]
    except Exception as erreur:
        return jsonify({"error": f"Impossible de lire le PDF : {str(erreur)}"}), 400

    prompt = f"""Tu es un expert pédagogique pour Learnova.
Analyse ce cours "{titre}" (niveau: {niveau}, {nb_pages} pages).

CONTENU :
{texte_pour_ia}

Génère UNIQUEMENT ce JSON :
{{
  "resume": "Résumé en 3-4 phrases",
  "concepts_cles": ["concept1", "concept2", "concept3"],
  "chapitres": [
    {{
      "numero": 1,
      "titre": "Titre",
      "description": "Description",
      "lecons": ["Leçon 1", "Leçon 2"],
      "duree_minutes": 20
    }}
  ],
  "quiz": [
    {{
      "question": "Question ?",
      "options": ["A", "B", "C", "D"],
      "correct": 0,
      "explication": "Explication"
    }}
  ],
  "difficulte": "Débutant",
  "duree_totale": "2h30",
  "objectifs": ["Objectif 1", "Objectif 2"]
}}

Génère 5 chapitres et 10 questions quiz. JSON uniquement."""

    try:
        reponse = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )
        texte_reponse = reponse.content[0].text.strip()
        if texte_reponse.startswith("```"):
            texte_reponse = texte_reponse.split("```")[1]
            if texte_reponse.startswith("json"):
                texte_reponse = texte_reponse[4:]
        donnees = json.loads(texte_reponse)
        donnees["titre"]    = titre
        donnees["nb_pages"] = nb_pages
        donnees["status"]   = "success"
        return jsonify(donnees)
    except json.JSONDecodeError:
        return jsonify({"error": "L'IA n'a pas retourné un JSON valide."}), 500
    except Exception as erreur:
        return jsonify({"error": f"Erreur IA : {str(erreur)}"}), 500


# ── RÉPONDRE AUX QUESTIONS ───────────────────────────────────
@app.route('/api/ask-ai', methods=['POST'])
def ask_ai():
    donnees        = request.json or {}
    question       = donnees.get('question', '').strip()
    contexte_cours = donnees.get('course_context', '')[:3000]
    titre_cours    = donnees.get('course_title', 'ce cours')

    if not question:
        return jsonify({"error": "Question vide"}), 400

    prompt = f"""Tu es un professeur expert Learnova.
Tu enseignes : "{titre_cours}"
Contexte : {contexte_cours}
Question : {question}

Réponds clairement, avec exemple si possible, en français, max 3 paragraphes."""

    try:
        reponse = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return jsonify({"answer": reponse.content[0].text, "status": "success"})
    except Exception as erreur:
        return jsonify({"error": str(erreur)}), 500


# ── GÉNÉRER UN PLAN DE SESSION ───────────────────────────────
@app.route('/api/generate-session-plan', methods=['POST'])
def generate_session_plan():
    donnees = request.json or {}
    sujet   = donnees.get('subject', '')
    format_ = donnees.get('format', 'session unique')
    niveau  = donnees.get('level', 'Tous niveaux')

    if not sujet:
        return jsonify({"error": "Sujet manquant"}), 400

    prompt = f"""Génère un plan de session Learnova pour :
Sujet : "{sujet}" | Format : {format_} | Niveau : {niveau}

JSON uniquement :
{{
  "plan": [
    {{
      "time": "00:00",
      "topic": "Titre",
      "type": "lesson",
      "duration_min": 20,
      "description": "Description"
    }}
  ],
  "duree_totale": "2h",
  "nb_challenges": 2,
  "nb_quiz": 1,
  "message_ouverture": "Message de bienvenue"
}}
Types: lesson, challenge, quiz, break. JSON uniquement."""

    try:
        reponse = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        texte = reponse.content[0].text.strip()
        if texte.startswith("```"):
            texte = texte.split("```")[1]
            if texte.startswith("json"):
                texte = texte[4:]
        return jsonify(json.loads(texte))
    except Exception as erreur:
        return jsonify({"error": str(erreur)}), 500


# ── GÉNÉRER UN QUIZ ──────────────────────────────────────────
@app.route('/api/generate-quiz', methods=['POST'])
def generate_quiz():
    donnees = request.json or {}
    sujet   = donnees.get('subject', '')
    niveau  = donnees.get('level', 'Débutant')
    nb      = donnees.get('num_questions', 5)

    prompt = f"""Génère {nb} questions quiz sur "{sujet}" (niveau: {niveau}).
JSON uniquement :
{{
  "quiz": [
    {{
      "question": "Question ?",
      "options": ["A", "B", "C", "D"],
      "correct": 0,
      "explication": "Explication"
    }}
  ]
}}"""

    try:
        reponse = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        texte = reponse.content[0].text.strip()
        if texte.startswith("```"):
            texte = texte.split("```")[1]
            if texte.startswith("json"):
                texte = texte[4:]
        return jsonify(json.loads(texte))
    except Exception as erreur:
        return jsonify({"error": str(erreur)}), 500


# ── L'IA ENSEIGNE EN LIVE ────────────────────────────────────
@app.route('/api/teach', methods=['POST'])
def teach():
    donnees       = request.json or {}
    sujet         = donnees.get('topic', '')
    type_activite = donnees.get('type', 'lesson')
    niveau        = donnees.get('level', 'Débutant')

    if type_activite == 'challenge':
        prompt = f"""Génère un challenge rapide (30 secondes) sur "{sujet}".
JSON uniquement :
{{
  "titre": "Challenge",
  "question": "Question ?",
  "options": ["A", "B", "C", "D"],
  "correct": 0,
  "explication": "Explication",
  "points": 100
}}"""
    else:
        prompt = f"""Tu es le professeur IA de Learnova. Enseigne en direct sur "{sujet}" (niveau: {niveau}).
Sois clair, enthousiaste, avec un exemple concret. Max 4 paragraphes. En français."""

    try:
        reponse = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        texte = reponse.content[0].text.strip()
        if type_activite == 'challenge':
            if texte.startswith("```"):
                texte = texte.split("```")[1]
                if texte.startswith("json"):
                    texte = texte[4:]
            return jsonify(json.loads(texte))
        return jsonify({"content": texte, "status": "success"})
    except Exception as erreur:
        return jsonify({"error": str(erreur)}), 500


# ── LANCER ───────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
