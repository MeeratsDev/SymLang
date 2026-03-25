r"""
Interpreter for the custom language spec.

Syntax summary:
  Variables:   $x = i(0);  $x = s("hi");  etc.
  Constants:   c$PI = f(3.14);
  Functions:   # add($a, $b) { \ ($i=0; $i<10; $i+=1) { ... } }
  Classes:     @ Dog { $name = s(""); # bark() { ... } }
  if/elif/else: ?($x > 0) { ... } ~?($x == 0) { ... } ~ { ... }
  when:        >($sig) { ... }   (listens for alarm() signal)
  while:       ::($x < 10) { ... }
  for:         \($i = i(0); $i < 10; $i += 1) { ... }
  alarm():     raise a detectable signal
  Comments:    // ...   /* ... */
"""

import re
import sys
from typing import Any, Dict, List, Optional, Tuple

# ──────────────────────────────────────────────
# Token types
# ──────────────────────────────────────────────
TT = {
    "NUMBER": "NUMBER",
    "STRING": "STRING",
    "BOOL": "BOOL",
    "IDENT": "IDENT",
    "VAR": "VAR",
    "CONST": "CONST",
    "FUNC_DEF": "FUNC_DEF",
    "CLASS_DEF": "CLASS_DEF",
    "IF": "IF",
    "ELSE_IF": "ELSE_IF",
    "ELSE": "ELSE",
    "WHEN": "WHEN",
    "WHILE": "WHILE",
    "FOR": "FOR",
    "LBRACE": "LBRACE",
    "RBRACE": "RBRACE",
    "LPAREN": "LPAREN",
    "RPAREN": "RPAREN",
    "LBRACKET": "LBRACKET",
    "RBRACKET": "RBRACKET",
    "COMMA": "COMMA",
    "SEMICOLON": "SEMICOLON",
    "DOT": "DOT",
    "ASSIGN": "ASSIGN",
    "PLUS_ASSIGN": "PLUS_ASSIGN",
    "MINUS_ASSIGN": "MINUS_ASSIGN",
    "STAR_ASSIGN": "STAR_ASSIGN",
    "SLASH_ASSIGN": "SLASH_ASSIGN",
    "PERCENT_ASSIGN": "PERCENT_ASSIGN",
    "PLUS": "PLUS",
    "MINUS": "MINUS",
    "STAR": "STAR",
    "SLASH": "SLASH",
    "PERCENT": "PERCENT",
    "EQ": "EQ",
    "NEQ": "NEQ",
    "LT": "LT",
    "GT": "GT",
    "LTE": "LTE",
    "GTE": "GTE",
    "AND": "AND",
    "OR": "OR",
    "NOT": "NOT",
    "TYPE_CALL": "TYPE_CALL",  # i( f( s( b( a( h(
    "RETURN": "RETURN",
    "NULL": "NULL",
    "EOF": "EOF",
}

TYPE_FUNCS = {"i", "f", "s", "b", "a", "h"}


# ──────────────────────────────────────────────
# Lexer
# ──────────────────────────────────────────────
class Token:
    def __init__(self, type_: str, value: Any, line: int):
        self.type = type_
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line})"


