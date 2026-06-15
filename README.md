# Order Status Agent (Production Architecture)

This project implements a robust agentic loop for tracking order status, evolving a demo script into a modular, production-ready architecture.

## 🏗️ Production Architecture

The system is decoupled into specific components to ensure reliability, testability, and scalability.

```text
order-status-agent/
├── main.py                 # Application entry point
├── app/
│   ├── orchestrator.py     # Core loop (implements the 5 Guards)
│   ├── registry.py         # Guard 1: Centralized tool management
│   ├── state_manager.py    # Guard 4: Verified fact tracking
│   ├── tools/              # Decoupled tool implementations
│   │   ├── base.py         # Tool definitions
│   │   └── order_tools.py  # Concrete business tools
│   └── schemas/            # Argument validation
│       └── tool_args.py     # Pydantic models
```

## 🛡️ The Five Guards Implementation

The `Orchestrator` manages the following guards in a precise sequence:

1. **Tool Registry (Guard 1)**: Uses `ToolRegistry` to verify tool existence before execution.
2. **Schema Validation (Guard 2)**: Uses Pydantic models in `tool_args.py` to validate arguments.
3. **Circuit Breaker (Guard 3)**: Caps iterations and detects repeated identical calls using a call-signature set.
4. **State Re-injection (Guard 4)**: Uses `StateManager` to append `GOAL` and `KNOWN FACTS` to the prompt at every turn.
5. **Untrusted Output Check (Guard 5)**: Cross-references the final LLM response against verified facts in the `StateManager`.

## 🚀 Running the Agent

### Installation
```bash
pip install pydantic ollama
```

### Execution Modes
- **Mock Mode**: Replays a scripted buggy model to demonstrate the guards firing.
  ```bash
  python main.py --mock
  ```
- **Ollama Mode**: Connects to a local LLM via Ollama.
  ```bash
  python main.py --ollama --model qwen3:7b
  ```
