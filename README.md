# Order Status Agent

This project implements an agentic loop for tracking order status, specifically designed to demonstrate the "Five Guards" of agentic backend design to prevent common failure modes like loops, fabrications, and invalid tool calls.

## 🛡️ The Five Guards
The implementation in `main.py` features:
1. **Tool Registry**: Rejects unknown tool names.
2. **Schema Validation**: Uses Pydantic to reject bad/missing arguments before execution.
3. **Circuit Breaker**: Caps total iterations and detects repeated identical calls.
4. **State Re-injection**: Pins the goal and verified facts at the end of the context every turn.
5. **Untrusted Output Check**: Verifies the final answer against verified facts (e.g., checking if the ETA matches the real tool result).

## 🚀 Running the Agent

### Prerequisites
- Python 3.10+
- `pydantic`
- (Optional) [Ollama](https://ollama.com/) for real local model execution.

### Installation
```bash
pip install pydantic
# If using Ollama
pip install ollama
```

### Execution Modes
The agent can be run in two modes:

1. **Mock Mode (Demo)**: Replays a scripted "buggy model" to show how the guards fire.
   ```bash
   python main.py --mock
   ```

2. **Ollama Mode (Real)**: Runs against a local model via Ollama.
   ```bash
   python main.py --ollama --model qwen3:7b
   ```

## ⚙️ Architecture
- **Naive Loop**: Demonstrates how an unguarded agent can fail (e.g., looping on a wrong ID).
- **Guarded Loop**: Implements the full safety stack to ensure correctness and reliability.
