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

## 🏁 Getting Started

Follow these steps to get a local copy up and running.

### 1. Clone the repository
```bash
git clone https://github.com/DivineElikem/crystal-ai-doctor.git
cd crystal-ai-doctor
```

### 2. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Configure Environment Variables:**
Create a `.env` file in the `backend` directory:
```bash
cp .env.example .env
```
Open `.env` and add your [Groq API Key](https://console.groq.com/):
```text
GROQ_API_KEY=your_groq_api_key_here
```

**Run Backend:**
```bash
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup
Open a new terminal window:
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to see the application in action.

## 🌐 Deployment

- **Frontend**: Deployed on Vercel
- **Backend**: Deployed on Render

## 🏛️ Mission

Empowering healthcare accessibility through intelligent AI-driven assessment.
