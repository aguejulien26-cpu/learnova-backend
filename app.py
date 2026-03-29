"""
LEARNOVA BACKEND V3
IA intelligente avec :
- Mémoire conversationnelle (historique des échanges)
- Contexte complet du cours (chapitres, objectifs, etc.)
- Temperature variable selon le type de réponse
- Streaming (réponses mot par mot comme ChatGPT)
- Anti-répétition (seed aléatoire dans les prompts)
- Analyse PDF, génération quiz, challenges contextuels
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import os, json, random, time, io

from openai import OpenAI

app = Flask(__name__)
CORS(app, origins="*")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL  = "gpt-4o-mini"

# ── HELPER : Appel GPT standard ───────────────────────────────
def gpt(system: str, messages: list, temperature: float = 0.8,
        max_tokens: int = 1200, json_mode: bool = False) -> str | None:
    try:
        kwargs = {
            "model": MODEL,
            "messages": [{"role": "system", "content": system}] + messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content
    except Exception as e:
        print(f"GPT Error: {e}")
        return None


# ── HELPER : Streaming GPT ────────────────────────────────────
def gpt_stream(system: str, messages: list, temperature: float = 0.8,
               max_tokens: int = 1200):
    """Générateur de tokens pour le streaming"""
    try:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": system}] + messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if hasattr(delta, 'content') and delta.content:
                yield delta.content
    except Exception as e:
        print(f"GPT Stream Error: {e}")
        yield ""


# ── ROUTES ────────────────────────────────────────────────────

@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "Learnova Backend V3 — IA intelligente active !",
        "model": MODEL,
        "features": ["streaming", "context", "memory", "pdf-analysis", "challenge-gen"]
    })


@app.route("/api/ask-ai", methods=["POST"])
def ask_ai():
    """
    L'apprenant pose une question à l'IA pendant le live ou le cours.
    L'IA reçoit l'historique de conversation + le contexte complet du cours.
    """
    data           = request.json or {}
    question       = data.get("question", "").strip()
    course_title   = data.get("course_title", "ce cours")
    course_context = data.get("course_context", "")
    history        = data.get("history", [])  # Historique: [{role, content}]
    current_module = data.get("current_module", "")
    chapitres      = data.get("chapitres", [])
    concepts       = data.get("concepts_cles", [])
    level          = data.get("level", "Tous niveaux")

    if not question:
        return jsonify({"error": "Question manquante"}), 400

    # Contexte enrichi du cours
    context_parts = [f"Cours : {course_title}"]
    if course_context:
        context_parts.append(f"Description : {course_context}")
    if current_module:
        context_parts.append(f"Module en cours : {current_module}")
    if chapitres:
        titres = [c.get('titre', '') for c in chapitres[:5] if c.get('titre')]
        if titres:
            context_parts.append(f"Chapitres : {', '.join(titres)}")
    if concepts:
        context_parts.append(f"Concepts clés : {', '.join(concepts[:8])}")
    context_parts.append(f"Niveau : {level}")

    context_str = "\n".join(context_parts)

    # System prompt précis et anti-répétition
    seed = random.randint(1000, 9999)
    system = f"""Tu es un professeur IA expert, pédagogue et bienveillant pour Learnova.

CONTEXTE DU COURS :
{context_str}

RÈGLES ABSOLUES :
1. Réponds DIRECTEMENT et PRÉCISÉMENT à la question posée — ne dévie jamais
2. Adapte ta réponse au niveau "{level}" de l'apprenant
3. Utilise des exemples concrets et pertinents liés à "{course_title}"
4. Sois encourageant mais précis — évite les réponses vagues
5. Format : utilise **gras** pour les points importants, `code` pour le technique
6. Longueur : 3-6 phrases max sauf si la question nécessite plus de détails
7. Si tu ne sais pas → dis-le honnêtement et oriente vers une ressource
8. Ne répète JAMAIS tes réponses précédentes (seed: {seed})

