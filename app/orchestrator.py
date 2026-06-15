import json
from typing import Any, Dict, List, Callable
from pydantic import ValidationError
from .registry import registry, UnknownToolError
from .state_manager import StateManager

class Orchestrator:
    def __init__(self, driver: Callable, state_manager: StateManager):
        self.driver = driver
        self.state_manager = state_manager

    def run(self, user_msg: str, max_steps: int = 8) -> str:
        seen = set()
        messages = [
            {"role": "system", "content": "You are an order-status agent. Find the order's shipping ETA, then notify the customer."},
            {"role": "user", "content": user_msg}
        ]

        for step in range(max_steps):
            # Guard 4: State Re-injection
            messages.append({
                "role": "system",
                "content": self.state_manager.get_knowledge_injection()
            })

            msg = self.driver(messages)
            messages.append(msg)

            if not msg.get("tool_calls"):
                return self.verify_final(msg["content"])

            for call in msg["tool_calls"]:
                name = call["function"]["name"]
                args = call["function"]["arguments"]

                # Guard 1: Tool Registry
                try:
                    tool_def = registry.get_tool(name)
                except UnknownToolError as e:
                    messages.append({"role": "tool", "content": json.dumps({"error": str(e)})})
                    continue

                # Guard 3: Circuit Breaker (Repeated Call)
                sig = (name, json.dumps(args, sort_keys=True))
                if sig in seen:
                    return f"[ESCALATED] Loop detected: repeated call to {name}"
                seen.add(sig)

                # Guard 2: Schema Validation
                try:
                    clean_args = tool_def.schema(**args).model_dump()
                except (ValidationError, TypeError) as e:
                    messages.append({"role": "tool", "content": json.dumps({"error": str(e)})})
                    continue

                # Execution
                result = tool_def.func(**clean_args)

                # Guard 4: Update state from result
                self.state_manager.promote_tool_results(result)

                messages.append({"role": "tool", "content": json.dumps(result)})

        return "[ESCALATED] Hit step limit"

    def verify_final(self, answer: str) -> str:
        # Guard 5: Final check against known facts
        real_eta = self.state_manager.get_fact("eta")
        if real_eta and real_eta not in (answer or ""):
            return f"[ESCALATED] answer ETA does not match verified ETA {real_eta}"
        return answer