class LexerError(Exception):
    pass


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    line = 1
    n = len(source)

    def peek(offset=0):
        idx = i + offset
        return source[idx] if idx < n else ""

    while i < n:
        # newlines
        if source[i] == "\n":
            line += 1
            i += 1
            continue

        # whitespace
        if source[i].isspace():
            i += 1
            continue

        # single-line comment
        if source[i : i + 2] == "//":
            while i < n and source[i] != "\n":
                i += 1
            continue

        # multi-line comment
        if source[i : i + 2] == "/*":
            i += 2
            while i < n and source[i : i + 2] != "*/":
                if source[i] == "\n":
                    line += 1
                i += 1
            i += 2
            continue

        # strings
        if source[i] in ('"', "'"):
            quote = source[i]
            i += 1
            buf = []
            while i < n and source[i] != quote:
                if source[i] == "\\" and i + 1 < n:
                    esc = source[i + 1]
                    buf.append({"n": "\n", "t": "\t", "r": "\r"}.get(esc, esc))
                    i += 2
                else:
                    buf.append(source[i])
                    i += 1
            i += 1  # closing quote
            tokens.append(Token(TT["STRING"], "".join(buf), line))
            continue

        # numbers
        if source[i].isdigit() or (
            source[i] == "-"
            and i + 1 < n
            and source[i + 1].isdigit()
            and (
                not tokens
                or tokens[-1].type
                in {
                    TT["ASSIGN"],
                    TT["PLUS_ASSIGN"],
                    TT["MINUS_ASSIGN"],
                    TT["STAR_ASSIGN"],
                    TT["SLASH_ASSIGN"],
                    TT["LPAREN"],
                    TT["COMMA"],
                    TT["SEMICOLON"],
                    TT["LBRACKET"],
                    TT["RETURN"],
                    TT["EQ"],
                    TT["NEQ"],
                    TT["LT"],
                    TT["GT"],
                    TT["LTE"],
                    TT["GTE"],
                }
            )
        ):
            buf = []
            if source[i] == "-":
                buf.append("-")
                i += 1
            while i < n and (source[i].isdigit() or source[i] == "."):
                buf.append(source[i])
                i += 1
            raw = "".join(buf)
            val = float(raw) if "." in raw else int(raw)
            tokens.append(Token(TT["NUMBER"], val, line))
            continue

        # type-call functions: i( f( s( b( a( h(
        if source[i] in TYPE_FUNCS and i + 1 < n and source[i + 1] == "(":
            tokens.append(Token(TT["TYPE_CALL"], source[i], line))
            i += 1
            continue

        # two-char operators
        two = source[i : i + 2]
        if two == "~?":
            tokens.append(Token(TT["ELSE_IF"], "~?", line))
            i += 2
            continue
        if two == "+=":
            tokens.append(Token(TT["PLUS_ASSIGN"], "+=", line))
            i += 2
            continue
        if two == "-=":
            tokens.append(Token(TT["MINUS_ASSIGN"], "-=", line))
            i += 2
            continue
        if two == "*=":
            tokens.append(Token(TT["STAR_ASSIGN"], "*=", line))
            i += 2
            continue
        if two == "/=":
            tokens.append(Token(TT["SLASH_ASSIGN"], "/=", line))
            i += 2
            continue
        if two == "%=":
            tokens.append(Token(TT["PERCENT_ASSIGN"], "%=", line))
            i += 2
            continue
        if two == "==":
            tokens.append(Token(TT["EQ"], "==", line))
            i += 2
            continue
        if two == "!=":
            tokens.append(Token(TT["NEQ"], "!=", line))
            i += 2
            continue
        if two == "<=":
            tokens.append(Token(TT["LTE"], "<=", line))
            i += 2
            continue
        if two == ">=":
            tokens.append(Token(TT["GTE"], ">=", line))
            i += 2
            continue
        if two == "&&":
            tokens.append(Token(TT["AND"], "&&", line))
            i += 2
            continue
        if two == "||":
            tokens.append(Token(TT["OR"], "||", line))
            i += 2
            continue

        # single-char tokens
        single = {
            "{": TT["LBRACE"],
            "}": TT["RBRACE"],
            "(": TT["LPAREN"],
            ")": TT["RPAREN"],
            "[": TT["LBRACKET"],
            "]": TT["RBRACKET"],
            ",": TT["COMMA"],
            ";": TT["SEMICOLON"],
            ".": TT["DOT"],
            "=": TT["ASSIGN"],
            "+": TT["PLUS"],
            "-": TT["MINUS"],
            "*": TT["STAR"],
            "/": TT["SLASH"],
            "%": TT["PERCENT"],
            "<": TT["LT"],
            ">": TT["GT"],
            "!": TT["NOT"],
            "?": TT["IF"],
            "~": TT["ELSE"],
            "#": TT["FUNC_DEF"],
            "@": TT["CLASS_DEF"],
            ":": None,
        }

        ch = source[i]

        if ch == ":" and i + 1 < n and source[i + 1] == ":":
            tokens.append(Token(TT["WHILE"], "::", line))
            i += 2
            continue

        if ch == "\\":
            tokens.append(Token(TT["FOR"], "\\", line))
            i += 1
            continue

        # > is WHEN when immediately followed by (
        if ch == ">" and i + 1 < n and source[i + 1] == "(":
            tokens.append(Token(TT["WHEN"], ">", line))
            i += 1
            continue

        if ch in single and single[ch] is not None:
            tokens.append(Token(single[ch], ch, line))
            i += 1
            continue

        # identifiers / keywords (including $var and c$const)
        if ch == "c" and i + 1 < n and source[i + 1] == "$":
            # constant: c$name
            i += 2
            buf = []
            while i < n and (source[i].isalnum() or source[i] == "_"):
                buf.append(source[i])
                i += 1
            tokens.append(Token(TT["CONST"], "".join(buf), line))
            continue

        if ch == "$":
            i += 1
            buf = []
            while i < n and (source[i].isalnum() or source[i] == "_"):
                buf.append(source[i])
                i += 1
            tokens.append(Token(TT["VAR"], "".join(buf), line))
            continue

        if ch.isalpha() or ch == "_":
            buf = []
            while i < n and (source[i].isalnum() or source[i] == "_"):
                buf.append(source[i])
                i += 1
            word = "".join(buf)
            if word == "true":
                tokens.append(Token(TT["BOOL"], True, line))
            elif word == "false":
                tokens.append(Token(TT["BOOL"], False, line))
            elif word == "null":
                tokens.append(Token(TT["NULL"], None, line))
            elif word == "return":
                tokens.append(Token(TT["RETURN"], "return", line))
            elif word == "and":
                tokens.append(Token(TT["AND"], "and", line))
            elif word == "or":
                tokens.append(Token(TT["OR"], "or", line))
            elif word == "not":
                tokens.append(Token(TT["NOT"], "not", line))
            else:
                tokens.append(Token(TT["IDENT"], word, line))
            continue

        raise LexerError(f"Unexpected character {ch!r} at line {line}")

    tokens.append(Token(TT["EOF"], None, line))
    return tokens


