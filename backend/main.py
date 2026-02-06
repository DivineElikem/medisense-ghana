from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.models.session import SessionStartResponse, AnswerRequest, SessionResponse, Question, QuestionType, Stage
from app.services.session_manager import session_manager
from app.services.reasoning_engine import reasoning_engine
from uuid import UUID
import json
import os

# Load environment variables
load_dotenv()

app = FastAPI(title="Medical Symptom Assessment Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/session/start", response_model=SessionStartResponse)
async def start_session():
    session = session_manager.create_session()
    
    # Introduce the bot and disclaimer
    message = "I can help you assess your symptoms. This is not a medical diagnosis."
    
    # Always start with Triage
    session.stage = Stage.TRIAGE
    session.question_count = 1
    next_q = reasoning_engine.select_next_question(session)
    
    if next_q:
        session.question_history.append({"id": next_q.id, "text": next_q.text, "answer": None})
        
    return SessionStartResponse(
        session_id=session.session_id,
        message=message,
        next_question=next_q
    )

@app.post("/session/undo", response_model=SessionResponse)
async def undo_answer(request: dict):
    """Undo the last answer and return the previous question."""
    session_id = UUID(request.get("session_id"))
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not session.answer_stack:
        raise HTTPException(status_code=400, detail="No answers to undo")
    
    # Pop the last answer
    last_answer = session.answer_stack.pop()
    question_id = last_answer["question_id"]
    
    # Remove the answer
    if question_id in session.answers:
        del session.answers[question_id]
    
    # Remove from asked_symptoms if applicable
    if question_id in session.asked_symptoms:
        session.asked_symptoms.remove(question_id)
    
    # Handle follow-up undo
    if "_duration" in question_id or "_severity" in question_id:
        base_symptom = question_id.replace("_duration", "").replace("_severity", "")
        if base_symptom in session.symptom_details:
            detail_type = "duration" if "_duration" in question_id else "severity"
            if detail_type in session.symptom_details[base_symptom]:
                del session.symptom_details[base_symptom][detail_type]
    
    # Restore stage if needed
    session.stage = last_answer.get("stage", session.stage)
    session.question_count = max(1, session.question_count - 1)
    
    # Remove from question history
    if session.question_history:
        session.question_history.pop()
    
    # Get the question to re-ask
    next_q = reasoning_engine.select_next_question(session)
    
    return SessionResponse(
        session_id=session.session_id,
        next_question=next_q,
        progress={
            "current": session.question_count,
            "estimated_total": session.estimated_total_questions
        },
        can_go_back=len(session.answer_stack) > 0
    )

def get_duration_id(text: str) -> str:
    """Convert duration text to ID."""
    for opt in reasoning_engine.kb.get("duration_options", []):
        if opt["text"] == text:
            return opt["id"]
    return ""

def get_severity_id(text: str) -> str:
    """Convert severity text to ID."""
    for opt in reasoning_engine.kb.get("severity_options", []):
        if opt["text"] == text:
            return opt["id"]
    return ""

