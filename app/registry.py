from typing import Any, Dict, List, Type, Optional
from pydantic import BaseModel
from .tools.base import ToolDefinition

class UnknownToolError(Exception):
    """Raised when a requested tool is not found in the registry."""
    pass

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, schema: Type[BaseModel]):
        """Decorator to register a tool."""
        def decorator(func):
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                schema=schema,
                func=func
            )
            return func
        return decorator

    def get_tool(self, name: str) -> ToolDefinition:
        """Retrieves a tool definition or raises UnknownToolError (Guard 1)."""
        if name not in self._tools:
            raise UnknownToolError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def get_llm_tools(self) -> List[Dict[str, Any]]:
        """Generates the JSON schema required by LLM drivers."""
        llm_tools = []
        for name, tool in self._tools.items():
            llm_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": self._generate_json_schema(tool.schema),
                },
            })
        return llm_tools

    def _generate_json_schema(self, schema: Type[BaseModel]) -> Dict[str, Any]:
        """Converts Pydantic model to OpenAI-style JSON schema."""
        # Simplification for the purpose of the demo
        properties = {}
        required = []
        for field_name, field in schema.__annotations__.items():
            # Basic type mapping
            type_map = {str: "string", int: "integer", float: "number", bool: "boolean"}
            properties[field_name] = {"type": type_map.get(field, "string")}
            required.append(field_name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

# Global registry instance
registry = ToolRegistry()