# ──────────────────────────────────────────────
# AST nodes
# ──────────────────────────────────────────────
class Node:
    pass


class Program(Node):
    def __init__(self, stmts):
        self.stmts = stmts


class VarDecl(Node):
    def __init__(self, name, expr, const=False, static_type=None):
        self.name = name
        self.expr = expr
        self.const = const
        self.static_type = static_type


class TypeCast(Node):
    def __init__(self, type_char, expr):
        self.type_char = type_char
        self.expr = expr


class Assign(Node):
    def __init__(self, target, op, expr):
        self.target = target
        self.op = op
        self.expr = expr


class VarRef(Node):
    def __init__(self, name):
        self.name = name


class ConstRef(Node):
    def __init__(self, name):
        self.name = name


class AttrAccess(Node):
    def __init__(self, obj, attr):
        self.obj = obj
        self.attr = attr


class NumberLit(Node):
    def __init__(self, value):
        self.value = value


class StringLit(Node):
    def __init__(self, value):
        self.value = value


class BoolLit(Node):
    def __init__(self, value):
        self.value = value


class NullLit(Node):
    pass


class ArrayLit(Node):
    def __init__(self, elements):
        self.elements = elements


class HashLit(Node):
    def __init__(self, pairs):
        self.pairs = pairs  # list of (key_expr, val_expr)


class BinOp(Node):
    def __init__(self, left, op, right):
        self.left = left
        self.op = op
        self.right = right


class UnaryOp(Node):
    def __init__(self, op, expr):
        self.op = op
        self.expr = expr


class FuncCall(Node):
    def __init__(self, name, args):
        self.name = name
        self.args = args


class MethodCall(Node):
    def __init__(self, obj, method, args):
        self.obj = obj
        self.method = method
        self.args = args


class FuncDef(Node):
    def __init__(self, name, params, body):
        self.name = name
        self.params = params
        self.body = body


class ClassDef(Node):
    def __init__(self, name, body):
        self.name = name
        self.body = body


class IfStmt(Node):
    def __init__(self, cond, then, elseifs, else_body):
        self.cond = cond
        self.then = then
        self.elseifs = elseifs
        self.else_body = else_body


class WhenStmt(Node):
    def __init__(self, signal, body):
        self.signal = signal
        self.body = body


class WhileStmt(Node):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body


class ForStmt(Node):
    def __init__(self, init, cond, update, body):
        self.init = init
        self.cond = cond
        self.update = update
        self.body = body


class ReturnStmt(Node):
    def __init__(self, expr):
        self.expr = expr


class AlarmCall(Node):
    pass


class IndexAccess(Node):
    def __init__(self, obj, index):
        self.obj = obj
        self.index = index


class IndexAssign(Node):
    def __init__(self, obj, index, op, expr):
        self.obj = obj
        self.index = index
        self.op = op
        self.expr = expr


