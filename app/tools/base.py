from dataclasses import dataclass
from typing import Callable, Any, Type
from pydantic import BaseModel

@dataclass
class ToolDefinition:
    name: str
    description: str
    schema: Type[BaseModel]
    func: Callable[..., Any]