Tu t'adresses à l'apprenant directement, à la 2ème personne."""

    # Construire les messages avec l'historique
    messages = []
    # Ajouter l'historique récent (max 8 échanges)
    for msg in history[-8:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    # Ajouter la question actuelle
    messages.append({"role": "user", "content": question})

    # Streaming ou standard selon la préférence
    use_stream = data.get("stream", False)

    if use_stream:
        def generate():
            full = ""
            for token in gpt_stream(system, messages, temperature=0.8, max_tokens=600):
                full += token
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield f"data: {json.dumps({'done': True, 'full': full})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )
    else:
        answer = gpt(system, messages, temperature=0.8, max_tokens=600)
        if not answer:
            answer = f"Excellente question sur **{course_title}** ! Ce point est important. Peux-tu me donner plus de détails sur ce que tu n'as pas compris ?"
        return jsonify({"answer": answer, "question": question})


@app.route("/api/teach", methods=["POST"])
def teach():
    """L'IA génère du contenu d'enseignement adapté au module et au cours"""
    data         = request.json or {}
    topic        = data.get("topic", "ce sujet")
    teach_type   = data.get("type", "lesson")
    level        = data.get("level", "Tous niveaux")
    course_data  = data.get("course_data", {})
    plan_context = data.get("plan_context", "")

    seed = random.randint(1000, 9999)

    if teach_type == "lesson":
        # Contexte du cours pour la leçon
        chapitres_str = ""
        if course_data.get("chapitres"):
            chapitres_str = "\n".join([
                f"- {c.get('titre', '')}: {', '.join(c.get('lecons', [])[:2])}"
                for c in course_data["chapitres"][:3]
            ])

        system = f"""Tu es un professeur IA expert qui enseigne en direct sur Learnova.

Cours : {course_data.get('titre', topic)}
Module actuel : {topic}
Niveau : {level}
{f"Plan du cours : {chapitres_str}" if chapitres_str else ""}
{f"Contexte : {plan_context}" if plan_context else ""}

Génère une leçon d'introduction engageante et structurée pour ce module.
- Commence par une accroche
- Explique le concept principal avec un exemple concret
- Donne 2-3 points clés à retenir
- Utilise **gras** pour les concepts importants et `code` pour le technique
- Longueur : 6-10 phrases
- Ton : enthousiaste, expert, bienveillant
- DIFFÉRENT des leçons précédentes (seed: {seed})"""

        content = gpt(system, [{"role": "user", "content": f"Enseigne le module : {topic}"}],
                      temperature=0.85, max_tokens=800)

        if not content:
            content = f"Nous explorons maintenant **{topic}**. Ce module est fondamental dans notre progression. Concentrons-nous sur les concepts essentiels et leurs applications pratiques."

        return jsonify({"content": content, "type": "lesson"})

    elif teach_type in ("challenge", "quiz"):
        system = f"""Tu es un professeur IA qui crée des challenges QCM engageants et variés.

Cours : {course_data.get('titre', topic)}
Module : {topic}
Niveau : {level}

Génère un challenge QCM unique et pertinent en JSON EXACT :
{{
  "titre": "Challenge — [nom court]",
  "question": "Question précise liée au module ?",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct": 1,
  "explication": "Explication claire de la bonne réponse (2-3 phrases)"
}}

RÈGLES :
- Question directement liée au contenu du module "{topic}"
- 4 options plausibles mais une seule correcte
- L'explication doit apprendre quelque chose
- correct = index (0, 1, 2 ou 3) de la bonne réponse
- Varie les difficultés (seed: {seed})"""

        result = gpt(system,
                     [{"role": "user", "content": f"Challenge sur : {topic}"}],
                     temperature=0.9, max_tokens=500, json_mode=True)
        try:
            ch = json.loads(result)
            if ch.get("question") and ch.get("options") and len(ch["options"]) == 4:
                return jsonify(ch)
        except:
            pass

        return jsonify({
            "titre": f"Challenge — {topic}",
            "question": f"Quel est le concept le plus important dans '{topic}' ?",
            "options": ["La théorie seule suffit", "La pratique régulière", "Mémoriser par cœur", "Regarder des vidéos"],
            "correct": 1,
            "explication": "La pratique régulière est toujours la clé de la maîtrise d'un sujet."
        })


@app.route("/api/generate-session-plan", methods=["POST"])
def generate_session_plan():
    """L'admin crée une session → l'IA génère le plan complet adapté au cours"""
    data       = request.json or {}
    subject    = data.get("subject", "Formation")
    fmt        = data.get("format", "session unique")
    level      = data.get("level", "Tous niveaux")
    course_data = data.get("course_data", {})

    # Extraire les chapitres du cours si disponible
    chapitres_str = ""
    if course_data.get("chapitres"):
        chapitres_str = "\n".join([
            f"- {c.get('titre', '')}"
            for c in course_data["chapitres"][:6]
        ])

    system = f"""Tu es un expert en ingénierie pédagogique qui conçoit des plans de formation.