# ──────────────────────────────────────────────
# Parser
# ──────────────────────────────────────────────
class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset=1) -> Token:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def consume(self, type_=None) -> Token:
        tok = self.current()
        if type_ and tok.type != type_:
            raise ParseError(
                f"Expected {type_}, got {tok.type} ({tok.value!r}) at line {tok.line}"
            )
        self.pos += 1
        return tok

    def match(self, *types) -> bool:
        return self.current().type in types

    def parse(self) -> Program:
        stmts = []
        while not self.match(TT["EOF"]):
            stmts.append(self.parse_stmt())
        return Program(stmts)

    def parse_block(self) -> List[Node]:
        self.consume(TT["LBRACE"])
        stmts = []
        while not self.match(TT["RBRACE"], TT["EOF"]):
            stmts.append(self.parse_stmt())
        self.consume(TT["RBRACE"])
        return stmts

    def parse_stmt(self) -> Node:
        tok = self.current()

        if tok.type == TT["CLASS_DEF"]:
            return self.parse_class_def()

        if tok.type == TT["FUNC_DEF"]:
            return self.parse_func_def()

        if tok.type == TT["CONST"]:
            return self.parse_const_decl()

        if tok.type == TT["VAR"]:
            # Peek ahead: if it's a dot call (method call), parse as expression stmt
            # Otherwise parse as var declaration/assignment
            save = self.pos
            name_tok2 = self.consume(TT["VAR"])
            if self.match(TT["DOT"]):
                # restore and fall through to expression statement
                self.pos = save
            else:
                self.pos = save
                return self.parse_var_stmt()

        if tok.type == TT["IF"]:
            return self.parse_if()

        if tok.type == TT["WHILE"]:
            return self.parse_while()

        if tok.type == TT["FOR"]:
            return self.parse_for()

        if tok.type == TT["WHEN"]:
            return self.parse_when()

        if tok.type == TT["RETURN"]:
            return self.parse_return()

        # expression statement (function calls, etc.)
        expr = self.parse_expr()
        if self.match(TT["SEMICOLON"]):
            self.consume()
        return expr

    def parse_class_def(self) -> ClassDef:
        self.consume(TT["CLASS_DEF"])
        name = self.consume(TT["IDENT"]).value
        body = self.parse_block()
        return ClassDef(name, body)

    def parse_func_def(self) -> FuncDef:
        self.consume(TT["FUNC_DEF"])
        name = self.consume(TT["IDENT"]).value
        self.consume(TT["LPAREN"])
        params = []
        while not self.match(TT["RPAREN"]):
            if self.match(TT["VAR"]):
                params.append(("var", self.consume().value))
            elif self.match(TT["CONST"]):
                params.append(("const", self.consume().value))
            else:
                params.append(("var", self.consume(TT["IDENT"]).value))
            if self.match(TT["COMMA"]):
                self.consume()
        self.consume(TT["RPAREN"])
        body = self.parse_block()
        return FuncDef(name, params, body)

    def parse_const_decl(self) -> VarDecl:
        name = self.consume(TT["CONST"]).value
        self.consume(TT["ASSIGN"])
        # must have a type call
        if not self.match(TT["TYPE_CALL"]):
            raise ParseError(
                f"Constants must use a type function at line {self.current().line}"
            )
        tc = self.parse_type_call()
        if self.match(TT["SEMICOLON"]):
            self.consume()
        return VarDecl(name, tc, const=True, static_type=tc.type_char)

    def parse_var_stmt(self) -> Node:
        # $x = expr;  or  $x += expr;  or  $x[index] = expr;
        name_tok = self.consume(TT["VAR"])
        name = name_tok.value

        # index assignment?
        if self.match(TT["LBRACKET"]):
            self.consume()
            index = self.parse_expr()
            self.consume(TT["RBRACKET"])
            op = self.parse_assign_op()
            expr = self.parse_expr()
            if self.match(TT["SEMICOLON"]):
                self.consume()
            return IndexAssign(VarRef(name), index, op, expr)

        op = self.parse_assign_op()
        expr = self.parse_expr()
        if self.match(TT["SEMICOLON"]):
            self.consume()

        if op == "=":
            return VarDecl(name, expr)
        else:
            return Assign(VarRef(name), op, expr)

    def parse_assign_op(self) -> str:
        for tt, sym in [
            (TT["PLUS_ASSIGN"], "+="),
            (TT["MINUS_ASSIGN"], "-="),
            (TT["STAR_ASSIGN"], "*="),
            (TT["SLASH_ASSIGN"], "/="),
            (TT["PERCENT_ASSIGN"], "%="),
            (TT["ASSIGN"], "="),
        ]:
            if self.match(tt):
                self.consume()
                return sym
        raise ParseError(f"Expected assignment operator at line {self.current().line}")

    def parse_if(self) -> IfStmt:
        self.consume(TT["IF"])
        self.consume(TT["LPAREN"])
        cond = self.parse_expr()
        self.consume(TT["RPAREN"])
        then = self.parse_block()
        elseifs = []
        else_body = None
        while self.match(TT["ELSE_IF"]):
            self.consume()
            self.consume(TT["LPAREN"])
            ei_cond = self.parse_expr()
            self.consume(TT["RPAREN"])
            ei_body = self.parse_block()
            elseifs.append((ei_cond, ei_body))
        if self.match(TT["ELSE"]):
            self.consume()
            else_body = self.parse_block()
        return IfStmt(cond, then, elseifs, else_body)

    def parse_while(self) -> WhileStmt:
        self.consume(TT["WHILE"])
        self.consume(TT["LPAREN"])
        cond = self.parse_expr()
        self.consume(TT["RPAREN"])
        body = self.parse_block()
        return WhileStmt(cond, body)

    def parse_for(self) -> ForStmt:
        # \($i = i(0); $i < 10; $i += 1) { ... }
        self.consume(TT["FOR"])
        self.consume(TT["LPAREN"])
        init = self.parse_stmt()  # already consumed semicolon
        cond = self.parse_expr()
        self.consume(TT["SEMICOLON"])
        # update part - re-use var stmt parsing logic inline
        update = self.parse_update()
        self.consume(TT["RPAREN"])
        body = self.parse_block()
        return ForStmt(init, cond, update, body)

    def parse_update(self) -> Node:
        """Parse an assignment or augmented-assignment without consuming a semicolon."""
        if self.match(TT["VAR"]):
            name = self.consume().value
            if self.match(TT["LBRACKET"]):
                self.consume()
                index = self.parse_expr()
                self.consume(TT["RBRACKET"])
                op = self.parse_assign_op()
                expr = self.parse_expr()
                return IndexAssign(VarRef(name), index, op, expr)
            op = self.parse_assign_op()
            expr = self.parse_expr()
            if op == "=":
                return VarDecl(name, expr)
            return Assign(VarRef(name), op, expr)
        return self.parse_expr()

    def parse_when(self) -> WhenStmt:
        self.consume(TT["WHEN"])
        self.consume(TT["LPAREN"])
        signal = self.parse_expr()
        self.consume(TT["RPAREN"])
        body = self.parse_block()
        return WhenStmt(signal, body)

    def parse_return(self) -> ReturnStmt:
        self.consume(TT["RETURN"])
        if self.match(TT["SEMICOLON"]):
            self.consume()
            return ReturnStmt(NullLit())
        expr = self.parse_expr()
        if self.match(TT["SEMICOLON"]):
            self.consume()
        return ReturnStmt(expr)

    # ── Expressions ──

    def parse_expr(self) -> Node:
        return self.parse_or()

    def parse_or(self) -> Node:
        left = self.parse_and()
        while self.match(TT["OR"]):
            self.consume()
            right = self.parse_and()
            left = BinOp(left, "||", right)
        return left

    def parse_and(self) -> Node:
        left = self.parse_equality()
        while self.match(TT["AND"]):
            self.consume()
            right = self.parse_equality()
            left = BinOp(left, "&&", right)
        return left

    def parse_equality(self) -> Node:
        left = self.parse_comparison()
        while self.match(TT["EQ"], TT["NEQ"]):
            op = self.consume().value
            right = self.parse_comparison()
            left = BinOp(left, op, right)
        return left

    def parse_comparison(self) -> Node:
        left = self.parse_additive()
        while self.match(TT["LT"], TT["GT"], TT["LTE"], TT["GTE"]):
            op = self.consume().value
            right = self.parse_additive()
            left = BinOp(left, op, right)
        return left

    def parse_additive(self) -> Node:
        left = self.parse_multiplicative()
        while self.match(TT["PLUS"], TT["MINUS"]):
            op = self.consume().value
            right = self.parse_multiplicative()
            left = BinOp(left, op, right)
        return left

    def parse_multiplicative(self) -> Node:
        left = self.parse_unary()
        while self.match(TT["STAR"], TT["SLASH"], TT["PERCENT"]):
            op = self.consume().value
            right = self.parse_unary()
            left = BinOp(left, op, right)
        return left

    def parse_unary(self) -> Node:
        if self.match(TT["NOT"]):
            self.consume()
            return UnaryOp("!", self.parse_unary())
        if self.match(TT["MINUS"]):
            self.consume()
            return UnaryOp("-", self.parse_unary())
        return self.parse_postfix()

    def parse_postfix(self) -> Node:
        expr = self.parse_primary()
        while True:
            if self.match(TT["DOT"]):
                self.consume()
                attr = self.consume(TT["IDENT"]).value
                if self.match(TT["LPAREN"]):
                    self.consume()
                    args = self.parse_args()
                    self.consume(TT["RPAREN"])
                    expr = MethodCall(expr, attr, args)
                else:
                    expr = AttrAccess(expr, attr)
            elif self.match(TT["LBRACKET"]):
                self.consume()
                index = self.parse_expr()
                self.consume(TT["RBRACKET"])
                expr = IndexAccess(expr, index)
            else:
                break
        return expr

    def parse_primary(self) -> Node:
        tok = self.current()

        if tok.type == TT["TYPE_CALL"]:
            return self.parse_type_call()

        if tok.type == TT["NUMBER"]:
            self.consume()
            return NumberLit(tok.value)

        if tok.type == TT["STRING"]:
            self.consume()
            return StringLit(tok.value)

        if tok.type == TT["BOOL"]:
            self.consume()
            return BoolLit(tok.value)

        if tok.type == TT["NULL"]:
            self.consume()
            return NullLit()

        if tok.type == TT["VAR"]:
            self.consume()
            return VarRef(tok.value)

        if tok.type == TT["CONST"]:
            self.consume()
            return ConstRef(tok.value)

        if tok.type == TT["IDENT"]:
            name = self.consume().value
            if self.match(TT["LPAREN"]):
                self.consume()
                args = self.parse_args()
                self.consume(TT["RPAREN"])
                if name == "alarm":
                    return AlarmCall()
                return FuncCall(name, args)
            return VarRef(name)  # bare identifier used as reference

        if tok.type == TT["LPAREN"]:
            self.consume()
            expr = self.parse_expr()
            self.consume(TT["RPAREN"])
            return expr

        if tok.type == TT["LBRACKET"]:
            self.consume()
            elements = []
            while not self.match(TT["RBRACKET"]):
                elements.append(self.parse_expr())
                if self.match(TT["COMMA"]):
                    self.consume()
            self.consume(TT["RBRACKET"])
            return ArrayLit(elements)

        if tok.type == TT["LBRACE"]:
            self.consume()
            pairs = []
            while not self.match(TT["RBRACE"]):
                key = self.parse_expr()
                self.consume(TT["ASSIGN"]) if self.match(
                    TT["ASSIGN"]
                ) else self.consume(
                    TT["COLON"] if hasattr(TT, "COLON") else TT["ASSIGN"]
                )
                # Actually use = or : for kv pair
                val = self.parse_expr()
                pairs.append((key, val))
                if self.match(TT["COMMA"]):
                    self.consume()
            self.consume(TT["RBRACE"])
            return HashLit(pairs)

        raise ParseError(
            f"Unexpected token {tok.type} ({tok.value!r}) at line {tok.line}"
        )

    def parse_type_call(self) -> TypeCast:
        type_char = self.consume(TT["TYPE_CALL"]).value
        self.consume(TT["LPAREN"])
        if self.match(TT["RPAREN"]):
            self.consume()
            # empty type call → default value
            defaults = {
                "i": NumberLit(0),
                "f": NumberLit(0.0),
                "s": StringLit(""),
                "b": BoolLit(False),
                "a": ArrayLit([]),
                "h": HashLit([]),
            }
            return TypeCast(type_char, defaults[type_char])
        expr = self.parse_expr()
        # handle var decl inside type call: i($y = 1)
        if self.match(TT["ASSIGN"]) or any(
            self.match(tt)
            for tt in [
                TT["PLUS_ASSIGN"],
                TT["MINUS_ASSIGN"],
                TT["STAR_ASSIGN"],
                TT["SLASH_ASSIGN"],
                TT["PERCENT_ASSIGN"],
            ]
        ):
            op = self.parse_assign_op()
            rhs = self.parse_expr()
            # We'll emit a VarDecl wrapped in a TypeCast — evaluator handles this
            if isinstance(expr, VarRef):
                inner = VarDecl(expr.name, rhs)
            else:
                inner = Assign(expr, op, rhs)
            self.consume(TT["RPAREN"])
            return TypeCast(type_char, inner)
        self.consume(TT["RPAREN"])
        return TypeCast(type_char, expr)

    def parse_args(self) -> List[Node]:
        args = []
        while not self.match(TT["RPAREN"]):
            args.append(self.parse_expr())
            if self.match(TT["COMMA"]):
                self.consume()
        return args


