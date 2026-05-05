# Crystal AI Doctor

AI-powered medical symptom triage assistant.

## 🏥 Features

- **Intelligent Symptom Assessment** - Conversational symptom collection
- **Probabilistic Diagnosis** - Weighted disease probability calculation
- **Global Context** - Adjusts for various regional disease prevalence
- **Confidence Scoring** - Transparent HIGH/MEDIUM/LOW confidence levels
- **Mobile Responsive** - Works on phones and desktops

## 🛠️ Tech Stack

- **Frontend**: Next.js 14, React, Tailwind CSS
- **Backend**: FastAPI, Python 3.11+
- **AI**: Groq LLM API (Llama 3.1)

## 🚀 Local Development

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000`

## 🌐 Deployment

- **Frontend**: Deployed on Vercel
- **Backend**: Deployed on Render

## 📝 Environment Variables

### Backend (.env)
```
GROQ_API_KEY=your_groq_api_key_here
```

## 🏛️ Mission

Empowering healthcare accessibility through intelligent AI-driven assessment.