Sujet : {subject}
Format : {fmt}
Niveau : {level}
{f"Chapitres du cours associé :\n{chapitres_str}" if chapitres_str else ""}

Génère un plan de session réaliste et engageant en JSON :
{{
  "plan": [
    {{"time": "00:00", "topic": "Nom précis du module", "type": "lesson"}},
    ...
  ]
}}

Types : lesson (leçon), challenge (QCM interactif), quiz (évaluation), break (pause)
Format attendu selon "{fmt}" :
- session unique : 6-8 étapes sur 2h
- 1h/jour : 5 étapes sur 1h
- 2h/semaine : 6-7 étapes sur 2h
- 30h/mois : 8-10 étapes sur plusieurs semaines

Les topics doivent être SPÉCIFIQUES au sujet "{subject}", pas génériques."""

    result = gpt(system,
                 [{"role": "user", "content": f"Plan pour : {subject}"}],
                 temperature=0.7, max_tokens=1000, json_mode=True)
    try:
        data_r = json.loads(result)
        if data_r.get("plan") and len(data_r["plan"]) > 0:
            return jsonify(data_r)
    except:
        pass

    # Fallback spécifique au sujet
    return jsonify({"plan": [
        {"time": "00:00", "topic": f"Introduction à {subject}", "type": "lesson"},
        {"time": "00:20", "topic": f"Fondamentaux de {subject}", "type": "lesson"},
        {"time": "00:45", "topic": "Challenge QCM", "type": "challenge"},
        {"time": "01:00", "topic": "Pause", "type": "break"},
        {"time": "01:10", "topic": f"Approfondissement — {subject}", "type": "lesson"},
        {"time": "01:45", "topic": "Quiz d'évaluation", "type": "quiz"}
    ]})


@app.route("/api/generate-quiz", methods=["POST"])
def generate_quiz():
    """Génère un quiz complet pour un cours"""
    data        = request.json or {}
    subject     = data.get("subject", "ce cours")
    level       = data.get("level", "Débutant")
    num         = min(int(data.get("num_questions", 5)), 10)
    course_data = data.get("course_data", {})

    # Contexte du cours
    chapitres_str = ""
    if course_data.get("chapitres"):
        chapitres_str = "\n".join([
            f"- {c.get('titre', '')}: {', '.join(c.get('lecons', [])[:3])}"
            for c in course_data["chapitres"][:5]
        ])

    seed = random.randint(1000, 9999)
    system = f"""Tu es un expert en évaluation pédagogique.

Cours : {subject}
Niveau : {level}
{f"Contenu du cours :\n{chapitres_str}" if chapitres_str else ""}

Génère exactement {num} questions QCM DIFFÉRENTES et progressives en JSON :
{{
  "quiz": [
    {{
      "question": "Question précise ?",
      "options": ["A", "B", "C", "D"],
      "correct": 0,
      "explication": "Explication pédagogique de la bonne réponse"
    }}
  ]
}}

RÈGLES :
- Questions progressives (facile → difficile)
- Chaque question teste un concept DIFFÉRENT
- Les 4 options doivent être plausibles
- L'explication apprend quelque chose d'utile
- Seed anti-répétition : {seed}"""

    result = gpt(system,
                 [{"role": "user", "content": f"Génère {num} questions sur : {subject}"}],
                 temperature=0.8, max_tokens=2000, json_mode=True)
    try:
        quiz_data = json.loads(result)
        if quiz_data.get("quiz") and len(quiz_data["quiz"]) > 0:
            return jsonify(quiz_data)
    except:
        pass

    return jsonify({"quiz": [
        {
            "question": f"Quel est le concept fondamental de '{subject}' ?",
            "options": ["La mémorisation", "La pratique régulière", "La lecture seule", "Les diplômes"],
            "correct": 1,
            "explication": "La pratique régulière est la base de tout apprentissage efficace."
        }
    ]})


@app.route("/api/analyze-pdf", methods=["POST"])
def analyze_pdf():
    """Analyse un PDF et génère résumé + chapitres + quiz complet"""
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier reçu"}), 400

    file  = request.files["file"]
    title = request.form.get("title", "Cours")
    level = request.form.get("level", "Débutant")

    # Extraire le texte du PDF
    try:
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        text = ""
        for i, page in enumerate(pdf_reader.pages):
            if i >= 25:  # Max 25 pages
                break
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except:
                continue
        text = text[:10000]  # Max 10000 chars
    except Exception as e:
        text = f"Document sur le sujet : {title}"

    if not text.strip():
        text = f"Document sur le sujet : {title}"

    system = f"""Tu es un expert en ingénierie pédagogique qui analyse des documents de formation.

