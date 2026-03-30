from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import os, json, random, io
from openai import OpenAI

app = Flask(__name__)
CORS(app, origins="*")
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"

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
    d = request.json or {}
    question = d.get("question","").strip()
    course_title = d.get("course_title","ce cours")
    course_ctx = d.get("course_context","")
    history = d.get("history", [])
    current_mod = d.get("current_module","")
    chapitres = d.get("chapitres",[])
    concepts = d.get("concepts_cles",[])
    level = d.get("level","Tous niveaux")

    if not question:
        return jsonify({"error":"Question manquante"}), 400

    seed = random.randint(1000,9999)
    ctx = f"Cours: {course_title}\nNiveau: {level}"
    if course_ctx: ctx += f"\nDescription: {course_ctx}"
    if current_mod: ctx += f"\nModule actuel: {current_mod}"
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
5. 3-6 phrases maximum
6. Sois encourageant et précis
7. Ne répète jamais les mêmes réponses (seed:{seed})"""

    msgs = [{"role":m["role"],"content":m["content"]} for m in history[-6:] if m.get("role") in ("user","assistant")]
    msgs.append({"role":"user","content":question})

    answer = gpt(system, msgs, temperature=0.85, max_tokens=600)
    if not answer or len(answer) < 10:
        answer = f"Excellente question sur **{course_title}** ! Ce concept est important. Peux-tu préciser ce que tu n'as pas compris ?"
    return jsonify({"answer": answer})

@app.route("/api/teach", methods=["POST"])
def teach():
    d = request.json or {}
    topic = d.get("topic","ce sujet")
    ttype = d.get("type","lesson")
    level = d.get("level","Tous niveaux")
    course_data = d.get("course_data",{})
    seed = random.randint(1000,9999)

    if ttype == "lesson":
        chaps_str = ""
        if course_data.get("chapitres"):
            chaps_str = "\n".join([f"- {c.get('titre','')}" for c in course_data["chapitres"][:3]])

        system = f"""Tu es un professeur IA dynamique sur Learnova.
Cours: {course_data.get('titre', topic)} | Module: {topic} | Niveau: {level}
{f"Chapitres: {chaps_str}" if chaps_str else ""}
Génère une leçon d'introduction engageante (6-9 phrases). Seed:{seed}"""
        content = gpt(system, [{"role":"user","content":f"Enseigne: {topic}"}], temperature=0.85, max_tokens=700)
        if not content:
            content = f"Explorons maintenant **{topic}**. Posez vos questions !"
        return jsonify({"content": content, "type": "lesson"})

    elif ttype in ("challenge","quiz"):
        system = f"""Tu crées des challenges QCM pour Learnova sur {topic}. Seed:{seed}"""
        result = gpt(system,[{"role":"user","content":f"Challenge sur: {topic}"}],temperature=0.9,max_tokens=400,json_mode=True)
        try:
            ch = json.loads(result)
            return jsonify(ch)
        except:
            return jsonify({"titre":"Challenge!","question":"Prêt ?","options":["A","B","C","D"],"correct":1,"explication":"..."})

@app.route("/api/generate-session-plan", methods=["POST"])
def gen_plan():
    d = request.json or {}
    subject = d.get("subject","Formation")
    system = f"Tu conçois des plans de formation pour {subject}."
    result = gpt(system,[{"role":"user","content":f"Plan pour: {subject}"}],temperature=0.7,max_tokens=800,json_mode=True)
    try:
        data = json.loads(result)
        return jsonify(data)
    except:
        return jsonify({"plan":[{"time":"00:00","topic":"Introduction","type":"lesson"}]})

@app.route("/api/generate-quiz", methods=["POST"])
def gen_quiz():
    d = request.json or {}
    subject = d.get("subject","ce cours")
    system = f"Tu crées des quiz pour {subject}."
    result = gpt(system,[{"role":"user","content":f"Quiz sur: {subject}"}],temperature=0.8,max_tokens=2000,json_mode=True)
    try:
        data = json.loads(result)
        return jsonify(data)
    except:
        return jsonify({"quiz":[]})

@app.route("/api/analyze-pdf", methods=["POST"])
def analyze_pdf():
    if "file" not in request.files:
        return jsonify({"error":"Aucun fichier"}), 400

    file = request.files["file"]
    title = request.form.get("title","Cours")
    
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file.read()))
        text = ""
        for i, page in enumerate(reader.pages):
            if i >= 10: break
            text += (page.extract_text() or "") + "\n"
        text = text[:8000]
    except:
        text = f"Document sur: {title}"

    system = "Tu analyses des documents pédagogiques pour Learnova."
    ai_response = gpt(system,[{"role":"user","content":f"Analyse:\n\n{text}"}],temperature=0.6,max_tokens=3000,json_mode=True)
    
    try:
        data = json.loads(ai_response)
        return jsonify(data)
    except:
        return jsonify({"resume": "Erreur d'analyse du document."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
