"""
Strict Intent Detector – Enforces Fixed JSON Format Based on Database Schema

This module provides strict intent detection that matches your database schema exactly:
- TASKS table expects: head (title), body
- PENDING_TASKS table expects: title, body
- All responses are validated against strict schemas

The validator ensures:
1. Exact field names match database columns
2. Types are always correct (string, not null, etc.)
3. No extra fields
4. No missing fields
5. Values are properly cleaned
"""

import json
import logging
from typing import TypedDict, Literal
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================

class IntentType(str, Enum):
    """Valid intent types."""
    CREATE_TASK = "create_task"
    NON_TASK = "non_task"
    UNCERTAIN = "uncertain"


@dataclass
class TaskIntentResponse:
    """
    Strict response format for CREATE_TASK intent.
    Maps directly to database schema:
    - head → TASKS.head (short descriptive title)
    - body → TASKS.body (detailed notes)
    """
    intent: Literal["create_task"]
    head: str              # Maps to TASKS.head
    body: str              # Maps to TASKS.body
    confidence: float      # 0.0 to 1.0
    reason: str           # Why this classification

    def __post_init__(self):
        """Validate on creation."""
        if not isinstance(self.head, str) or not self.head.strip():
            raise ValueError("head must be a non-empty string")
        if not isinstance(self.body, str):
            raise ValueError("body must be a string")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise ValueError("confidence must be a number")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not isinstance(self.reason, str):
            raise ValueError("reason must be a string")

    def to_dict(self) -> dict:
        """Convert to dictionary with exact field names."""
        return {
            "intent": self.intent,
            "head": self.head.strip(),
            "body": self.body.strip(),
            "confidence": float(self.confidence),
            "reason": self.reason.strip(),
        }


@dataclass
class NonTaskIntentResponse:
    """
    Strict response format for NON_TASK or UNCERTAIN intent.
    No task data is created for these intents.
    """
    intent: Literal["non_task", "uncertain"]
    confidence: float
    reason: str

    def __post_init__(self):
        """Validate on creation."""
        if self.intent not in ("non_task", "uncertain"):
            raise ValueError(f"intent must be 'non_task' or 'uncertain', got {self.intent}")
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise ValueError("confidence must be a number")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not isinstance(self.reason, str):
            raise ValueError("reason must be a string")

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "intent": self.intent,
            "confidence": float(self.confidence),
            "reason": self.reason.strip(),
        }


# ============================================================================
# STRICT VALIDATOR
# ============================================================================

