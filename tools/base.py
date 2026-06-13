import inspect
from typing import Callable, Any, Dict

class BaseTool:
    def __init__(self, name: str, description: str, parameters: Dict[str, Any], func: Callable[..., Any]):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func

    async def execute(self, **kwargs) -> str:
        """Executes the wrapped function (handling async/sync seamlessly) and returns the output as a string."""
        try:
            # If the function is defined with async def, await it
            if inspect.iscoroutinefunction(self.func):
                result = await self.func(**kwargs)
            else:
                result = self.func(**kwargs)
            return str(result)
        except Exception as e:
            return f"Error executing tool '{self.name}': {e}"

def generate_schema(func: Callable[..., Any]) -> Dict[str, Any]:
    """Generates an OpenAI-compatible JSON schema for the function's parameters."""
    sig = inspect.signature(func)
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    # Map Python types to JSON Schema equivalents
    type_mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object"
    }

    for param_name, param in sig.parameters.items():
        # Skip catch-all arguments or object references
        if param_name in ("self", "args", "kwargs"):
            continue
            
        param_type = param.annotation
        json_type = type_mapping.get(param_type, "string")  # Default to string if untyped
        
        param_schema = {"type": json_type}
        parameters["properties"][param_name] = param_schema
        
        # If the parameter has no default value, it is required
        if param.default == inspect.Parameter.empty:
            parameters["required"].append(param_name)
            
    return parameters

def tool(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to automatically wrap and register a function into the global registry."""
    # Import registry locally to avoid circular dependencies at startup
    from tools.registry import registry
    
    name = func.__name__
    description = func.__doc__ or "No description provided."
    parameters = generate_schema(func)
    
    # Instantiate and register the base tool
    base_tool = BaseTool(name=name, description=description, parameters=parameters, func=func)
    registry.register(base_tool)
    
    return func