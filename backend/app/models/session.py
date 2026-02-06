from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from typing import List, Dict, Optional, Union, Any
from enum import Enum

class Stage(str, Enum):
    TRIAGE = "TRIAGE"
    BASELINE = "BASELINE"
    CHIEF_COMPLAINT = "CHIEF_COMPLAINT"
    FOLLOW_UP = "FOLLOW_UP"
    EXPLANATION = "EXPLANATION"
    RESULT = "RESULT"

class QuestionType(str, Enum):
    BOOLEAN = "boolean"
    CHOICE = "choice"
    NUMBER = "number"
    TEXT = "text"

class Question(BaseModel):
    id: str
    text: str
    type: QuestionType
    options: Optional[List[str]] = None
    unit: Optional[str] = None
    conditions: Optional[List[str]] = None

class SessionStartResponse(BaseModel):
    session_id: UUID
    message: str
    next_question: Question

class AnswerRequest(BaseModel):
    session_id: UUID
    question_id: str
    answer: Any

class AssessmentResult(BaseModel):
    name: str
    probability: float

class SessionResponse(BaseModel):
    session_id: UUID
    emergency: bool = False
    message: Optional[str] = None
    next_question: Optional[Question] = None
    result: Optional[Dict[str, Any]] = None
    progress: Optional[Dict[str, int]] = None  # {"current": 3, "estimated_total": 10}
    can_go_back: bool = False
    empathy_message: Optional[str] = None

class SessionState(BaseModel):
    session_id: UUID = Field(default_factory=uuid4)
    stage: Stage = Stage.TRIAGE
    answers: Dict[str, Any] = {}
    question_history: List[Dict[str, Any]] = []  # [{"id": "...", "text": "...", "answer": "..."}]
    asked_symptoms: List[str] = []  # Track IDs from KB to avoid repetition
    red_flags_triggered: List[str] = []
    candidate_conditions: Dict[str, float] = {}
    is_complete: bool = False
    
    # Progress tracking
    question_count: int = 0
    estimated_total_questions: int = 12
    
    # Symptom details (duration/severity)
    symptom_details: Dict[str, Dict[str, str]] = {}  # {"fever": {"duration": "1_3_days", "severity": "moderate"}}
    
    # Undo functionality
    answer_stack: List[Dict[str, Any]] = []  # Stack of {question_id, answer, stage} for undo
    
    # Pending follow-up questions
    pending_follow_up: Optional[Dict[str, Any]] = None  # {symptom_id, type: "duration"|"severity"}
    
    # Baseline context
    age: Optional[int] = None
    sex: Optional[str] = None
    temperature: Optional[float] = None
    chief_complaint: Optional[str] = None
