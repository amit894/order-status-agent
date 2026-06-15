import argparse
import json
import sys
from app.registry import registry
from app.state_manager import StateManager
from app.orchestrator import Orchestrator
import app.tools.order_tools # Ensure tools are registered

def ollama_driver(model="qwen3:7b"):
    import ollama
    def drive(messages):
        resp = ollama.chat(model=model, messages=messages, tools=registry.get_llm_tools())
        m = resp["message"]
        # normalise tool_calls to plain dicts
        calls = []
        for c in (m.get("tool_calls") or []):
            calls.append({"function": {"name": c["function"]["name"],
                                       "arguments": dict(c["function"]["arguments"])}})
        return {"role": "assistant", "content": m.get("content", ""), "tool_calls": calls}
    return drive

def mock_buggy_driver():
    steps = iter([
        # 1. correct first call
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "get_order", "arguments": {"order_id": "A-1029"}}}]},
        # 2. WRONG: passes the order id to get_shipping instead of the tracking id
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "get_shipping", "arguments": {"tracking_id": "A-1029"}}}]},
        # 3. repeats the exact same failing call -> circuit breaker should fire
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "get_shipping", "arguments": {"tracking_id": "A-1029"}}}]},
    ])
    def drive(messages):
        try:
            return next(steps)
        except StopIteration:
            # if the breaker hadn't caught it, it would fabricate here
            return {"role": "assistant",
                    "content": "Your order ships, ETA 2026-12-31.",  # made-up date
                    "tool_calls": []}
    return drive

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--ollama", action="store_true")
    ap.add_argument("--model", default="qwen3:7b")
    args = ap.parse_args()

    if not (args.mock or args.ollama):
        print("Run with --mock or --ollama")
        sys.exit(0)

    driver = ollama_driver(args.model) if args.ollama else mock_buggy_driver()
    state_manager = StateManager(goal="Notify the customer of the ETA")
    orchestrator = Orchestrator(driver, state_manager)

    user_msg = "Where is my order A-1029?"
    print(f"User: {user_msg}")
    print("-" * 20)
    result = orchestrator.run(user_msg)
    print(f"RESULT: {result}")

if __name__ == "__main__":
    main()
