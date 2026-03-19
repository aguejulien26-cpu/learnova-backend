# ============================================================
# LEARNOVA — Backend Python avec Google Gemini
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import PyPDF2
import os
import io
import json

app = Flask(__name__)
CORS(app, origins=["*"])

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))
model = genai.GenerativeModel("gemini-1.5-flash")

def ask_gemini(prompt):
    response = model.generate_content(prompt)
    return response.text.strip()

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "ok",
        "message": "Learnova Backend Gemini est en ligne !"
    })

@app.route('/api/analyze-pdf', methods=['POST'])
def analyze_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400
    fichier = request.files['file']
    titre   = request.form.get('title', 'Cours sans titre')
    niveau  = request.form.get('level', 'Débutant')
    try:
        lecteur_pdf = PyPDF2.PdfReader(io.BytesIO(fichier.read()))
        texte = ""
        for i, page in enumerate(lecteur_pdf.pages):
            t = page.extract_text()
            if t:
                texte += f"\n[Page {i+1}]\n{t}"
        nb_pages = len(lecteur_pdf.pages)
        texte = texte[:6000]
    except Exception as e:
        return jsonify({"error": f"Impossible de lire le PDF : {str(e)}"}), 400

    prompt = f"""Expert pédagogique Learnova. Analyse "{titre}" ({niveau}, {nb_pages} pages).
CONTENU : {texte}
Génère UNIQUEMENT ce JSON :
{{
  "resume": "Résumé 3-4 phrases",
  "concepts_cles": ["c1","c2","c3"],
  "chapitres": [{{"numero":1,"titre":"Titre","description":"Desc","lecons":["L1","L2"],"duree_minutes":20}}],
  "quiz": [{{"question":"Q?","options":["A","B","C","D"],"correct":0,"explication":"Exp"}}],
  "difficulte": "Débutant",
  "duree_totale": "2h",
  "objectifs": ["O1","O2"]
}}
5 chapitres, 10 quiz. JSON uniquement."""

    try:
        reponse = ask_gemini(prompt)
        if reponse.startswith("```"):
            reponse = reponse.split("```")[1]
            if reponse.startswith("json"):
                reponse = reponse[4:]
        data = json.loads(reponse)
        data.update({"titre": titre, "nb_pages": nb_pages, "status": "success"})
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ask-ai', methods=['POST'])
def ask_ai():
    d = request.json or {}
    question = d.get('question', '').strip()
    contexte = d.get('course_context', '')[:3000]
    titre    = d.get('course_title', 'ce cours')
    if not question:
        return jsonify({"error": "Question vide"}), 400
    prompt = f"""Professeur expert Learnova. Cours : "{titre}".
Contexte : {contexte}
Question : {question}
Réponds clairement avec exemple, en français, max 3 paragraphes."""
    try:
        return jsonify({"answer": ask_gemini(prompt), "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-session-plan', methods=['POST'])
def generate_session_plan():
    d      = request.json or {}
    sujet  = d.get('subject', '')
    format_= d.get('format', 'session unique')
    niveau = d.get('level', 'Tous niveaux')
    if not sujet:
        return jsonify({"error": "Sujet manquant"}), 400
    prompt = f"""Plan session Learnova : "{sujet}" | {format_} | {niveau}
JSON uniquement :
{{
  "plan": [{{"time":"00:00","topic":"Titre","type":"lesson","duration_min":20,"description":"Desc"}}],
  "duree_totale": "2h",
  "nb_challenges": 2,
  "nb_quiz": 1,
  "message_ouverture": "Bienvenue !"
}}
Types: lesson, challenge, quiz, break."""
    try:
        texte = ask_gemini(prompt)
        if texte.startswith("```"):
            texte = texte.split("```")[1]
            if texte.startswith("json"):
                texte = texte[4:]
        return jsonify(json.loads(texte))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-quiz', methods=['POST'])
def generate_quiz():
    d     = request.json or {}
    sujet = d.get('subject', '')
    niveau= d.get('level', 'Débutant')
    nb    = d.get('num_questions', 5)
    prompt = f"""Génère {nb} questions quiz sur "{sujet}" ({niveau}).
JSON : {{"quiz":[{{"question":"Q?","options":["A","B","C","D"],"correct":0,"explication":"Exp"}}]}}"""
    try:
        texte = ask_gemini(prompt)
        if texte.startswith("```"):
            texte = texte.split("```")[1]
            if texte.startswith("json"):
                texte = texte[4:]
        return jsonify(json.loads(texte))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/teach', methods=['POST'])
def teach():
    d     = request.json or {}
    sujet = d.get('topic', '')
    type_ = d.get('type', 'lesson')
    niveau= d.get('level', 'Débutant')
    if type_ == 'challenge':
        prompt = f"""Challenge 30 sec sur "{sujet}".
JSON : {{"titre":"Challenge","question":"Q?","options":["A","B","C","D"],"correct":0,"explication":"Exp","points":100}}"""
    else:
        prompt = f"""Professeur IA Learnova. Enseigne "{sujet}" ({niveau}).
Clair, enthousiaste, exemple concret. Max 4 paragraphes. Français."""
    try:
        texte = ask_gemini(prompt)
        if type_ == 'challenge':
            if texte.startswith("```"):
                texte = texte.split("```")[1]
                if texte.startswith("json"):
                    texte = texte[4:]
            return jsonify(json.loads(texte))
        return jsonify({"content": texte, "status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
