from typing import Dict, Any, List


FIXED_PAYLOAD = {
    "gemini-3-pro": {
        "model": "gemini-3-pro",
        "temperature": 1,
        "extra_body": {
            "thinking_level": "high",
        },
        "stream": True,
    },
    "gpt-5.2": {
        "model": "gpt-5.2",
        "temperature": 1,
        "extra_body": {
            "verbosity": "high",
            "reasoning_effort": "high"
        },
        "stream": True,
    }
}


def build_fixed_payload(model: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    if payload := FIXED_PAYLOAD[model]:
        if payload["extra_body"]:
            return {
                **payload,
                "messages": messages,
                "extra_body": payload["extra_body"].copy()
            }

    default = FIXED_PAYLOAD["gemini-3-pro"]
    return {
        **default,
        "messages": messages,
        "extra_body": default["extra_body"].copy()
    }
