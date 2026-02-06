from groq import Groq
import os
import json
import re
from typing import Dict, Any, List, Optional
from app.services.guardrails import guardrails

SYSTEM_PROMPT_MEDICAL_ASSISTANT = """
You are a medical symptom assessment assistant.

Your role is to help users understand possible medical conditions based on
reported symptoms as part of a clinical decision-support system.

STRICT RULES:
- You must NOT diagnose any disease.
- You must NOT state that the user has a condition.
- You must NOT give medical prescriptions, drug names, or dosages.
- You must NOT override emergency or safety decisions made by the system.
- You must use cautious, probabilistic language at all times.
- Always recommend professional medical evaluation when appropriate.
- If information is insufficient, clearly say so.

You are NOT a doctor.
You are assisting a structured medical assessment system.
"""

class LLMClient:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is required")
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.1-8b-instant"

    async def _call_llm(self, user_prompt: str, temperature: float = 0.2, max_tokens: int = 400) -> str:
        if not self.client:
            return ""
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_MEDICAL_ASSISTANT},
                    {"role": "user", "content": user_prompt}
                ],
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.9
            )
            output = chat_completion.choices[0].message.content
            
            # Post-processing Guardrails
            if not guardrails.validate_output(output):
                return guardrails.get_safe_fallback()
                
            return output
        except Exception as e:
            print(f"LLM Error: {str(e)}")
            return guardrails.get_safe_fallback()

    async def extract_symptoms_from_complaint(self, text: str, symptom_list: List[Dict[str, Any]]) -> List[str]:
        """Extracts known symptom IDs from free-text complaint."""
        # Build a clear ID list
        valid_ids = [s['id'] for s in symptom_list]
        symptom_descriptions = "\n".join([f"- {s['id']}" for s in symptom_list])
        
        # Common synonyms mapping
        synonym_map = {
            "weakness": "fatigue",
            "tired": "fatigue",
            "exhausted": "fatigue",
            "body aches": "muscle_pain",
            "body pain": "muscle_pain",
            "temperature": "fever",
            "high fever": "fever",
            "cold": "chills",
            "shivering": "chills",
            "stomach pain": "abdominal_pain",
            "belly pain": "abdominal_pain",
            "vomiting": "nausea",
            "throwing up": "nausea",
            "loose stool": "diarrhea",
            "rash": "skin_rash",
            "stuffy nose": "runny_nose",
            "congestion": "runny_nose",
            "throat pain": "sore_throat",
            "hard to breathe": "difficulty_breathing",
            "breathless": "difficulty_breathing",
            "sweaty": "sweating",
            "night sweats": "sweating"
        }
        
        prompt = f"""AVAILABLE SYMPTOM IDS (use ONLY these exact IDs):
{symptom_descriptions}

USER COMPLAINT: "{text}"

TASK: Extract which symptom IDs from the list above match what the user describes.
- "severe headache" → "headache"
- "high fever" or "temperature" → "fever"  
- "weakness" or "tired" → "fatigue"
- "loose stool" → "diarrhea"

Return ONLY a valid JSON array with matching IDs. Example: ["headache", "fever"]
If no symptoms match, return: []"""
        
        try:
            response = await self._call_llm(prompt, temperature=0.0)
            print(f"[DEBUG] Extraction response: {response}")
            
            # Find JSON list in response
            match = re.search(r"\[.*?\]", response, re.DOTALL)
            if match:
                extracted = json.loads(match.group(0))
                print(f"[DEBUG] Parsed extraction: {extracted}")
                
                # Validate and apply synonym mapping
                result = []
                for item in extracted:
                    item_lower = item.lower().strip()
                    # Direct match
                    if item_lower in valid_ids:
                        result.append(item_lower)
                    # Synonym mapping
                    elif item_lower in synonym_map:
                        result.append(synonym_map[item_lower])
                
                print(f"[DEBUG] Final extracted IDs: {result}")
                return list(set(result))  # Remove duplicates
            return []
        except Exception as e:
            print(f"[DEBUG] Extraction error: {e}")
            return []

    async def rephrase_nurse_question(self, symptom_text: str, history: List[Dict[str, Any]]) -> str:
        """Acting as a nurse, rephrases a clinical symptom into a warm question."""
        formatted_history = "\n".join([f"Q: {i['text']} A: {i['answer']}" for i in history if i["answer"] is not None])
        
        prompt = f"""
Persona: You are a calm, digital triage nurse.
Goal: Inquire about a clinical symptom in a gentle way.

Previous conversation history:
{formatted_history}

Clinical Symptom to check: "{symptom_text}"

TASK:
Rephrase the clinical symptom check into a natural, warm question.
Example: "Do you have a fever?" -> "Have you noticed your temperature running high lately?"

RULES:
- ONLY output the question text.
- Be extremely brief.
- Do NOT use medical jargon.
- Do NOT sound robotic.
"""
        response = await self._call_llm(prompt, temperature=0.5)
        if not response or response == guardrails.get_safe_fallback():
            return symptom_text # Fallback to original text if rephrasing fails
        return response.strip()

    async def generate_explanation(self, history: List[Dict[str, Any]], ranked_conditions: Dict[str, float]) -> str:
        """Explains the current thinking before showing results."""
        formatted_history = "\n".join([f"- {i['text']}: {i['answer']}" for i in history if i["answer"] is not None])
        
        prompt = f"""
Persona: You are a calm, digital triage nurse.
User context reported so far:
{formatted_history}

Preliminary logic assessment (weighted likelihoods): 
{json.dumps(ranked_conditions)}

TASK:
Briefly explain why we are looking into these possibilities. 
Mention that many conditions share similar early signs.
Do NOT give a diagnosis. 

Output should be warm and supportive. 60 words max.
"""
        response = await self._call_llm(prompt, temperature=0.3)
        return response.strip()

    async def explain_results(self, conditions_with_probabilities: Dict[str, float], key_symptoms: List[str]) -> str:
        prompt = f"""
Context:
You are explaining symptom assessment results to a non-medical user.

Possible conditions (NOT diagnoses):
{json.dumps(conditions_with_probabilities)}

Symptoms reported by the user:
{json.dumps(key_symptoms)}

Your task:
Explain in clear, calm, and simple language why these conditions are being
considered.

RULES:
- Do NOT say the user has any condition.
- Use phrases such as "may be associated with" or "can sometimes cause".
- Keep the explanation reassuring and neutral.
- Avoid medical jargon.
- Maximum of 4 short paragraphs.
"""
        return await self._call_llm(prompt, max_tokens=400)

    async def generate_final_summary(self, final_conditions: Dict[str, float], urgency: str) -> str:
        prompt = f"""
You are summarizing a medical symptom assessment.

Urgency: {urgency}
Top conditions (probabilities, not diagnoses): {json.dumps(final_conditions)}

Write a 2-3 sentence summary that:
- Explains why these conditions are being considered
- Recommends next steps based on urgency
- Uses calm, supportive language

RULES:
- No diagnosis statements
- No medication names  
- Max 50 words
"""
        return await self._call_llm(prompt, max_tokens=150)

# Singleton
llm_client = LLMClient()
