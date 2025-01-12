from typing import Optional, List, Dict, Any, Type, Callable
from dataclasses import dataclass
from pydantic import BaseModel


@dataclass
class Tool:
    name: str
    description: str
    input_schema: Type[BaseModel]
    execute: Optional[Callable] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema.model_json_schema(),
        }