class StrictIntentValidator:
    """
    Validates intent detection responses against strict schemas.
    Ensures all responses match database table structure exactly.
    """

    # Schema for CREATE_TASK intent
    CREATE_TASK_SCHEMA = {
        "required_fields": {"intent", "head", "body", "confidence", "reason"},
        "forbidden_fields": {"title", "task", "description"},  # Common mistakes
        "field_types": {
            "intent": str,
            "head": str,
            "body": str,
            "confidence": (int, float),
            "reason": str,
        },
        "constraints": {
            "intent": lambda x: x == "create_task",
            "head": lambda x: isinstance(x, str) and 0 < len(x.strip()) <= 500,
            "body": lambda x: isinstance(x, str) and 0 <= len(x.strip()) <= 2000,
            "confidence": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 1,
            "reason": lambda x: isinstance(x, str) and 0 <= len(x.strip()) <= 500,
        },
    }

    # Schema for NON_TASK/UNCERTAIN intent
    NON_TASK_SCHEMA = {
        "required_fields": {"intent", "confidence", "reason"},
        "forbidden_fields": {"head", "body", "title", "task"},  # Must not exist
        "field_types": {
            "intent": str,
            "confidence": (int, float),
            "reason": str,
        },
        "constraints": {
            "intent": lambda x: x in ("non_task", "uncertain"),
            "confidence": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 1,
            "reason": lambda x: isinstance(x, str) and 0 <= len(x.strip()) <= 500,
        },
    }

    @classmethod
    def validate_create_task(cls, payload: dict) -> TaskIntentResponse:
        """
        Strictly validate a CREATE_TASK response.
        Raises ValueError if validation fails.
        """
        if not isinstance(payload, dict):
            raise ValueError("Response must be a JSON object")

        # Check required fields
        missing = cls.CREATE_TASK_SCHEMA["required_fields"] - set(payload.keys())
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Check forbidden fields (common mistakes)
        forbidden = set(payload.keys()) & cls.CREATE_TASK_SCHEMA["forbidden_fields"]
        if forbidden:
            raise ValueError(
                f"Invalid fields for create_task: {forbidden}. "
                f"Use 'head' instead of 'title', not 'task' or 'description'"
            )

        # Check for extra fields
        extra = set(payload.keys()) - cls.CREATE_TASK_SCHEMA["required_fields"]
        if extra:
            raise ValueError(f"Extra unexpected fields: {extra}")

        # Type validation
        for field, expected_type in cls.CREATE_TASK_SCHEMA["field_types"].items():
            value = payload[field]
            if not isinstance(value, expected_type):
                raise ValueError(
                    f"Field '{field}' must be {expected_type}, got {type(value).__name__}"
                )

        # Constraint validation
        for field, constraint in cls.CREATE_TASK_SCHEMA["constraints"].items():
            try:
                if not constraint(payload[field]):
                    raise ValueError(f"Field '{field}' failed validation constraint")
            except Exception as e:
                raise ValueError(f"Field '{field}' validation failed: {e}")

        # Create and return typed response
        return TaskIntentResponse(
            intent=payload["intent"],
            head=payload["head"],
            body=payload["body"],
            confidence=float(payload["confidence"]),
            reason=payload["reason"],
        )

    @classmethod
    def validate_non_task(cls, payload: dict) -> NonTaskIntentResponse:
        """
        Strictly validate a NON_TASK or UNCERTAIN response.
        Raises ValueError if validation fails.
        """
        if not isinstance(payload, dict):
            raise ValueError("Response must be a JSON object")

        # Check required fields
        missing = cls.NON_TASK_SCHEMA["required_fields"] - set(payload.keys())
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Check forbidden fields (must not have task data)
        forbidden = set(payload.keys()) & cls.NON_TASK_SCHEMA["forbidden_fields"]
        if forbidden:
            raise ValueError(
                f"Fields {forbidden} should not exist for non_task intent. "
                f"Only include: intent, confidence, reason"
            )

        # Check for extra fields
        extra = set(payload.keys()) - cls.NON_TASK_SCHEMA["required_fields"]
        if extra:
            raise ValueError(f"Extra unexpected fields: {extra}")

        # Type validation
        for field, expected_type in cls.NON_TASK_SCHEMA["field_types"].items():
            value = payload[field]
            if not isinstance(value, expected_type):
                raise ValueError(
                    f"Field '{field}' must be {expected_type}, got {type(value).__name__}"
                )

        # Constraint validation
        for field, constraint in cls.NON_TASK_SCHEMA["constraints"].items():
            try:
                if not constraint(payload[field]):
                    raise ValueError(f"Field '{field}' failed validation constraint")
            except Exception as e:
                raise ValueError(f"Field '{field}' validation failed: {e}")

        # Create and return typed response
        return NonTaskIntentResponse(
            intent=payload["intent"],
            confidence=float(payload["confidence"]),
            reason=payload["reason"],
        )

    @classmethod
    def validate(cls, payload: dict) -> dict:
        """
        Universal validator that routes to appropriate schema.
        Returns validated dictionary ready for database insertion.
        """
        if not isinstance(payload, dict):
            raise ValueError("Response must be a JSON object")

        intent = payload.get("intent")

        if intent == "create_task":
            response = cls.validate_create_task(payload)
            return response.to_dict()

        elif intent in ("non_task", "uncertain"):
            response = cls.validate_non_task(payload)
            return response.to_dict()

        else:
            raise ValueError(
                f"Invalid intent '{intent}'. Must be 'create_task', 'non_task', or 'uncertain'"
            )


# ============================================================================
# SYSTEM PROMPT GENERATOR
# ============================================================================

def get_strict_intent_classification_prompt() -> str:
    """
    Generates a system prompt that enforces strict JSON format.
    This prompt is designed to force the LLM to return exact schemas.
    """
    return """You are an intent classification system. You MUST respond with ONLY valid JSON.

Your task: Classify whether the Discord message is requesting task creation.

CRITICAL RULES:
1. Your response MUST be valid JSON only (no markdown, no backticks, no explanation)
2. Response format depends on the intent:

FOR CREATE_TASK (user wants to create a task):
{
  "intent": "create_task",
  "head": "Short descriptive task title (max 500 chars)",
  "body": "Detailed task description or notes (max 2000 chars, can be empty)",
  "confidence": 0.95,
  "reason": "Why you classified this as create_task"
}

FOR NON_TASK or UNCERTAIN (not a task):
{
  "intent": "non_task",
  "confidence": 0.85,
  "reason": "Why you classified this as non_task"
}

IMPORTANT FIELD MAPPING:
- "head" is the SHORT TITLE (maps to database TASKS.head)
- "body" is DETAILED NOTES (maps to database TASKS.body)
- NEVER use "title", "task", or "description" - use "head" and "body"
- For non_task: NEVER include "head" or "body" fields
- confidence: floating point number from 0 to 1
- reason: brief explanation string

CLASSIFICATION RULES:
- create_task: User explicitly states intent to do something
  Examples: "I will finish my essay", "Remind me to run 5k", "I need to call mom"
- non_task: Conversation, questions, hypotheticals, vague statements
  Examples: "How's the weather?", "Do you think I should exercise?", "I might start coding"
- uncertain: Borderline cases where intent is unclear

VALIDATION:
- head must not be empty (if create_task)
- body can be empty string (if create_task)
- confidence must be between 0 and 1
- reason must not be empty
- All strings must be properly escaped in JSON
- No markdown code blocks in response

RESPOND WITH ONLY THE JSON OBJECT. NO OTHER TEXT.
"""