Titre du cours : {title}
Niveau cible : {level}

Analyse ce document et génère une structure pédagogique complète en JSON :
{{
  "resume": "Résumé en 2-3 phrases percutantes",
  "duree_totale": "Xh30",
  "concepts_cles": ["Concept 1", "Concept 2", "Concept 3", "Concept 4", "Concept 5"],
  "objectifs": ["L'apprenant sera capable de...", "L'apprenant saura...", "L'apprenant pourra..."],
  "chapitres": [
    {{
      "titre": "Chapitre 1 — Titre précis",
      "lecons": ["Leçon 1.1", "Leçon 1.2", "Leçon 1.3"],
      "duree_minutes": 30
    }}
  ],
  "quiz": [
    {{
      "question": "Question précise basée sur le contenu ?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct": 0,
      "explication": "Explication pédagogique"
    }}
  ]
}}

IMPÉRATIF :
- 3 à 6 chapitres cohérents avec le contenu
- Exactement 10 questions de quiz basées sur le contenu réel
- Les concepts et objectifs doivent correspondre au document
- Durée réaliste selon la densité du contenu"""

    result = gpt(system,
                 [{"role": "user", "content": f"Analyse ce document :\n\n{text}"}],
                 temperature=0.6, max_tokens=3000, json_mode=True)

    try:
        analysis = json.loads(result)
        # Vérifications
        if not analysis.get("chapitres"):
            raise ValueError("Pas de chapitres")
        if not analysis.get("quiz"):
            raise ValueError("Pas de quiz")
        return jsonify(analysis)
    except Exception as e:
        return jsonify({
            "resume": f"Ce cours couvre les fondamentaux de {title} avec une approche progressive et pratique.",
            "duree_totale": "3h",
            "concepts_cles": [title, "Fondamentaux", "Pratique", "Application", "Maîtrise"],
            "objectifs": [
                f"Comprendre les bases de {title}",
                f"Appliquer les concepts de {title}",
                f"Maîtriser les techniques avancées"
            ],
            "chapitres": [
                {"titre": "Introduction et fondamentaux", "lecons": ["Présentation", "Concepts de base", "Premiers pas"], "duree_minutes": 30},
                {"titre": "Concepts intermédiaires", "lecons": ["Approfondissement", "Exemples pratiques", "Exercices"], "duree_minutes": 60},
                {"titre": "Applications avancées", "lecons": ["Cas pratiques", "Techniques avancées", "Projet final"], "duree_minutes": 60}
            ],
            "quiz": [
                {"question": f"Qu'est-ce que {title} ?", "options": ["Définition A", "Définition B", "Définition C", "Définition D"], "correct": 0, "explication": f"{title} est un domaine important à maîtriser."}
            ]
        })


@app.route("/api/transition", methods=["POST"])
def generate_transition():
    """Génère une phrase de transition entre les modules du live"""
    data       = request.json or {}
    from_module = data.get("from", "")
    to_module   = data.get("to", "")
    course      = data.get("course", "")

    system = """Tu es un animateur de formation dynamique.
Génère UNE SEULE phrase de transition courte et engageante (max 20 mots).
La phrase doit créer de l'enthousiasme pour la prochaine étape.
Pas de formalité excessive. Ton dynamique et positif."""

    msg = f"De '{from_module}' vers '{to_module}' dans le cours '{course}'"
    result = gpt(system, [{"role": "user", "content": msg}], temperature=0.9, max_tokens=60)

    return jsonify({"transition": result or f"Passons maintenant à : {to_module} !"})


@app.route("/api/community-moderate", methods=["POST"])
def moderate():
    """Modération automatique des posts communauté"""
    data = request.json or {}
    text = data.get("text", "")

    system = """Tu es un modérateur d'une communauté éducative bienveillante.
Analyse ce texte et réponds en JSON :
{"approved": true/false, "reason": "raison si refusé"}
Refuse uniquement si : spam évident, insultes graves, contenu inapproprié, hors-sujet total.
Sois indulgent pour les critiques constructives et questions directes."""

    result = gpt(system, [{"role": "user", "content": text}],
                 temperature=0.3, max_tokens=100, json_mode=True)
    try:
        return jsonify(json.loads(result))
    except:
        return jsonify({"approved": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

    try:
        return jsonify(json.loads(result))
    except:
        return jsonify({"approved": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
