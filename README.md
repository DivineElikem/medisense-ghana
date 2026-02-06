# Medisense Ghana

AI-powered medical symptom triage assistant for Ghana.

## 🏥 Features

- **Intelligent Symptom Assessment** - Conversational symptom collection
- **Probabilistic Diagnosis** - Bayesian-style disease probability calculation
- **Regional Awareness** - Adjusts for tropical disease prevalence in Ghana
- **Confidence Scoring** - Transparent HIGH/MEDIUM/LOW confidence levels
- **Mobile Responsive** - Works on phones and desktops

## 🛠️ Tech Stack

- **Frontend**: Next.js 14, React, Tailwind CSS
- **Backend**: FastAPI, Python 3.11+
- **AI**: Groq LLM API

## 🚀 Local Development

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your GROQ_API_KEY
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

## 🇬🇭 Ghana Science & Tech Explorer Prize

Built for GSTEP - empowering healthcare accessibility in Ghana.
