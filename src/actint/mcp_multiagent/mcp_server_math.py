"""
MCP server for the math specialist agent.

This server exposes math and quantitative analysis tools only.
"""

import ast
import json
import math
from statistics import mean, median, pstdev

from fastmcp import FastMCP

mcp = FastMCP("AIS Math Specialist", "1.0.0")


def _parse_float_list(values_csv: str) -> list[float]:
    parts = [p.strip() for p in (values_csv or "").split(",") if p.strip()]
    if not parts:
        raise ValueError("values_csv must contain at least one numeric value")
    return [float(p) for p in parts]


def _safe_eval(expression: str) -> float:
    allowed_nodes = {
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.Mod,
        ast.USub,
        ast.UAdd,
        ast.Constant,
        ast.Load,
        ast.Call,
        ast.Name,
    }
    allowed_funcs = {
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "abs": abs,
        "ceil": math.ceil,
        "floor": math.floor,
        "round": round,
    }
    allowed_consts = {"pi": math.pi, "e": math.e}

    tree = ast.parse(expression, mode="eval")
    for node in ast.walk(tree):
        if type(node) not in allowed_nodes:
            raise ValueError(f"Disallowed expression node: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id not in allowed_funcs and node.id not in allowed_consts:
            raise ValueError(f"Unknown symbol: {node.id}")

    code = compile(tree, "<expression>", "eval")
    return float(eval(code, {"__builtins__": {}}, {**allowed_funcs, **allowed_consts}))


@mcp.tool()
def evaluate_expression(expression: str) -> str:
    """Evaluate a safe arithmetic expression.

    Supports +, -, *, /, **, %, parentheses, and selected functions (sqrt, sin,
    cos, tan, log, log10, exp, abs, ceil, floor, round) with constants pi and e.
    """
    try:
        expr = (expression or "").strip()
        if not expr:
            return json.dumps({"error": "expression is required"})
        result = _safe_eval(expr)
        return json.dumps({"expression": expr, "result": result}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def basic_arithmetic(a: float | str, b: float | str, operation: str) -> str:
    """Perform basic arithmetic on two values.

    operation: add | sub | mul | div
    """
    try:
        a = float(a)
        b = float(b)
        op = (operation or "").strip().lower()
        if op == "add":
            result = a + b
        elif op == "sub":
            result = a - b
        elif op == "mul":
            result = a * b
        elif op == "div":
            if b == 0:
                return json.dumps({"error": "division by zero"})
            result = a / b
        else:
            return json.dumps({"error": "operation must be one of: add, sub, mul, div"})
        return json.dumps({"a": a, "b": b, "operation": op, "result": result}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def power_and_root(value: float | str, exponent: float | str = 2, root_degree: float | str = 0) -> str:
    """Compute value^exponent and optionally n-th root if root_degree > 0."""
    try:
        value = float(value)
        exponent = float(exponent)
        root_degree = float(root_degree)

        payload = {"value": value, "exponent": exponent, "power": value**exponent}
        if root_degree > 0:
            if value < 0 and int(root_degree) % 2 == 0:
                return json.dumps({"error": "even root of negative value is not real"})
            payload["root_degree"] = root_degree
            payload["root"] = value ** (1.0 / root_degree)
        return json.dumps(payload, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def logarithm(value: float | str, base: float | str = math.e) -> str:
    """Compute logarithm of value with a given base (default natural log)."""
    try:
        value = float(value)
        base = float(base)
        if value <= 0:
            return json.dumps({"error": "value must be > 0"})
        if base <= 0 or base == 1:
            return json.dumps({"error": "base must be > 0 and != 1"})
        result = math.log(value, base)
        return json.dumps({"value": value, "base": base, "result": result}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def trigonometry(angle_degrees: float | str, function: str) -> str:
    """Compute trigonometric function for an angle in degrees.

    function: sin | cos | tan
    """
    try:
        angle_degrees = float(angle_degrees)
        fn = (function or "").strip().lower()
        radians = math.radians(angle_degrees)
        if fn == "sin":
            result = math.sin(radians)
        elif fn == "cos":
            result = math.cos(radians)
        elif fn == "tan":
            result = math.tan(radians)
        else:
            return json.dumps({"error": "function must be one of: sin, cos, tan"})
        return json.dumps(
            {
                "angle_degrees": angle_degrees,
                "angle_radians": radians,
                "function": fn,
                "result": result,
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def percentage_change(old_value: float | str, new_value: float | str) -> str:
    """Compute percentage change from old_value to new_value."""
    try:
        old_value = float(old_value)
        new_value = float(new_value)
        if old_value == 0:
            return json.dumps({"error": "old_value must not be zero"})
        delta = new_value - old_value
        pct = (delta / old_value) * 100.0
        return json.dumps(
            {
                "old_value": old_value,
                "new_value": new_value,
                "delta": delta,
                "percent_change": pct,
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def solve_linear(a: float | str, b: float | str) -> str:
    """Solve linear equation a*x + b = 0."""
    try:
        a = float(a)
        b = float(b)
        if a == 0:
            return json.dumps({"error": "a must not be zero for a linear equation"})
        x = -b / a
        return json.dumps({"a": a, "b": b, "solution_x": x}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def solve_quadratic(a: float | str, b: float | str, c: float | str) -> str:
    """Solve quadratic equation a*x^2 + b*x + c = 0."""
    try:
        a = float(a)
        b = float(b)
        c = float(c)
        if a == 0:
            return json.dumps({"error": "a must not be zero for a quadratic equation"})

        discriminant = b * b - 4 * a * c
        if discriminant >= 0:
            root_disc = math.sqrt(discriminant)
            x1 = (-b + root_disc) / (2 * a)
            x2 = (-b - root_disc) / (2 * a)
            roots = [x1, x2]
        else:
            root_disc = math.sqrt(-discriminant)
            real = -b / (2 * a)
            imag = root_disc / (2 * a)
            roots = [f"{real}+{imag}i", f"{real}-{imag}i"]

        return json.dumps(
            {
                "a": a,
                "b": b,
                "c": c,
                "discriminant": discriminant,
                "roots": roots,
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def descriptive_stats(values_csv: str) -> str:
    """Compute descriptive statistics for comma-separated numeric values."""
    try:
        values = _parse_float_list(values_csv)
        n = len(values)
        if n == 1:
            std_dev = 0.0
        else:
            std_dev = pstdev(values)

        return json.dumps(
            {
                "count": n,
                "min": min(values),
                "max": max(values),
                "mean": mean(values),
                "median": median(values),
                "population_std_dev": std_dev,
                "sum": sum(values),
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def correlation(x_values_csv: str, y_values_csv: str) -> str:
    """Compute Pearson correlation coefficient for two numeric series."""
    try:
        x = _parse_float_list(x_values_csv)
        y = _parse_float_list(y_values_csv)
        if len(x) != len(y):
            return json.dumps({"error": "x and y must have same length"})
        if len(x) < 2:
            return json.dumps({"error": "at least 2 paired values are required"})

        mx = mean(x)
        my = mean(y)
        num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        den_x = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        den_y = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if den_x == 0 or den_y == 0:
            return json.dumps({"error": "correlation undefined for zero-variance series"})

        r = num / (den_x * den_y)
        return json.dumps({"pearson_r": r, "n": len(x)}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def linear_regression(x_values_csv: str, y_values_csv: str) -> str:
    """Fit y = slope*x + intercept for paired numeric series."""
    try:
        x = _parse_float_list(x_values_csv)
        y = _parse_float_list(y_values_csv)
        if len(x) != len(y):
            return json.dumps({"error": "x and y must have same length"})
        if len(x) < 2:
            return json.dumps({"error": "at least 2 paired values are required"})

        mx = mean(x)
        my = mean(y)
        sxx = sum((xi - mx) ** 2 for xi in x)
        if sxx == 0:
            return json.dumps({"error": "cannot fit regression when all x values are identical"})

        sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
        slope = sxy / sxx
        intercept = my - slope * mx
        return json.dumps(
            {
                "slope": slope,
                "intercept": intercept,
                "equation": f"y = {slope} * x + {intercept}",
                "n": len(x),
            },
            indent=2,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()
