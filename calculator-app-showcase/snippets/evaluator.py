"""Safe expression evaluator.

I parse expressions myself with a small tokenizer and a recursive-descent
parser instead of calling ``eval``, so typed input can never execute code.
All numbers are ``Decimal``, which is why ``0.1 + 0.2`` is exactly ``0.3``.

Grammar (lowest to highest precedence)::

    expression := term (("+" | "-") term)*
    term       := unary (("*" | "/" | <implicit multiplication>) unary)*
    unary      := ("-" | "+") unary | power
    power      := postfix ("^" unary)?              (right associative)
    postfix    := primary ("%" | "!")*
    primary    := NUMBER | CONSTANT | "(" expression ")" | FUNCTION "(" expression ")"

Percent behaves like a pocket calculator: ``50%`` is 0.5, and ``100+10%``
means "add 10 percent of 100", which is 110.
"""
from __future__ import annotations

import decimal
import math
import re
from decimal import Decimal
from typing import List, Optional, Tuple

from .errors import (
    CalcOverflowError,
    DivisionByZeroError,
    ExpressionSyntaxError,
    MathDomainError,
)

Token = Tuple[str, str]  # (kind, text) where kind is "num", "name" or "op"

_PRECISION = 40
_EXPONENT_LIMIT = 999_999

_TOKEN_RE = re.compile(
    r"\s*(?:"
    r"(?P<num>\d+\.?\d*|\.\d+)"
    r"|(?P<name>sin|cos|tan|ln|log|sqrt|abs|pi|e)"
    r"|(?P<sym>[+\-*/^%!()×÷−–—π√])"
    r")"
)
# The keypad types display symbols; I map them to ASCII operators here.
_SYMBOLS = {"×": "*", "÷": "/", "−": "-", "–": "-", "—": "-"}
_BINARY = {"+", "-", "*", "/", "^"}
_FUNCTIONS = {"sin", "cos", "tan", "ln", "log", "sqrt", "abs"}
_CONSTANTS = {
    "pi": Decimal("3.14159265358979323846264338327950288"),
    "e": Decimal("2.71828182845904523536028747135266250"),
}
# 10000! has about 35,000 digits: still instant to compute and far below the
# exponent limit. Anything bigger is refused rather than freezing the app.
_MAX_FACTORIAL = 10_000

# sin, cos and tan at 0°, 90°, 180° and 270°. None marks tan's poles.
_QUARTER_TURNS = {
    "sin": (0, 1, 0, -1),
    "cos": (1, 0, -1, 0),
    "tan": (0, None, 0, None),
}


def tokenize(text: str) -> List[Token]:
    """Split ``text`` into tokens, normalising display symbols (×, ÷, −, π, √)."""
    text = text.strip()
    tokens: List[Token] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN_RE.match(text, pos)
        if match is None:
            raise ExpressionSyntaxError()
        pos = match.end()
        if match.group("num"):
            tokens.append(("num", match.group("num")))
        elif match.group("name"):
            tokens.append(("name", match.group("name")))
        else:
            symbol = match.group("sym")
            if symbol == "π":
                tokens.append(("name", "pi"))
            elif symbol == "√":
                tokens.append(("name", "sqrt"))
            else:
                tokens.append(("op", _SYMBOLS.get(symbol, symbol)))
    return tokens


def _prepare(tokens: List[Token]) -> List[Token]:
    """Forgive unfinished input: drop a dangling operator and close open brackets.

    This is what lets the live preview show ``= 5`` while the user is still
    typing ``5+`` or ``(2+3``.
    """
    tokens = list(tokens)
    while tokens:
        kind, text = tokens[-1]
        if kind == "op" and (text in _BINARY or text == "("):
            tokens.pop()
        elif kind == "name" and text in _FUNCTIONS:
            tokens.pop()
        else:
            break
    opened = sum(1 for k, t in tokens if k == "op" and t == "(")
    closed = sum(1 for k, t in tokens if k == "op" and t == ")")
    if opened > closed:
        tokens.extend([("op", ")")] * (opened - closed))
    return tokens


def evaluate(expression: str, degrees: bool = True) -> Decimal:
    """Evaluate ``expression`` and return the result as a ``Decimal``.

    ``degrees`` selects the angle unit for sin/cos/tan.
    Raises a :class:`~calculator.core.errors.CalculatorError` subclass on failure.
    """
    tokens = _prepare(tokenize(expression))
    if not tokens:
        return Decimal(0)

    # I work in a private decimal context so the precision and the traps
    # never leak into the rest of the program.
    with decimal.localcontext() as ctx:
        ctx.prec = _PRECISION
        ctx.Emax = _EXPONENT_LIMIT
        ctx.Emin = -_EXPONENT_LIMIT
        for trap in (decimal.InvalidOperation, decimal.DivisionByZero, decimal.Overflow):
            ctx.traps[trap] = True
        try:
            return _Parser(tokens, degrees).parse()
        except decimal.DivisionByZero:
            raise DivisionByZeroError() from None
        except decimal.Overflow:
            raise CalcOverflowError() from None
        except decimal.DecimalException:
            raise MathDomainError() from None
        except RecursionError:  # absurdly deep nesting such as 500 "(" in a row
            raise ExpressionSyntaxError() from None


