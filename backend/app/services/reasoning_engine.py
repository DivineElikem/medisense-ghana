from typing import Dict, List, Any, Optional, Tuple
from app.models.session import SessionState, Question, QuestionType, Stage
import json
import os
import random

class ReasoningEngine:
    def __init__(self, kb_path: str):
        with open(kb_path, "r") as f:
            self.kb = json.load(f)
        
        self.baseline_questions = self.kb.get("baseline_questions", [
            {"id": "age", "text": "What is your age?", "type": "number"},
            {"id": "sex", "text": "What is your sex?", "type": "choice", "options": ["Male", "Female", "Other"]},
            {"id": "temperature", "text": "Do you know your current body temperature?", "type": "number", "unit": "°C"}
        ])

    def evaluate_triage(self, state: SessionState) -> Optional[Dict[str, Any]]:
        for rule in self.kb["triage_rules"]:
            condition_met = True
            for key, val in rule["if"].items():
                if state.answers.get(key) != val:
                    condition_met = False
                    break
            if condition_met:
                return rule["then"]
        return None

    def get_duration_weight(self, duration_id: str) -> float:
        """Get weight multiplier for symptom duration."""
        for opt in self.kb.get("duration_options", []):
            if opt["id"] == duration_id:
                return opt["weight"]
        return 1.0

    def get_severity_weight(self, severity_id: str) -> float:
        """Get weight multiplier for symptom severity."""
        for opt in self.kb.get("severity_options", []):
            if opt["id"] == severity_id:
                return opt["weight"]
        return 1.0

    def calculate_probabilities(self, state: SessionState) -> Dict[str, float]:
        scores = {}
        region = self._get_region_id(state.answers.get("region"))
        
        for disease in self.kb["diseases"]:
            # Base score from prevalence (with regional adjustment)
            base_prevalence = disease["prevalence"]
            regional_mult = disease.get("regional_prevalence", {}).get(region, 1.0)
            score = base_prevalence * regional_mult
            
            # Symptom-based scoring with duration/severity
            for symptom_id, weight in disease["symptoms"].items():
                answer = state.answers.get(symptom_id)
                if answer is True:
                    base_boost = 1 + weight
                    
                    # Apply duration multiplier if available
                    details = state.symptom_details.get(symptom_id, {})
                    duration_mult = self.get_duration_weight(details.get("duration", ""))
                    severity_mult = self.get_severity_weight(details.get("severity", ""))
                    
                    score *= base_boost * duration_mult * severity_mult
                elif answer is False:
                    score *= (1 - weight * 0.5)
                # "unknown" answers don't modify the score
            
            # Apply symptom combination boosts
            combo_boost = self._evaluate_combinations(disease, state)
            score *= combo_boost
            
            # Apply rule-out logic (negative symptoms reduce probability)
            rule_out_factor = self._apply_rule_outs(disease, state)
            score *= rule_out_factor
            
            # Risk factor weighting
            risk_factors = disease.get("risk_factors", {})
            for factor_id, factor_weight in risk_factors.items():
                answer = state.answers.get(factor_id)
                if answer is True:
                    score *= (1 + factor_weight * 0.5)
            
            scores[disease["name"]] = max(score, 0.001)
        
        # Normalize to sum to 1
        total = sum(scores.values())
        if total > 0:
            for name in scores:
                scores[name] = round(scores[name] / total, 3)
        
        return dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))

    def _get_region_id(self, region_answer: Optional[str]) -> str:
        """Convert region answer to region ID."""
        if not region_answer:
            return "temperate"  # Default
        region_map = {
            "Tropical / Africa / Southeast Asia": "tropical",
            "South Asia (India, Pakistan)": "south_asia",
            "Temperate (Europe / N. America)": "temperate"
        }
        return region_map.get(region_answer, "temperate")

    def _evaluate_combinations(self, disease: Dict[str, Any], state: SessionState) -> float:
        """Check for symptom combinations and return boost multiplier."""
        combinations = disease.get("symptom_combinations", [])
        max_boost = 1.0
        
        for combo in combinations:
            symptoms_required = combo.get("symptoms", [])
            # Check if all symptoms in combination are present
            all_present = all(state.answers.get(s) is True for s in symptoms_required)
            if all_present:
                max_boost = max(max_boost, combo.get("boost", 1.0))
        
        return max_boost

    def _apply_rule_outs(self, disease: Dict[str, Any], state: SessionState) -> float:
        """Apply rule-out logic: if a symptom is explicitly False, reduce probability."""
        rules_out = disease.get("rules_out", {})
        factor = 1.0
        
        for symptom_id, reduction in rules_out.items():
            # Only apply if symptom is explicitly False (not unknown)
            if state.answers.get(symptom_id) is False:
                factor *= (1.0 - reduction)
        
        return max(factor, 0.1)  # Never reduce by more than 90%


    def get_symptom_mapping(self, state: SessionState) -> Dict[str, List[str]]:
        """Returns which user symptoms match each candidate condition."""
        mapping = {}
        for disease in self.kb["diseases"]:
            matched = []
            for symptom_id in disease["symptoms"].keys():
                if state.answers.get(symptom_id) is True:
                    # Get human-readable symptom name
                    symptom_data = next((s for s in self.kb["symptoms"] if s["id"] == symptom_id), None)
                    if symptom_data:
                        # Build symptom text with details in parentheses
                        symptom_text = symptom_id.replace("_", " ").title()
                        details = state.symptom_details.get(symptom_id, {})
                        
                        # Collect detail parts
                        detail_parts = []
                        if details.get("severity"):
                            detail_parts.append(details["severity"])
                        if details.get("duration"):
                            duration_text = next((d["text"] for d in self.kb.get("duration_options", []) 
                                                  if d["id"] == details["duration"]), "")
                            if duration_text:
                                detail_parts.append(duration_text.lower())
                        
                        # Add details in parentheses if any
                        if detail_parts:
                            symptom_text += f" ({', '.join(detail_parts)})"
                        
                        matched.append(symptom_text)
            if matched:
                mapping[disease["name"]] = matched
        return mapping

    def get_condition_details(self, condition_name: str) -> Dict[str, Any]:
        """Get warning signs and recommended tests for a condition."""
        for disease in self.kb["diseases"]:
            if disease["name"] == condition_name:
                return {
                    "warning_signs": disease.get("warning_signs", []),
                    "recommended_tests": disease.get("recommended_tests", [])
                }
        return {"warning_signs": [], "recommended_tests": []}

    def get_matched_combinations(self, state: SessionState) -> List[str]:
        """Return list of matched symptom combinations for transparency."""
        matched = []
        for disease in self.kb["diseases"]:
            combinations = disease.get("symptom_combinations", [])
            for combo in combinations:
                symptoms_required = combo.get("symptoms", [])
                all_present = all(state.answers.get(s) is True for s in symptoms_required)
                if all_present:
                    combo_name = combo.get("name", " + ".join(symptoms_required))
                    matched.append(f"{disease['name']}: {combo_name}")
        return matched

    def get_empathy_statement(self) -> str:
        """Get a random empathy statement for conversational warmth."""
        statements = self.kb.get("empathy_statements", [])
        if statements:
            return random.choice(statements)
        return ""

    def get_best_next_symptom(self, state: SessionState) -> Optional[Dict[str, Any]]:
        """Finds the most relevant symptom from KB that hasn't been asked yet."""
        current_probs = self.calculate_probabilities(state)
        candidates = [d for d in self.kb["diseases"] if current_probs.get(d["name"], 0) > 0.05]
        
        if not candidates:
            candidates = sorted(self.kb["diseases"], key=lambda x: x["prevalence"], reverse=True)

        symptom_scores = {}
        for disease in candidates:
            prob = current_probs.get(disease["name"], disease["prevalence"])
            for symptom_id, weight in disease["symptoms"].items():
                if symptom_id not in state.answers and symptom_id not in state.asked_symptoms:
                    symptom_data = next((s for s in self.kb["symptoms"] if s["id"] == symptom_id), None)
                    info_gain = symptom_data.get("information_gain", 0.5) if symptom_data else 0.5
                    symptom_scores[symptom_id] = symptom_scores.get(symptom_id, 0) + (weight * prob * info_gain)

        if not symptom_scores:
            return None

        best_id = max(symptom_scores, key=symptom_scores.get)
        symptom = next((s for s in self.kb["symptoms"] if s["id"] == best_id), None)
        return symptom

    def get_follow_up_question(self, symptom_id: str, follow_up_type: str) -> Optional[Question]:
        """Generate a follow-up question for duration or severity."""
        symptom = next((s for s in self.kb["symptoms"] if s["id"] == symptom_id), None)
        if not symptom or "follow_up" not in symptom:
            return None
        
        follow_up = symptom["follow_up"]
        
        if follow_up_type == "duration" and follow_up.get("duration"):
            options = [opt["text"] for opt in self.kb.get("duration_options", [])]
            return Question(
                id=f"{symptom_id}_duration",
                text=follow_up.get("duration_text", f"How long have you had the {symptom_id.replace('_', ' ')}?"),
                type=QuestionType.CHOICE,
                options=options
            )
        elif follow_up_type == "severity" and follow_up.get("severity"):
            options = [opt["text"] for opt in self.kb.get("severity_options", [])]
            return Question(
                id=f"{symptom_id}_severity",
                text=follow_up.get("severity_text", f"How severe is the {symptom_id.replace('_', ' ')}?"),
                type=QuestionType.CHOICE,
                options=options
            )
        return None

    def select_next_question(self, state: SessionState) -> Optional[Question]:
        # Check for pending follow-up questions first
        if state.pending_follow_up:
            symptom_id = state.pending_follow_up["symptom_id"]
            follow_up_type = state.pending_follow_up["type"]
            return self.get_follow_up_question(symptom_id, follow_up_type)
        
        if state.stage == Stage.TRIAGE:
            triage_ids = ["difficulty_breathing", "chest_pain"]
            for tid in triage_ids:
                if tid not in state.answers:
                    symptom = next((s for s in self.kb["symptoms"] if s["id"] == tid), None)
                    if symptom:
                        return Question(**{k: v for k, v in symptom.items() 
                                          if k in ["id", "text", "type", "options", "unit"]})
            
        elif state.stage == Stage.BASELINE:
            for q in self.baseline_questions:
                if q["id"] not in state.answers:
                    return Question(**{k: v for k, v in q.items() 
                                      if k in ["id", "text", "type", "options", "unit"]})
                    
        elif state.stage == Stage.CHIEF_COMPLAINT:
            if "chief_complaint" not in state.answers:
                return Question(
                    id="chief_complaint",
                    text="What is the main problem bothering you right now?",
                    type=QuestionType.TEXT
                )
        
        elif state.stage == Stage.FOLLOW_UP:
            symptom = self.get_best_next_symptom(state)
            if symptom:
                return Question(**{k: v for k, v in symptom.items() 
                                  if k in ["id", "text", "type", "options", "unit"]})

        return None

# Singleton
KB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "knowledge_base.json")
reasoning_engine = ReasoningEngine(KB_PATH)
