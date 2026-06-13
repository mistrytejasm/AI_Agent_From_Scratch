import ast
import operator
from tools.base import tool

# Safe supported operators mapping
operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Pow: operator.pow
}

def safe_eval(node):
    """Recursively parses AST nodes to safely calculate math operations."""
    if isinstance(node, ast.Constant):  # Python >= 3.8 constant value
        return node.value
    elif isinstance(node, ast.BinOp):  # Binary operation (e.g. 5 + 3)
        left = safe_eval(node.left)
        right = safe_eval(node.right)
        op_type = type(node.op)
        if op_type in operators:
            return operators[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
    elif isinstance(node, ast.UnaryOp):  # Unary operation (e.g. -5)
        operand = safe_eval(node.operand)
        op_type = type(node.op)
        if op_type in operators:
            return operators[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
    raise ValueError(f"Unsupported expression component: {type(node).__name__}")

@tool
def calculate(expression: str) -> str:
    """Safely evaluates a basic mathematical expression (e.g. '25 * (432 + 12)'). Supports +, -, *, /, **, and brackets."""
    try:
        # Parse expression string into abstract syntax trees
        tree = ast.parse(expression, mode='eval')
        result = safe_eval(tree.body)
        return str(result)
    except Exception as e:
        return f"Error evaluating math expression: {e}"