# ──────────────────────────────────────────────
# Runtime values / environment
# ──────────────────────────────────────────────
class ReturnException(Exception):
    def __init__(self, value):
        self.value = value


class AlarmSignal(Exception):
    def __init__(self, signal):
        self.signal = signal


class RuntimeError_(Exception):
    pass


class ClassInstance:
    def __init__(self, class_def: "ClassDef", env: "Environment"):
        self.class_def = class_def
        self.env = Environment(env)
        # execute class body in its own env
        interp = Interpreter.__singleton__
        for stmt in class_def.body:
            interp.exec(stmt, self.env)

    def get(self, attr: str):
        return self.env.get(attr)

    def set(self, attr: str, val):
        self.env.set(attr, val)

    def __repr__(self):
        return f"<instance of {self.class_def.name}>"


class Environment:
    def __init__(self, parent: Optional["Environment"] = None):
        self.vars: Dict[str, Any] = {}
        self.consts: Dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str) -> Any:
        if name in self.vars:
            return self.vars[name]
        if name in self.consts:
            return self.consts[name]
        if self.parent:
            return self.parent.get(name)
        raise RuntimeError_(f"Undefined variable '{name}'")

    def set(self, name: str, value: Any):
        # Walk up to find where this var lives
        if name in self.consts or (self.parent and self._find_const(name)):
            raise RuntimeError_(f"Cannot reassign constant '{name}'")
        env = self._find_var_env(name)
        if env:
            env.vars[name] = value
        else:
            self.vars[name] = value

    def define(self, name: str, value: Any, const=False, static_type=None):
        if const:
            if static_type:
                value = _coerce(value, static_type)
            self.consts[name] = value
        else:
            self.vars[name] = value

    def _find_var_env(self, name: str) -> Optional["Environment"]:
        if name in self.vars:
            return self
        if self.parent:
            return self.parent._find_var_env(name)
        return None

    def _find_const(self, name: str) -> bool:
        if name in self.consts:
            return True
        if self.parent:
            return self.parent._find_const(name)
        return False


