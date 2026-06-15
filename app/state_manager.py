from typing import Dict, Any, Optional

class StateManager:
    """
    Guard 4: State Re-injection and Knowledge Management.
    Tracks verified facts and manages the goal.
    """
    def __init__(self, goal: str):
        self.goal = goal
        self.facts: Dict[str, Any] = {}

    def promote_tool_results(self, result: Dict[str, Any]) -> None:
        """
        Automatically promotes specific verified keys from tool results to facts.
        """
        promotable_keys = {"eta", "tracking_id", "status", "location"}
        for key in promotable_keys:
            if key in result:
                self.facts[key] = result[key]

    def get_knowledge_injection(self) -> str:
        """
        Generates the state injection fragment for the LLM context.
        """
        facts_str = json_dumps_simple(self.facts) if self.facts else "{}"
        return f"GOAL: {self.goal}. KNOWN FACTS: {facts_str}"

    def set_fact(self, key: str, value: Any) -> None:
        self.facts[key] = value

    def get_fact(self, key: str) -> Optional[Any]:
        return self.facts.get(key)

def json_dumps_simple(data: Dict) -> str:
    """Minimal JSON dump for prompt injection."""
    import json
    return json.dumps(data)
