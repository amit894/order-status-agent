"""
order_status_agent.py
Companion code for "Agentic Backend Design 102: An FMEA for Your Agent".

Runs two ways:
  python order_status_agent.py --mock     # no GPU needed; replays a buggy model so you SEE the guards fire
  python order_status_agent.py --ollama   # real loop against a local model via Ollama

The five guards map 1:1 to the article's blocks:
  Block 1  tool registry          -> reject unknown tool names
  Block 2  schema validation      -> reject bad/missing args before executing
  Block 3  circuit breaker        -> cap iterations + detect repeated calls
  Block 4  state re-injection      -> pin goal + known facts every turn
  Block 5  untrusted output check  -> verify the final message against real tool results
"""

import argparse
import json
import sys
from pydantic import BaseModel, ValidationError


# ----------------------------------------------------------------------
# The tools (mocked with a tiny in-memory "database")
# ----------------------------------------------------------------------

_ORDERS = {"A-1029": {"tracking_id": "TRK-8810", "status": "shipped"}}
_SHIPMENTS = {"TRK-8810": {"location": "Bengaluru hub", "eta": "2026-06-16"}}
_SENT = []


def get_order(order_id: str) -> dict:
    if order_id not in _ORDERS:
        return {"error": f"order '{order_id}' not found"}
    return _ORDERS[order_id]


def get_shipping(tracking_id: str) -> dict:
    if tracking_id not in _SHIPMENTS:
        return {"error": f"tracking id '{tracking_id}' not found"}
    return _SHIPMENTS[tracking_id]


def notify_customer(order_id: str, message: str) -> dict:
    _SENT.append({"order_id": order_id, "message": message})
    return {"sent": True}


REGISTRY = {
    "get_order": get_order,
    "get_shipping": get_shipping,
    "notify_customer": notify_customer,
}


# ----------------------------------------------------------------------
# Argument schemas (Block 2 lives here)
# ----------------------------------------------------------------------

class GetOrderArgs(BaseModel):
    order_id: str


class GetShippingArgs(BaseModel):
    tracking_id: str


class NotifyArgs(BaseModel):
    order_id: str
    message: str


SCHEMAS = {
    "get_order": GetOrderArgs,
    "get_shipping": GetShippingArgs,
    "notify_customer": NotifyArgs,
}


# Tool definitions handed to the model (Ollama / OpenAI-style function schema)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Look up an order by its order id.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_shipping",
            "description": "Get shipping location and ETA by TRACKING id (not order id).",
            "parameters": {
                "type": "object",
                "properties": {"tracking_id": {"type": "string"}},
                "required": ["tracking_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify_customer",
            "description": "Send a message to the customer about their order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["order_id", "message"],
            },
        },
    },
]

SYSTEM = (
    "You are an order-status agent. Find the order's shipping ETA, then notify "
    "the customer. Use get_order first, take the tracking_id from its result, "
    "pass THAT to get_shipping, then notify_customer with the ETA."
)


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------

def tool_error(detail: str) -> str:
    return json.dumps({"error": detail})


def escalate(reason: str) -> str:
    # In production this is where you route to a frontier model.
    return f"[ESCALATED] {reason}"


def log(tag: str, payload):
    print(f"  {tag:<13} {payload}")


# ----------------------------------------------------------------------
# THE NAIVE LOOP — no guards. This is the demo that bites you.
# ----------------------------------------------------------------------

def run_naive(driver, user_msg: str) -> str:
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_msg}]
    while True:
        msg = driver(messages)
        messages.append(msg)
        if not msg.get("tool_calls"):
            return msg["content"]
        for call in msg["tool_calls"]:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            log("TOOL CALL", f"{name} {args}")
            result = REGISTRY[name](**args)        # blindly trusts the model
            log("TOOL RESULT", result)
            messages.append({"role": "tool", "content": json.dumps(result)})


# ----------------------------------------------------------------------
# THE GUARDED LOOP — all five guards.
# ----------------------------------------------------------------------

