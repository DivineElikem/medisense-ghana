# About Crystal AI Doctor - Technical Documentation

Crystal AI Doctor is a hybrid AI-driven medical symptom assessment tool. It combines **deterministic medical rules** (Probabilistic Engine) with **probabilistic language models** (LLM) to provide a safe, structured, and empathetic health assessment.

---

## 🏛️ Architecture Overview

The system is split into three main layers:

1.  **Frontend (Next.js/Tailwind)**: A responsive, chat-based interface that handles user input and displays visual diagnostic feedback (probability bars, urgency badges).
2.  **Backend (FastAPI)**: A stateful API that manages user sessions and coordinates between the reasoning engine and the AI.
3.  **AI Layer (Groq / Llama 3.1)**: Handles natural language tasks such as symptom extraction, question rephrasing, and clinical explanations.

---

## 🧠 The Reasoning Engine (How it Thinks)

Unlike a pure chatbot that might "hallucinate" a diagnosis, Crystal AI Doctor uses a **Knowledge-Base-First** approach.

### 1. The Knowledge Base (JSON)
All medical knowledge is stored in `backend/data/knowledge_base.json`. This file defines:
-   **Diseases**: Their prevalence, core symptoms, and associated weights.
-   **Triage Rules**: Emergency conditions that trigger immediate alerts.
-   **Regional Logic**: Adjustments for diseases like Malaria based on the user's location.

### 2. Probabilistic Scoring
The bot calculates the likelihood of diseases using a weighted scoring model:
-   **Base Score**: Starts with the disease's general prevalence in the population.
-   **Symptom Boosts**: If a user says "Yes" to a symptom, the disease's score is multiplied by its weight (e.g., Fever for Malaria is a x1.95 boost).
-   **Mandatory Symptoms**: Some diseases have "prerequisites." If a user denies all core symptoms of a disease (e.g., no cough for a cold), the score is decimated (x0.01).
-   **Incompatible Symptoms**: If a user reports a symptom rare for a disease (e.g., runny nose during Malaria), the score is penalized.

### 3. Adaptive Questioning (Information Gain)
Crystal AI Doctor doesn't ask the same questions every time. It uses a **Greedy Information Gain** algorithm to pick the "best" next question. It calculates which unasked symptom will most effectively "separate" the top disease candidates.

---

## 🤖 The Role of AI (LLM)

We use the **Llama 3.1-8B** model (via Groq) for three specific tasks:

1.  **Symptom Extraction**: When a user describes their problem in plain English (e.g., "My head is pounding and I feel hot"), the LLM extracts the structured IDs (`headache`, `fever`) that the math engine can understand.
2.  **Nurse Persona**: To avoid sounding robotic, the LLM rephrases clinical questions into warm, empathetic inquiries.
3.  **Clinical Explanation**: At the end of the session, the LLM analyzes the math results and explains *why* certain conditions are being considered in simple, non-jargon terms.

---

## 🚦 The Assessment Flow

1.  **Triage**: Immediate check for life-threatening signs (Difficulty breathing, chest pain).
2.  **Baseline**: Gathers vitals (Age, Region, Temperature, Heart Rate).
3.  **Chief Complaint**: Free-text entry where the user describes their issue.
4.  **Follow-Up**: The bot asks 8–12 targeted questions to narrow down the possibilities.
5.  **Explanation**: A short bridge explaining the bot's current "thinking."
6.  **Results**: A final report showing probabilities, urgency level (Low/Moderate/High), warning signs, and recommended next steps.

---

## 🛡️ Safety & Guardrails

Crystal AI Doctor is built with **safety as a priority**:
-   **No Diagnosis**: The system is legally and technically constrained to never say "You have X." It uses language like "Your symptoms are associated with..."
-   **Regex Guardrails**: A post-processing script checks every AI response for forbidden words (like "prescription," "take this dose," or "cure").
-   **Emergency Overrides**: If a triage rule is met, the AI is bypassed entirely to show a hardcoded emergency instruction.

---

## 🏛️ Context: Mission
Crystal AI Doctor is designed to empower healthcare accessibility globally. Its logic is tuned for precision across various regional contexts, with a particular strength in detecting patterns for common and critical health conditions.
