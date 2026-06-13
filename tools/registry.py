from typing import Dict, Any, List
from tools.base import BaseTool

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Adds a tool to the registry."""
        self._tools[tool.name] = tool
        print(f"[Registry] Registered tool: {tool.name}")

    def get_tool(self, name: str) -> BaseTool | None:
        """Retrieves a registered tool by name."""
        return self._tools.get(name)

    def get_all_tool_schemas(self) -> List[Dict[str, Any]]:
        """Converts all registered tools to the schemas format expected by the LLM."""
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return schemas

    async def execute(self, name: str, arguments: Dict[str, Any]) -> str:
        """Executes a registered tool by name with the given argument inputs."""
        tool = self.get_tool(name)
        if not tool:
            return f"Error: Tool '{name}' is not registered."
        return await tool.execute(**arguments)

# Singleton instance of registry used across the system
registry = ToolRegistry()