class _Parser:
    """One method per grammar rule. Each returns ``(value, is_percent)``.

    I carry ``is_percent`` upwards so that ``+`` and ``−`` can tell whether
    their right-hand side was written as a percentage.
    """

    def __init__(self, tokens: List[Token], degrees: bool) -> None:
        self._tokens = tokens
        self._pos = 0
        self._degrees = degrees

    # -- token helpers -------------------------------------------------------
    def _peek(self) -> Optional[Token]:
        return self._tokens[self._pos] if self._pos < len(self._tokens) else None

    def _next(self) -> Token:
        token = self._peek()
        if token is None:
            raise ExpressionSyntaxError()
        self._pos += 1
        return token

    def _peek_op(self, *ops: str) -> bool:
        token = self._peek()
        return token is not None and token[0] == "op" and token[1] in ops

    def _expect_op(self, op: str) -> None:
        if not self._peek_op(op):
            raise ExpressionSyntaxError()
        self._pos += 1

    # -- grammar -------------------------------------------------------------
    def parse(self) -> Decimal:
        value, _ = self._expression()
        if self._peek() is not None:
            raise ExpressionSyntaxError()
        return value

    def _expression(self) -> Tuple[Decimal, bool]:
        left, is_percent = self._term()
        while self._peek_op("+", "-"):
            op = self._next()[1]
            right, right_is_percent = self._term()
            if right_is_percent:  # "100 + 10%" adds 10% *of the left side*
                right = left * right
            left = left + right if op == "+" else left - right
            is_percent = False
        return left, is_percent

    def _term(self) -> Tuple[Decimal, bool]:
        left, is_percent = self._unary()
        while True:
            token = self._peek()
            if token is None:
                break
            if self._peek_op("*", "/"):
                op = self._next()[1]
                right, _ = self._unary()
                if op == "*":
                    left = left * right
                else:
                    if right == 0:
                        raise DivisionByZeroError()
                    left = left / right
            elif self._starts_primary(token):
                previous = self._tokens[self._pos - 1]
                if previous[0] == "num" and token[0] == "num":
                    raise ExpressionSyntaxError()  # "1.2.3" or "2 3"
                right, _ = self._unary()  # implicit multiplication: 2(3), 2π
                left = left * right
            else:
                break
            is_percent = False
        return left, is_percent

    @staticmethod
    def _starts_primary(token: Token) -> bool:
        return token[0] in ("num", "name") or (token[0] == "op" and token[1] == "(")

    def _unary(self) -> Tuple[Decimal, bool]:
        if self._peek_op("-"):
            self._pos += 1
            value, _ = self._unary()
            return -value, False
        if self._peek_op("+"):
            self._pos += 1
            return self._unary()
        return self._power()

    def _power(self) -> Tuple[Decimal, bool]:
        base, is_percent = self._postfix()
        if self._peek_op("^"):
            self._pos += 1
            exponent, _ = self._unary()  # recursing through unary makes ^ right-associative
            return _power(base, exponent), False
        return base, is_percent

    def _postfix(self) -> Tuple[Decimal, bool]:
        value = self._primary()
        is_percent = False
        while True:
            if self._peek_op("!"):
                self._pos += 1
                value = _factorial(value)
                is_percent = False
            elif self._peek_op("%"):
                self._pos += 1
                value = value / Decimal(100)
                is_percent = True
            else:
                return value, is_percent

    def _primary(self) -> Decimal:
        kind, text = self._next()
        if kind == "num":
            return Decimal(text)
        if kind == "name":
            if text in _CONSTANTS:
                return _CONSTANTS[text]
            self._expect_op("(")
            argument, _ = self._expression()
            self._expect_op(")")
            return _apply_function(text, argument, self._degrees)
        if kind == "op" and text == "(":
            value, _ = self._expression()
            self._expect_op(")")
            return value
        raise ExpressionSyntaxError()


# -- math helpers ------------------------------------------------------------
def _power(base: Decimal, exponent: Decimal) -> Decimal:
    if base == 0:
        if exponent < 0:
            raise DivisionByZeroError()
        return Decimal(1) if exponent == 0 else Decimal(0)
    if base < 0 and exponent != exponent.to_integral_value():
        raise MathDomainError()  # (−8)^0.5 has no real answer
    return base**exponent


def _factorial(value: Decimal) -> Decimal:
    if value < 0 or value != value.to_integral_value():
        raise MathDomainError()
    if value > _MAX_FACTORIAL:
        raise CalcOverflowError()
    return Decimal(math.factorial(int(value)))


def _apply_function(name: str, x: Decimal, degrees: bool) -> Decimal:
    if name == "abs":
        return abs(x)
    if name == "sqrt":
        if x < 0:
            raise MathDomainError()
        return x.sqrt()
    if name in ("ln", "log"):
        if x <= 0:
            raise MathDomainError()
        return x.ln() if name == "ln" else x.log10()
    return _trig(name, x, degrees)


def _trig(name: str, x: Decimal, degrees: bool) -> Decimal:
    """sin, cos or tan of ``x``.

    In degree mode I reduce the angle with exact decimal arithmetic before
    touching floats. That keeps sin(10^20°) accurate and lets me return exact
    answers at multiples of 90°, so sin(180) is 0 and tan(90) is "Undefined".
    """
    if degrees:
        x = x % 360
        if x % 90 == 0:
            exact = _QUARTER_TURNS[name][int(x / 90) % 4]
            if exact is None:
                raise MathDomainError("Undefined")
            return Decimal(exact)
        angle = math.radians(float(x))
    else:
        angle = float(x)

    try:
        if name == "tan" and abs(math.cos(angle)) < 1e-15:
            raise MathDomainError("Undefined")  # tan(π/2) in radians
        result = getattr(math, name)(angle)
    except (ValueError, OverflowError):
        raise MathDomainError() from None
    if not math.isfinite(result):
        raise MathDomainError()
    # sin(π) comes back from floats as 1.2e-16 instead of 0. I treat a result
    # as zero only when it is tiny *relative to the angle*, so a genuinely
    # tiny answer like sin(1e-13) survives.
    if abs(result) < 1e-12 * abs(angle):
        return Decimal(0)
    return Decimal(format(result, ".15g"))