def _coerce(value: Any, type_char: str) -> Any:
    try:
        if type_char == "i":
            return int(value) if value is not None else 0
        if type_char == "f":
            return float(value) if value is not None else 0.0
        if type_char == "s":
            return str(value) if value is not None else ""
        if type_char == "b":
            if isinstance(value, str):
                return value.lower() not in ("false", "0", "")
            return bool(value)
        if type_char == "a":
            if isinstance(value, list):
                return value
            return list(value) if hasattr(value, "__iter__") else [value]
        if type_char == "h":
            if isinstance(value, dict):
                return value
            return dict(value) if hasattr(value, "__iter__") else {}
    except Exception:
        pass
    return value


# ──────────────────────────────────────────────
# Interpreter
# ──────────────────────────────────────────────
class Interpreter:
    __singleton__: "Interpreter" = None  # type: ignore

    def __init__(self):
        Interpreter.__singleton__ = self
        self.global_env = Environment()
        self._setup_builtins()
        self.when_handlers: List[Tuple[Any, List[Node], Environment]] = []

    def _setup_builtins(self):
        env = self.global_env
        # print / output
        env.vars["print"] = lambda *args: print(*args)
        env.vars["println"] = lambda *args: print(*args)
        env.vars["input"] = lambda prompt="": input(prompt)
        env.vars["len"] = lambda x: len(x)
        env.vars["str"] = lambda x: str(x)
        env.vars["int"] = lambda x: int(x)
        env.vars["float"] = lambda x: float(x)
        env.vars["type"] = lambda x: type(x).__name__
        env.vars["push"] = lambda arr, v: arr.append(v) or arr
        env.vars["pop"] = lambda arr: arr.pop()
        env.vars["keys"] = lambda h: list(h.keys())
        env.vars["values"] = lambda h: list(h.values())
        env.vars["range"] = lambda *args: list(range(*args))

    def run(self, program: Program):
        for stmt in program.stmts:
            self.exec(stmt, self.global_env)

    def exec(self, node: Node, env: Environment) -> Any:
        t = type(node)

        if t is VarDecl:
            val = self.eval(node.expr, env)
            env.define(node.name, val, const=node.const, static_type=node.static_type)
            return val

        if t is Assign:
            rhs = self.eval(node.expr, env)
            if node.op == "=":
                new_val = rhs
            else:
                current = self.eval(node.target, env)
                new_val = self._apply_op(current, node.op[0], rhs)
            self._assign_target(node.target, new_val, env)
            return new_val

        if t is IndexAssign:
            container = self.eval(node.obj, env)
            index = self.eval(node.index, env)
            rhs = self.eval(node.expr, env)
            if node.op == "=":
                new_val = rhs
            else:
                current = container[index]
                new_val = self._apply_op(current, node.op[0], rhs)
            container[index] = new_val
            return new_val

        if t is FuncDef:
            env.define(node.name, node)
            return None

        if t is ClassDef:
            env.define(node.name, node)
            return None

        if t is IfStmt:
            if self._truthy(self.eval(node.cond, env)):
                return self._exec_block(node.then, env)
            for ei_cond, ei_body in node.elseifs:
                if self._truthy(self.eval(ei_cond, env)):
                    return self._exec_block(ei_body, env)
            if node.else_body is not None:
                return self._exec_block(node.else_body, env)
            return None

        if t is WhenStmt:
            # Register a when handler
            signal_val = self.eval(node.signal, env)
            self.when_handlers.append((signal_val, node.body, env))
            return None

        if t is WhileStmt:
            while self._truthy(self.eval(node.cond, env)):
                try:
                    self._exec_block(node.body, env)
                except ReturnException:
                    raise
            return None

        if t is ForStmt:
            self.exec(node.init, env)
            while self._truthy(self.eval(node.cond, env)):
                self._exec_block(node.body, env)
                self.exec(node.update, env)
            return None

        if t is ReturnStmt:
            val = self.eval(node.expr, env)
            raise ReturnException(val)

        if t is AlarmCall:
            # Trigger all matching when-handlers (matching any signal)
            signal = "alarm"
            for s, body, when_env in self.when_handlers:
                if s == signal or s is True or s == True:
                    self._exec_block(body, when_env)
            raise AlarmSignal(signal)

        # Expression statement
        return self.eval(node, env)

    def _exec_block(self, stmts: List[Node], parent_env: Environment) -> Any:
        env = Environment(parent_env)
        result = None
        for stmt in stmts:
            result = self.exec(stmt, env)
        return result

    def eval(self, node: Node, env: Environment) -> Any:
        t = type(node)

        if t is NumberLit:
            return node.value
        if t is StringLit:
            return node.value
        if t is BoolLit:
            return node.value
        if t is NullLit:
            return None
        if t is ArrayLit:
            return [self.eval(e, env) for e in node.elements]
        if t is HashLit:
            result = {}
            for k, v in node.pairs:
                result[self.eval(k, env)] = self.eval(v, env)
            return result

        if t is TypeCast:
            inner = node.expr
            # handle var decl inside type call
            if isinstance(inner, VarDecl):
                val = self.eval(inner.expr, env)
                coerced = _coerce(val, node.type_char)
                env.define(inner.name, coerced)
                return coerced
            val = self.eval(inner, env)
            return _coerce(val, node.type_char)

        if t is VarRef:
            return env.get(node.name)
        if t is ConstRef:
            return env.get(node.name)

        if t is AttrAccess:
            obj = self.eval(node.obj, env)
            if isinstance(obj, ClassInstance):
                return obj.get(node.attr)
            if isinstance(obj, dict):
                return obj[node.attr]
            raise RuntimeError_(
                f"Cannot access attribute '{node.attr}' on {type(obj).__name__}"
            )

        if t is IndexAccess:
            obj = self.eval(node.obj, env)
            idx = self.eval(node.index, env)
            return obj[idx]

        if t is BinOp:
            left = self.eval(node.left, env)
            right = self.eval(node.right, env)
            return self._binop(left, node.op, right)

        if t is UnaryOp:
            val = self.eval(node.expr, env)
            if node.op == "-":
                return -val
            if node.op == "!":
                return not self._truthy(val)

        if t is FuncCall:
            return self._call_func(node.name, node.args, env)

        if t is MethodCall:
            obj = self.eval(node.obj, env)
            args = [self.eval(a, env) for a in node.args]
            return self._call_method(obj, node.method, args)

        if t is AlarmCall:
            signal = "alarm"
            triggered = False
            for s, body, when_env in self.when_handlers:
                if s == signal or s is True:
                    self._exec_block(body, when_env)
                    triggered = True
            return triggered

        # statements used as expressions (e.g. inside for init)
        if t in (
            VarDecl,
            Assign,
            IndexAssign,
            FuncDef,
            ClassDef,
            IfStmt,
            WhileStmt,
            ForStmt,
            ReturnStmt,
            WhenStmt,
        ):
            return self.exec(node, env)

        raise RuntimeError_(f"Unknown node type {t.__name__}")

    def _call_func(self, name: str, arg_nodes: List[Node], env: Environment) -> Any:
        # built-in callable?
        try:
            fn = env.get(name)
        except RuntimeError_:
            raise RuntimeError_(f"Undefined function '{name}'")

        if callable(fn) and not isinstance(fn, (FuncDef, ClassDef)):
            args = [self.eval(a, env) for a in arg_nodes]
            return fn(*args)

        if isinstance(fn, ClassDef):
            # instantiate class
            instance = ClassInstance(fn, env)
            return instance

        if isinstance(fn, FuncDef):
            args = [self.eval(a, env) for a in arg_nodes]
            func_env = Environment(self.global_env)
            for (_, pname), val in zip(fn.params, args):
                func_env.define(pname, val)
            try:
                self._exec_block_in(fn.body, func_env)
            except ReturnException as e:
                return e.value
            return None

        raise RuntimeError_(f"'{name}' is not callable")

    def _exec_block_in(self, stmts: List[Node], env: Environment):
        for stmt in stmts:
            self.exec(stmt, env)

    def _call_method(self, obj: Any, method: str, args: List[Any]) -> Any:
        if isinstance(obj, ClassInstance):
            fn = obj.env.vars.get(method)
            if isinstance(fn, FuncDef):
                func_env = Environment(obj.env)
                for (_, pname), val in zip(fn.params, args):
                    func_env.define(pname, val)
                try:
                    self._exec_block_in(fn.body, func_env)
                except ReturnException as e:
                    return e.value
                return None
            raise RuntimeError_(f"Method '{method}' not found on {obj}")

        # built-in methods on lists / dicts / strings
        if isinstance(obj, list):
            if method == "push":
                obj.append(args[0])
                return obj
            if method == "pop":
                return obj.pop()
            if method == "length":
                return len(obj)
            if method == "join":
                sep = args[0] if args else ","
                return sep.join(str(x) for x in obj)
        if isinstance(obj, dict):
            if method == "get":
                return obj.get(args[0])
            if method == "set":
                obj[args[0]] = args[1]
                return obj
            if method == "keys":
                return list(obj.keys())
            if method == "values":
                return list(obj.values())
        if isinstance(obj, str):
            if method == "length":
                return len(obj)
            if method == "upper":
                return obj.upper()
            if method == "lower":
                return obj.lower()
            if method == "split":
                sep = args[0] if args else " "
                return obj.split(sep)
            if method == "contains":
                return args[0] in obj
            if method == "replace":
                return obj.replace(args[0], args[1])
        raise RuntimeError_(f"Unknown method '{method}' on {type(obj).__name__}")

    def _assign_target(self, target: Node, value: Any, env: Environment):
        if isinstance(target, VarRef):
            env.set(target.name, value)
        elif isinstance(target, AttrAccess):
            obj = self.eval(target.obj, env)
            if isinstance(obj, ClassInstance):
                obj.set(target.attr, value)
            else:
                raise RuntimeError_(f"Cannot set attribute on {type(obj).__name__}")
        else:
            raise RuntimeError_(f"Invalid assignment target {type(target).__name__}")

    def _apply_op(self, current: Any, op_char: str, rhs: Any) -> Any:
        ops = {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b,
            "%": lambda a, b: a % b,
        }
        return ops[op_char](current, rhs)

    def _binop(self, left: Any, op: str, right: Any) -> Any:
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise RuntimeError_("Division by zero")
            return left / right
        if op == "%":
            return left % right
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right
        if op == "&&":
            return self._truthy(left) and self._truthy(right)
        if op == "||":
            return self._truthy(left) or self._truthy(right)
        raise RuntimeError_(f"Unknown operator {op!r}")

    def _truthy(self, val: Any) -> bool:
        if val is None or val is False:
            return False
        if isinstance(val, (int, float)) and val == 0:
            return False
        if isinstance(val, str) and val == "":
            return False
        if isinstance(val, (list, dict)) and len(val) == 0:
            return False
        return True


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
def interpret(source: str):
    try:
        tokens = tokenize(source)
    except LexerError as e:
        print(f"[Lexer Error] {e}", file=sys.stderr)
        return

    try:
        parser = Parser(tokens)
        ast = parser.parse()
    except ParseError as e:
        print(f"[Parse Error] {e}", file=sys.stderr)
        return

    interp = Interpreter()
    try:
        interp.run(ast)
    except RuntimeError_ as e:
        print(f"[Runtime Error] {e}", file=sys.stderr)
    except AlarmSignal as e:
        pass  # alarm already triggered its when-handlers


def main():
    if len(sys.argv) < 2:
        # REPL mode
        print("Custom Language Interpreter — type 'exit' to quit")
        buf = []
        while True:
            try:
                line = input(">>> " if not buf else "... ")
            except EOFError:
                break
            if line.strip() == "exit":
                break
            buf.append(line)
            if line.strip().endswith(";") or line.strip().endswith("}"):
                interpret("\n".join(buf))
                buf = []
    else:
        with open(sys.argv[1], "r") as f:
            source = f.read()
        interpret(source)


if __name__ == "__main__":
    main()