def run_safe(driver, user_msg: str, max_steps: int = 8) -> str:
    facts = {}                                     # Block 4: what we actually know
    seen = set()                                   # Block 3: repeated-call detection

    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_msg}]

    for _ in range(max_steps):                     # Block 3: bounded loop
        # Block 4: re-inject goal + known facts at the END of context every turn.
        messages.append({
            "role": "system",
            "content": f"GOAL: notify the customer of the ETA. KNOWN FACTS: {facts or '{}'}",
        })

        msg = driver(messages)
        messages.append(msg)

        if not msg.get("tool_calls"):
            return verify_final(msg["content"], facts)   # Block 5

        for call in msg["tool_calls"]:
            name = call["function"]["name"]
            args = call["function"]["arguments"]
            log("TOOL CALL", f"{name} {args}")

            # Block 1: tool must exist
            if name not in REGISTRY:
                log("GUARD", f"Block1 reject unknown tool '{name}'")
                messages.append({"role": "tool", "content": tool_error(f"unknown tool '{name}'")})
                continue

            # Block 3: same call twice -> trip the breaker
            sig = (name, json.dumps(args, sort_keys=True))
            if sig in seen:
                log("GUARD", "Block3 circuit breaker: repeated call")
                return escalate("loop detected: repeated identical call")
            seen.add(sig)

            # Block 2: validate args before executing
            try:
                clean = SCHEMAS[name](**args).model_dump()
            except (ValidationError, TypeError) as e:
                log("GUARD", "Block2 invalid args -> feeding error back")
                messages.append({"role": "tool", "content": tool_error(str(e))})
                continue

            result = REGISTRY[name](**clean)
            log("TOOL RESULT", result)

            # capture real facts for Blocks 4 & 5
            if "eta" in result:
                facts["eta"] = result["eta"]
            if "tracking_id" in result:
                facts["tracking_id"] = result["tracking_id"]

            messages.append({"role": "tool", "content": json.dumps(result)})

    return escalate("hit step limit")              # Block 3: never run forever


def verify_final(answer: str, facts: dict) -> str:
    # Block 5: don't trust a free-text answer. If it states an ETA, it must match reality.
    real_eta = facts.get("eta")
    if real_eta and real_eta not in (answer or ""):
        log("GUARD", "Block5 fabricated ETA -> rejected")
        return escalate(f"answer ETA does not match verified ETA {real_eta}")
    return answer


# ----------------------------------------------------------------------
# DRIVER A: a real local model via Ollama
# ----------------------------------------------------------------------

def ollama_driver(model="qwen3:7b"):
    import ollama

    def drive(messages):
        resp = ollama.chat(model=model, messages=messages, tools=TOOLS)
        m = resp["message"]
        # normalise tool_calls to plain dicts
        calls = []
        for c in (m.get("tool_calls") or []):
            calls.append({"function": {"name": c["function"]["name"],
                                       "arguments": dict(c["function"]["arguments"])}})
        return {"role": "assistant", "content": m.get("content", ""), "tool_calls": calls}

    return drive


# ----------------------------------------------------------------------
# DRIVER B: a scripted "buggy 7B" so you can watch the guards fire (no GPU)
# It reproduces three classic failures: wrong-id threading, a repeat, a fabrication.
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="run scripted buggy model (no GPU)")
    ap.add_argument("--ollama", action="store_true", help="run against a local Ollama model")
    ap.add_argument("--model", default="qwen3:7b")
    args = ap.parse_args()

    if not (args.mock or args.ollama):
        print(__doc__)
        sys.exit(0)

    driver = ollama_driver(args.model) if args.ollama else mock_buggy_driver()
    user_msg = "Where is my order A-1029?"

    print("\n=== NAIVE LOOP (no guards) ===")
    try:
        # fresh driver for the naive run so the script isn't exhausted
        d = ollama_driver(args.model) if args.ollama else mock_buggy_driver()
        print("RESULT:", run_naive(d, user_msg))
    except Exception as e:
        print("CRASHED:", e)

    print("\n=== GUARDED LOOP (five guards) ===")
    d = ollama_driver(args.model) if args.ollama else mock_buggy_driver()
    print("RESULT:", run_safe(d, user_msg))


if __name__ == "__main__":
    main()
