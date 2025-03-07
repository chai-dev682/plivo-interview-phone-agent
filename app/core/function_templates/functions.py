import json

function_list = [
    {
        "type": "function",
        "function": {
            "name": "evaluate_interview",
            "description": "Evaluate interview responses based on specified criteria",
            "parameters": {
                "type": "object",
                "properties": {
                    "criteria": {
                        "type": "array",
                        "description": "Array of evaluation criteria with scores and explanations",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Name of the evaluation criterion"
                                },
                                "score": {
                                    "type": "integer",
                                    "description": "Score from 0-100",
                                    "minimum": 0,
                                    "maximum": 100
                                },
                                "explanation": {
                                    "type": "string",
                                    "description": "Detailed explanation of the score"
                                }
                            },
                            "required": ["name", "score", "explanation"]
                        }
                    },
                    "final_score": {
                        "type": "integer",
                        "description": "Final score from 0-100 based on above criteria"
                    }
                },
                "required": ["criteria", "final_score"]
            }
        }
    }
]

functions = json.loads(json.dumps(function_list))