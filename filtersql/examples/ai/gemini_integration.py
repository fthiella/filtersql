# -*- coding: utf-8 -*-
"""
filtersql + Gemini Structured Outputs
===================================
Minimal example of Gemini integration using the new google.genai SDK.
The AI DOES NOT generate SQL; it ONLY generates the payload for filtersql.
100% secure, 0 risk of SQL injection.
"""

import os
import json
from google import genai
from filtersql import filtersql

from dotenv import load_dotenv
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# Initialize the Client
# Ensure GEMINI_API_KEY is set in your environment variables
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# ============================================================================
# JSON SCHEMA - The "sandbox" for Gemini
# ============================================================================
# Schema definition for structured JSON output

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "source": {
            "type": "STRING",
            "enum": ["users", "contracts", "resolutions"]
        },
        "filters": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "field": {"type": "STRING"},
                    "operator": {
                        "type": "STRING",
                        "enum": ["=", "!=", ">", ">=", "<", "<=", "icontains", "in"]
                    },
                    "value": {"type": "STRING"}
                },
                "required": ["field", "operator", "value"]
            }
        },
        "order": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "field": {"type": "STRING"},
                    "order": {"type": "STRING", "enum": ["asc", "desc"]}
                },
                "required": ["field", "order"]
            }
        }
    },
    "required": ["source", "filters"]
}

SYSTEM_INSTRUCTION = """Convert user questions into SQL filter payloads.
Tables: users (id, first_name, last_name, email, age, status, role)
Operators: =, !=, >, >=, <, <=, icontains (contains), in, between

Examples:
"Active users" -> {"source":"users","filters":[{"field":"status","operator":"=","value":"active"}]}
"Users over 30 years old" -> {"source":"users","filters":[{"field":"age","operator":">","value":"30"}]}
"Admins named John" -> {"source":"users","filters":[{"field":"role","operator":"=","value":"admin"},{"field":"first_name","operator":"icontains","value":"John"}]}
"""

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def question_to_sql(question: str):
    """Transforms a natural language question into safe SQL via filtersql."""
    
    # 1. Gemini generates the JSON payload
    response = client.models.generate_content(
        model='gemini-3.1-flash-lite',
        contents=f"{SYSTEM_INSTRUCTION}\n\nUser Question: {question}",
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SCHEMA,
            temperature=0.0
        )
    )
    
    payload = json.loads(response.text)
    print("\nAI Payload:", json.dumps(payload, indent=2, ensure_ascii=False))
    
    # 2. filtersql generates the safe SQL query!
    query, params = filtersql(
        payload,
        action='select',
        dbms='SQLite',
        placeholder='?'
    )
    
    print(f"\nSQL: {query.strip()}")
    print(f"Parameters: {params}")
    
    return query, params

# ============================================================================
# TESTS
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("filtersql + Gemini (Structured Outputs)")
    print("=" * 60)
    
    test_questions = [
        "Show me all active users",
        "Users older than 40",
        "Find inactive admins"
    ]
    
    for q in test_questions:
        print(f"\n{'--'}")
        print(f"{q}")
        question_to_sql(q)