# ============================================================================
# EXAMPLE USAGE & TESTING
# ============================================================================

def test_validator():
    """Test the strict validator with various payloads."""
    
    print("=" * 70)
    print("STRICT INTENT VALIDATOR - TEST SUITE")
    print("=" * 70)

    # Test 1: Valid CREATE_TASK
    print("\n✅ Test 1: Valid CREATE_TASK")
    try:
        valid_create = {
            "intent": "create_task",
            "head": "Complete the project report",
            "body": "Finish the Q3 report with all metrics and graphs",
            "confidence": 0.95,
            "reason": "User explicitly stated intent to complete",
        }
        result = StrictIntentValidator.validate(valid_create)
        print(f"PASS: {json.dumps(result, indent=2)}")
    except ValueError as e:
        print(f"FAIL: {e}")

    # Test 2: Valid NON_TASK
    print("\n✅ Test 2: Valid NON_TASK")
    try:
        valid_non_task = {
            "intent": "non_task",
            "confidence": 0.85,
            "reason": "User asking a question, not creating a task",
        }
        result = StrictIntentValidator.validate(valid_non_task)
        print(f"PASS: {json.dumps(result, indent=2)}")
    except ValueError as e:
        print(f"FAIL: {e}")

    # Test 3: Invalid - Uses "title" instead of "head"
    print("\n❌ Test 3: Invalid - Uses 'title' instead of 'head'")
    try:
        invalid_title = {
            "intent": "create_task",
            "title": "Complete the project report",  # WRONG!
            "body": "Finish the Q3 report",
            "confidence": 0.95,
            "reason": "User explicitly stated intent",
        }
        result = StrictIntentValidator.validate(invalid_title)
        print(f"UNEXPECTED PASS: {result}")
    except ValueError as e:
        print(f"EXPECTED FAIL: {e}")

    # Test 4: Invalid - NON_TASK with head field
    print("\n❌ Test 4: Invalid - NON_TASK with 'head' field")
    try:
        invalid_non_task = {
            "intent": "non_task",
            "head": "Should not be here",  # WRONG!
            "confidence": 0.85,
            "reason": "This is not a task",
        }
        result = StrictIntentValidator.validate(invalid_non_task)
        print(f"UNEXPECTED PASS: {result}")
    except ValueError as e:
        print(f"EXPECTED FAIL: {e}")

    # Test 5: Invalid - Missing "head"
    print("\n❌ Test 5: Invalid - CREATE_TASK missing 'head'")
    try:
        missing_head = {
            "intent": "create_task",
            "body": "Some description",
            "confidence": 0.95,
            "reason": "User said something",
        }
        result = StrictIntentValidator.validate(missing_head)
        print(f"UNEXPECTED PASS: {result}")
    except ValueError as e:
        print(f"EXPECTED FAIL: {e}")

    # Test 6: Invalid - Confidence out of range
    print("\n❌ Test 6: Invalid - Confidence > 1.0")
    try:
        invalid_conf = {
            "intent": "create_task",
            "head": "Task title",
            "body": "Task body",
            "confidence": 1.5,  # WRONG!
            "reason": "User said something",
        }
        result = StrictIntentValidator.validate(invalid_conf)
        print(f"UNEXPECTED PASS: {result}")
    except ValueError as e:
        print(f"EXPECTED FAIL: {e}")

    # Test 7: Invalid - Empty head
    print("\n❌ Test 7: Invalid - CREATE_TASK with empty 'head'")
    try:
        empty_head = {
            "intent": "create_task",
            "head": "   ",  # Empty after strip!
            "body": "Task body",
            "confidence": 0.95,
            "reason": "User said something",
        }
        result = StrictIntentValidator.validate(empty_head)
        print(f"UNEXPECTED PASS: {result}")
    except ValueError as e:
        print(f"EXPECTED FAIL: {e}")

    # Test 8: Invalid - Wrong intent type
    print("\n❌ Test 8: Invalid - Wrong intent type")
    try:
        wrong_intent = {
            "intent": "maybe_task",  # WRONG!
            "head": "Task title",
            "body": "Task body",
            "confidence": 0.95,
            "reason": "User said something",
        }
        result = StrictIntentValidator.validate(wrong_intent)
        print(f"UNEXPECTED PASS: {result}")
    except ValueError as e:
        print(f"EXPECTED FAIL: {e}")

    print("\n" + "=" * 70)
    print("TEST SUITE COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_validator()