@app.post("/session/answer", response_model=SessionResponse)
async def submit_answer(request: AnswerRequest):
    session = session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Store for undo
    session.answer_stack.append({
        "question_id": request.question_id,
        "answer": request.answer,
        "stage": session.stage
    })
    
    # Handle follow-up answers (duration/severity)
    if "_duration" in request.question_id:
        base_symptom = request.question_id.replace("_duration", "")
        if base_symptom not in session.symptom_details:
            session.symptom_details[base_symptom] = {}
        session.symptom_details[base_symptom]["duration"] = get_duration_id(request.answer)
        
        # Clear pending and check for severity follow-up
        session.pending_follow_up = None
        symptom = next((s for s in reasoning_engine.kb["symptoms"] if s["id"] == base_symptom), None)
        if symptom and symptom.get("follow_up", {}).get("severity"):
            session.pending_follow_up = {"symptom_id": base_symptom, "type": "severity"}
    
    elif "_severity" in request.question_id:
        base_symptom = request.question_id.replace("_severity", "")
        if base_symptom not in session.symptom_details:
            session.symptom_details[base_symptom] = {}
        session.symptom_details[base_symptom]["severity"] = get_severity_id(request.answer)
        session.pending_follow_up = None
    
    else:
        # Regular answer handling
        if request.answer == "unknown" or request.answer is None:
            session.answers[request.question_id] = "unknown"
        else:
            session.answers[request.question_id] = request.answer
        
        # Record in history
        for entry in session.question_history:
            if entry["id"] == request.question_id:
                entry["answer"] = request.answer
                break
        
        # Check for follow-up on positive symptom answers
        if request.answer is True:
            symptom = next((s for s in reasoning_engine.kb["symptoms"] if s["id"] == request.question_id), None)
            if symptom and "follow_up" in symptom:
                follow_up = symptom["follow_up"]
                if follow_up.get("duration"):
                    session.pending_follow_up = {"symptom_id": request.question_id, "type": "duration"}
                elif follow_up.get("severity"):
                    session.pending_follow_up = {"symptom_id": request.question_id, "type": "severity"}
    
    # Mark symptom as asked
    if request.question_id in session.asked_symptoms:
        pass
    elif not ("_duration" in request.question_id or "_severity" in request.question_id):
        if request.question_id not in session.asked_symptoms:
            session.asked_symptoms.append(request.question_id)
    
    # 1. Evaluate Triage Rules - BEFORE any LLM calls
    triage_result = reasoning_engine.evaluate_triage(session)
    if triage_result:
        session.is_complete = True
        return SessionResponse(
            session_id=session.session_id,
            emergency=True,
            message=triage_result["message"]
        )
    
    # Extract symptoms from chief complaint
    if request.question_id == "chief_complaint":
        session.chief_complaint = request.answer
        from app.services.llm_client import llm_client
        extracted_ids = await llm_client.extract_symptoms_from_complaint(request.answer, reasoning_engine.kb["symptoms"])
        
        # Get valid symptom IDs from KB
        valid_ids = {s["id"] for s in reasoning_engine.kb["symptoms"]}
        
        print(f"[DEBUG] Chief complaint: {request.answer}")
        print(f"[DEBUG] Extracted symptoms: {extracted_ids}")
        
        for eid in extracted_ids:
            # Validate against KB
            if eid in valid_ids and eid not in session.answers:
                session.answers[eid] = True
                session.asked_symptoms.append(eid)
                
                # Check for follow-up questions on extracted symptoms
                symptom = next((s for s in reasoning_engine.kb["symptoms"] if s["id"] == eid), None)
                if symptom and "follow_up" in symptom:
                    # Only set pending if none already set
                    if not session.pending_follow_up:
                        follow_up = symptom["follow_up"]
                        if follow_up.get("duration"):
                            session.pending_follow_up = {"symptom_id": eid, "type": "duration"}
                        elif follow_up.get("severity"):
                            session.pending_follow_up = {"symptom_id": eid, "type": "severity"}
        
        print(f"[DEBUG] Symptoms marked as answered: {list(session.answers.keys())}")
        print(f"[DEBUG] Asked symptoms list: {session.asked_symptoms}")

    # Define Max Questions
    MAX_QUESTIONS = 12

    # Get empathy message occasionally
    empathy_msg = None
    if session.question_count > 3 and session.question_count % 4 == 0:
        empathy_msg = reasoning_engine.get_empathy_statement()

    # 2. Stage Management & Next Question Selection
    while not session.is_complete:
        # Check question count limit
        if len(session.answers) >= MAX_QUESTIONS and session.stage == Stage.FOLLOW_UP:
            session.stage = Stage.EXPLANATION

        next_q = reasoning_engine.select_next_question(session)
        
        if next_q:
            session.question_count += 1
            
            if next_q.id not in session.asked_symptoms and not ("_duration" in next_q.id or "_severity" in next_q.id):
                session.asked_symptoms.append(next_q.id)

            # Rephrase via LLM if in FOLLOW_UP (not for duration/severity)
            if session.stage == Stage.FOLLOW_UP and not ("_duration" in next_q.id or "_severity" in next_q.id):
                from app.services.llm_client import llm_client
                rephrased_text = await llm_client.rephrase_nurse_question(next_q.text, session.question_history)
                if "may not be able to provide a reliable assessment" not in rephrased_text:
                    next_q.text = rephrased_text

            session.question_history.append({"id": next_q.id, "text": next_q.text, "answer": None})
            
            return SessionResponse(
                session_id=session.session_id,
                next_question=next_q,
                progress={
                    "current": session.question_count,
                    "estimated_total": session.estimated_total_questions
                },
                can_go_back=len(session.answer_stack) > 1,
                empathy_message=empathy_msg
            )
        
        # Stage transitions
        if session.stage == Stage.TRIAGE:
            session.stage = Stage.BASELINE
        elif session.stage == Stage.BASELINE:
            session.stage = Stage.CHIEF_COMPLAINT
        elif session.stage == Stage.CHIEF_COMPLAINT:
            session.stage = Stage.FOLLOW_UP
        elif session.stage == Stage.FOLLOW_UP:
            session.stage = Stage.EXPLANATION
        
        elif session.stage == Stage.EXPLANATION:
            from app.services.llm_client import llm_client
            current_probs = reasoning_engine.calculate_probabilities(session)
            explanation = await llm_client.generate_explanation(session.question_history, current_probs)
            
            session.question_history.append({"id": "explanation", "text": explanation, "answer": "READ"})
            session.stage = Stage.RESULT
            
            return SessionResponse(
                session_id=session.session_id,
                message=explanation
            )
        
        elif session.stage == Stage.RESULT:
            session.is_complete = True
            session.candidate_conditions = reasoning_engine.calculate_probabilities(session)
            
            from app.services.llm_client import llm_client
            
            # Determine urgency
            max_prob = max(session.candidate_conditions.values()) if session.candidate_conditions else 0
            has_concerning_symptoms = any(session.answers.get(s) for s in ["fever", "chills", "abdominal_pain"])
            
            # Check severity for urgency boost
            has_severe = any(
                details.get("severity") == "severe"
                for details in session.symptom_details.values()
            )
            
            urgency = "LOW"
            if max_prob > 0.5 or has_concerning_symptoms:
                urgency = "MODERATE"
            if max_prob > 0.65 or has_severe:
                urgency = "HIGH"
            
            # Calculate confidence level
            sorted_probs = sorted(session.candidate_conditions.values(), reverse=True)
            top_prob = sorted_probs[0] if sorted_probs else 0
            second_prob = sorted_probs[1] if len(sorted_probs) > 1 else 0
            spread = top_prob - second_prob
            
            if top_prob > 0.5 and spread > 0.15:
                confidence = "HIGH"
            elif top_prob > 0.35:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"
            
            # Get matched combinations for transparency
            matched_combos = reasoning_engine.get_matched_combinations(session)
            
            # Recommendations based on urgency
            if urgency == "HIGH":
                recommendation = "Please visit a healthcare facility as soon as possible for further evaluation."
            elif urgency == "MODERATE":
                recommendation = "Consider scheduling a visit with a healthcare provider within the next 24-48 hours."
            else:
                recommendation = "Monitor your symptoms. If they persist or worsen, consult a healthcare provider."
            
            # Get symptom mapping and condition details
            symptom_mapping = reasoning_engine.get_symptom_mapping(session)
            
            # Get top condition details
            top_condition = list(session.candidate_conditions.keys())[0] if session.candidate_conditions else None
            condition_details = reasoning_engine.get_condition_details(top_condition) if top_condition else {}
            
            summary = await llm_client.generate_final_summary(session.candidate_conditions, urgency)
            
            # Build symptoms summary
            reported_symptoms = [
                sid.replace("_", " ").title() for sid, ans in session.answers.items()
                if ans is True and sid in [s["id"] for s in reasoning_engine.kb["symptoms"]]
            ]
            
            return SessionResponse(
                session_id=session.session_id,
                result={
                    "summary": summary,
                    "probabilities": session.candidate_conditions,
                    "urgency": urgency,
                    "confidence": confidence,
                    "recommendation": recommendation,
                    "symptom_mapping": symptom_mapping,
                    "matched_combinations": matched_combos,
                    "reported_symptoms": reported_symptoms,
                    "warning_signs": condition_details.get("warning_signs", []),
                    "recommended_tests": condition_details.get("recommended_tests", []),
                    "disclaimer": "This is not a medical diagnosis. Please consult a healthcare professional."
                }
            )

    return SessionResponse(session_id=session.session_id)

@app.get("/health")
async def health():
    return {"status": "ok"}
