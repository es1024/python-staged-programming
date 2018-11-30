from macropy.core.quotes import macros, q, name

import ast
import astunparse

class SubexprVisitor(ast.NodeVisitor):
    """
    AST node visitor that just visits every node in a Python AST.
    """
    def generic_visit(self, node):
        for field, value in ast.iter_fields(node):
            setattr(node, field, self.visit(value))
        return node

    def visit_FunctionDef(self, node):
        node.body = list(map(self.visit, node.body))
        return node

    def visit_Num(self, node):
        return node

    def visit_list(self, nodes):
        r = list(map(self.visit, nodes))
        return r

class NameExtractor(SubexprVisitor):
    """
    AST node visitor to generate a set of all names used.
    """
    def __init__(self):
        self.names = set()

    def visit_Name(self, node):
        self.names.add(node.id)
        return node

def to_ast(maybe_ast):
    if isinstance(maybe_ast, ast.AST):
        return maybe_ast
    elif isinstance(maybe_ast, list):
        return list(map(to_ast, maybe_ast))
    else:
        return q[u[maybe_ast]]

class ProcessEscape(SubexprVisitor):
    """
    AST node visitor that transforms the AST to remove escapes.
    """
    def __init__(self, params, _globals, _locals):
        self.globals = _globals
        self.locals = _locals
        self.names = set(list(params))
        for p in params:
            self.locals[p] = q[name[p]]

    def visit_Assign(self, node):
        rv = self.generic_visit(node)
        for target in rv.targets:
            if hasattr(target, 'id'):
                self.names.add(target.id)
                self.locals[target.id] = q[name[target.id]]
        return rv

    def process_escape(self, node):
        ne = NameExtractor()
        ne.visit(node)
        _locals = self.locals.copy()
        for n in ne.names:
            _locals[n] = _locals[n] if n in _locals else q[name[n]]
        ev = eval(astunparse.unparse(node), self.globals, _locals)
        return self.visit(to_ast(ev))

    def visit_Name(self, node):
        if node.id not in self.names and hasattr(node, 'ctx') and type(node.ctx) == ast.Load:
            return self.process_escape(node)
        return node

    def visit_Set(self, node):
        assert len(node.elts) == 1
        return self.process_escape(node.elts[0])

    def visit_Captured(self, node):
        return to_ast(node.val)

