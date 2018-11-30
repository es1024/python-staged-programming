from macropy.core.quotes import macros, q, name

import ast
import astunparse

class SubexprVisitor(ast.NodeVisitor):
    """
    AST node visitor that just visits every node in a Python AST.
    """
    def generic_visit(self, node):
        return node

    def visit_FunctionDef(self, node):
        node.body = list(map(self.visit, node.body))
        return node

    def visit_Return(self, node):
        if node.value is not None:
            node.value = self.visit(node.value)
        return node

    def visit_Call(self, node):
        node.func = self.visit(node.func)
        node.args = list(map(self.visit, node.args))
        node.keywords = list(map(lambda x: (x[0], self.visit(x[1])), node.keywords))
        return node

    def visit_Expr(self, node):
        node.value = self.visit(node.value)
        return node

    def visit_Assign(self, node):
        node.targets = list(map(self.visit, node.targets))
        node.value = self.visit(node.value)
        return node

    def visit_BinOp(self, node):
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)
        return node

class NameExtractor(SubexprVisitor):
    """
    AST node visitor to generate a set of all names used.
    """
    def __init__(self):
        self.names = set()

    def visit_Name(self, node):
        self.names.add(node.id)
        return node

class CapturedExtractor(SubexprVisitor):
    """
    AST node visitor that converts macropy Captured objects into their value.
    """
    def visit_Captured(self, node):
        return node.val

class ProcessEscape(SubexprVisitor):
    """
    AST node visitor that transforms the AST to remove escapes.
    """
    def __init__(self, _globals, _locals):
        self.globals = _globals
        self.locals = _locals

    def visit_Set(self, node):
        assert len(node.elts) == 1
        ne = NameExtractor()
        ne.visit(node.elts[0])
        _locals = self.locals.copy()
        for n in ne.names:
            _locals[n] = _locals[n] if n in _locals else q[name[n]]
        ev = eval(astunparse.unparse(node.elts[0]), self.globals, _locals)
        return CapturedExtractor().visit(ev)

