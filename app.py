from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import os, json, random, io

from openai import OpenAI

app   = Flask(__name__)
CORS(app, origins="*")
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL  = "gpt-4o-mini"

def gpt(system, messages, temperature=0.8, max_tokens=1000, json_mode=False):
    try:
        kwargs = {
            "model": MODEL,
            "messages": [{"role":"system","content":system}] + messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if json_mode:
            kwargs["response_format"] = {"type":"json_object"}
        r = client.chat.completions.create(**kwargs)
        return r.choices[0].message.content
    except Exception as e:
        print(f"GPT error: {e}")
        return None

@app.route("/")
def home():
    return jsonify({"status":"ok","message":"Learnova Backend V4","model":MODEL})

@app.route("/api/ask-ai", methods=["POST"])
def ask_ai():
    d             = request.json or {}
    question      = d.get("question","").strip()
    course_title  = d.get("course_title","ce cours")
    course_ctx    = d.get("course_context","")
    history       = d.get("history", [])
    current_mod   = d.get("current_module","")
    chapitres     = d.get("chapitres",[])
    concepts      = d.get("concepts_cles",[])
    level         = d.get("level","Tous niveaux")

    if not question:
        return jsonify({"error":"Question manquante"}), 400

    seed = random.randint(1000,9999)
    ctx  = f"Cours: {course_title}\nNiveau: {level}"
    if course_ctx:   ctx += f"\nDescription: {course_ctx}"
    if current_mod:  ctx += f"\nModule actuel: {current_mod}"
    if chapitres:
        titres = [c.get('titre','') for c in chapitres[:4] if c.get('titre')]
        if titres: ctx += f"\nChapitres: {', '.join(titres)}"
    if concepts:
        ctx += f"\nConcepts clés: {', '.join(concepts[:6])}"

    system = f"""Tu es un professeur IA expert et pédagogue pour Learnova.

{ctx}

RÈGLES :
1. Réponds DIRECTEMENT et PRÉCISÉMENT à la question posée
2. Adapte ta réponse au niveau "{level}"
3. Utilise des exemples concrets liés à "{course_title}"
4. Format: **gras** pour les points clés, `code` pour le technique
5. 3-6 phrases maximum (sauf si la question nécessite plus)
6. Sois encourageant et précis — jamais vague
7. Ne répète jamais les mêmes réponses (seed:{seed})"""

    msgs = [{"role":m["role"],"content":m["content"]} for m in history[-6:] if m.get("role") in ("user","assistant")]
    msgs.append({"role":"user","content":question})

    answer = gpt(system, msgs, temperature=0.85, max_tokens=600)
    if not answer or len(answer) < 10:
        answer = f"Excellente question sur **{course_title}** ! Ce concept est important. Peux-tu préciser ce que tu n'as pas compris ?"
    return jsonify({"answer": answer})

@app.route("/api/teach", methods=["POST"])
def teach():
    d           = request.json or {}
    topic       = d.get("topic","ce sujet")
    ttype       = d.get("type","lesson")
    level       = d.get("level","Tous niveaux")
    course_data = d.get("course_data",{})
    seed        = random.randint(1000,9999)

    if ttype == "lesson":
        chaps_str = ""
        if course_data.get("chapitres"):
            chaps_str = "\n".join([f"- {c.get('titre','')}" for c in course_data["chapitres"][:3]])

        system = f"""Tu es un professeur IA dynamique sur Learnova.
Cours: {course_data.get('titre', topic)} | Module: {topic} | Niveau: {level}
{f"Chapitres: {chaps_str}" if chaps_str else ""}

Génère une leçon d'introduction engageante (6-9 phrases).
- Accroche captivante
- Explication claire du concept principal
- Exemple concret
- Points clés à retenir
- Utilise **gras** et `code` pour le technique
- Seed:{seed} (varie chaque réponse)"""
        content = gpt(system, [{"role":"user","content":f"Enseigne: {topic}"}], temperature=0.85, max_tokens=700)
        if not content:
            content = f"Explorons maintenant **{topic}**. Ce module est essentiel dans {course_data.get('titre','ce cours')}. Posez vos questions !"
        return jsonify({"content": content, "type": "lesson"})

    elif ttype in ("challenge","quiz"):
        system = f"""Tu crées des challenges QCM engageants pour Learnova.
Cours: {course_data.get('titre', topic)} | Module: {topic} | Niveau: {level}

JSON exact:
{{"titre":"Challenge — [titre court]","question":"Question précise?","options":["A","B","C","D"],"correct":1,"explication":"Explication 2-3 phrases"}}
- correct = index 0-3
- 4 options plausibles, une seule correcte
- Lié directement à "{topic}"
- Seed:{seed}"""
        result = gpt(system,[{"role":"user","content":f"Challenge sur: {topic}"}],temperature=0.9,max_tokens=400,json_mode=True)
        try:
            ch = json.loads(result)
            if ch.get("question") and ch.get("options") and len(ch["options"])==4:
                return jsonify(ch)
        except: pass
        return jsonify({"titre":f"Challenge!","question":f"Qu'est-ce qui est essentiel dans '{topic}'?","options":["La théorie","La pratique","La mémoire","Les livres"],"correct":1,"explication":"La pratique régulière est la clé de la maîtrise."})

@app.route("/api/generate-session-plan", methods=["POST"])
def gen_plan():
    d           = request.json or {}
    subject     = d.get("subject","Formation")
    fmt         = d.get("format","session unique")
    level       = d.get("level","Tous niveaux")
    course_data = d.get("course_data",{})

    chaps_str = ""
    if course_data.get("chapitres"):
        chaps_str = "\n".join([f"- {c.get('titre','')}" for c in course_data["chapitres"][:5]])

    system = f"""Tu conçois des plans de formation pédagogiques pour Learnova.
Sujet: {subject} | Format: {fmt} | Niveau: {level}
{f"Chapitres du cours lié:\n{chaps_str}" if chaps_str else ""}

JSON:
{{"plan":[{{"time":"00:00","topic":"Titre précis du module","type":"lesson"}}]}}
Types: lesson, challenge, quiz, break
- session unique: 6-7 étapes ~2h
- 1h/jour: 5 étapes ~1h
- 2h/semaine: 6-7 étapes ~2h
- 30h/mois: 8 étapes sur plusieurs semaines
Topics SPÉCIFIQUES à "{subject}", pas génériques."""

    result = gpt(system,[{"role":"user","content":f"Plan pour: {subject}"}],temperature=0.7,max_tokens=800,json_mode=True)
    try:
        data = json.loads(result)
        if data.get("plan") and len(data["plan"])>0:
            return jsonify(data)
    except: pass

    return jsonify({"plan":[
        {"time":"00:00","topic":f"Introduction à {subject}","type":"lesson"},
        {"time":"00:20","topic":f"Fondamentaux de {subject}","type":"lesson"},
        {"time":"00:45","topic":"Challenge QCM","type":"challenge"},
        {"time":"01:00","topic":"Pause","type":"break"},
        {"time":"01:10","topic":f"Approfondissement — {subject}","type":"lesson"},
        {"time":"01:50","topic":"Quiz final","type":"quiz"}
    ]})

@app.route("/api/generate-quiz", methods=["POST"])
def gen_quiz():
    d           = request.json or {}
    subject     = d.get("subject","ce cours")
    level       = d.get("level","Débutant")
    num         = min(int(d.get("num_questions",5)),10)
    course_data = d.get("course_data",{})
    seed        = random.randint(1000,9999)

    chaps_str = ""
    if course_data.get("chapitres"):
        chaps_str = "\n".join([f"- {c.get('titre','')}: {', '.join(c.get('lecons',[])[:2])}" for c in course_data["chapitres"][:4]])

    system = f"""Tu crées des quiz pédagogiques pour Learnova.
Cours: {subject} | Niveau: {level}
{f"Contenu:\n{chaps_str}" if chaps_str else ""}

JSON:
{{"quiz":[{{"question":"Question?","options":["A","B","C","D"],"correct":0,"explication":"Explication"}}]}}
- Exactement {num} questions progressives (facile→difficile)
- Chaque question teste un concept DIFFÉRENT
- correct = index 0-3
- Seed:{seed}"""

    result = gpt(system,[{"role":"user","content":f"{num} questions sur: {subject}"}],temperature=0.8,max_tokens=2000,json_mode=True)
    try:
        data = json.loads(result)
        if data.get("quiz") and len(data["quiz"])>0:
            return jsonify(data)
    except: pass

    return jsonify({"quiz":[{"question":f"Concept principal de '{subject}'?","options":["Théorie seule","Pratique régulière","Mémorisation","Diplômes"],"correct":1,"explication":"La pratique régulière est la base de tout apprentissage."}]})

@app.route("/api/analyze-pdf", methods=["POST"])
def analyze_pdf():
    if "file" not in request.files:
        return jsonify({"error":"Aucun fichier"}), 400

    file  = request.files["file"]
    title = request.form.get("title","Cours")
    level = request.form.get("level","Débutant")

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        text = ""
        for i, page in enumerate(reader.pages):
            if i >= 20: break
            try: text += (page.extract_text() or "") + "\n"
            except: continue
        text = text[:9000]
    except Exception as e:
        text = f"Document sur: {title}"

    if not text.strip():
        text = f"Document sur: {title}"

    system = f"""Tu analyses des documents pédagogiques pour Learnova.
Titre: {title} | Niveau: {level}

JSON:
{{"resume":"Résumé 2-3 phrases","duree_totale":"Xh30","concepts_cles":["C1","C2","C3","C4","C5"],"objectifs":["Obj1","Obj2","Obj3"],"chapitres":[{{"titre":"Chap 1","lecons":["L1","L2","L3"],"duree_minutes":30}}],"quiz":[{{"question":"Q?","options":["A","B","C","D"],"correct":0,"explication":"Expl"}}]}}

- 3-5 chapitres cohérents avec le contenu
- Exactement 10 questions de quiz
- Tout basé sur le contenu réel du document"""

    result = gpt(system,[{"role":"user","content":f"Analyse:\n\n{text}"}],temperature=0.6,max_tokens=3000,json_mode=True)
    try:
        data = json.loads(result)
        if data.get("chapitres") and data.get("quiz"):
            return jsonify(data)
    except: pass

    return jsonify({
        "resume":f"Ce cours couvre les fondamentaux de {title}.",
        "duree_totale":"3h",
        "concepts_cles":[title,"Fondamentaux","Pratique","Application","Maîtrise"],
        "objectifs":[f"Comprendre {title}",f"Appliquer {title}","Maîtriser les techniques"],
        "chapitres":[
            {"titre":"Introduction","lecons":["Présentation","Concepts de base"],"duree_minutes":30},
            {"titre":"Contenu principal","lecons":["Concepts clés","Exemples"],"duree_minutes":60},
            {"titre":"Applications","lecons":["Pratique","Projet final"],"duree_minutes":60}
        ],
        "quiz":[{"question":f"Qu'est-ce que {title}?","options":["Def A","Def B","Def C","Def D"],"correct":0,"explication":f"{title} est un domaine important."}]
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0", port=port, debug=False)

        return jsonify(json.loads(result))
    except:
        return jsonify({"approved": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
