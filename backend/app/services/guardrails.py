import re
from typing import List, Optional

class Guardrails:
    def __init__(self):
        # Forbidden words and phrases
        self.forbidden_patterns = [
            r"\bdiagnos(?:ed|is|ing)\b",
            r"\byou have\b",
            r"\btake\b",
            r"\bdosage\b",
            r"\bmg\b",
            r"\bprescription\b",
            r"\bcure\b",
            r"\btreat\b"
        ]
        
        # Certainty claims
        self.certainty_patterns = [
            r"\bit is certain\b",
            r"\bdefinitely\b",
            r"\bconfirmed\b",
            r"\bi am sure\b"
        ]
        
        # Medication instruction regex (e.g., "500mg twice a day")
        self.medication_regex = re.compile(r"\d+\s?(mg|g|ml)\b", re.IGNORECASE)

    def validate_output(self, text: str) -> bool:
        """
        Returns True if the text passes all safety checks.
        """
        # Check forbidden patterns
        for pattern in self.forbidden_patterns + self.certainty_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        # Check medication regex
        if self.medication_regex.search(text):
            return False
            
        return True

    def get_safe_fallback(self) -> str:
        return "I may not be able to provide a reliable assessment based on the available information. It would be best to consult a qualified healthcare professional for further evaluation."

# Singleton
guardrails = Guardrails()
