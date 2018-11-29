from macropy.core.quotes import macros, q, name, ast_literal
from macropy.core.hquotes import macros, hq, u
import ast
import inspect
import astor
import astunparse

class SubexprVisitor(ast.NodeVisitor):
    def generic_visit(self, node):
        return node

    def visit_FunctionDef(self, node):
        node.body = list(map(self.visit, node.body))
        return node

    def visit_Return(self, node):
        if node.value is not None:
            node.value = self.visit(node.value)
        return node

class NameExtractor(SubexprVisitor):
    def __init__(self):
        self.names = set()
        self.names = {'a', 'b'} # TODO remove after subexprvisitor visits everything

    def visit_Name(self, node):
        self.names.add(node.id)

class ProcessEscape(SubexprVisitor):
    def visit_Set(self, node):
        assert len(node.elts) == 1
        def inner(___names, ___elt):
            ___old_globals = globals().copy()
            for ___n in ___names:
                globals()[___n] = q[u[___n]]
            ___v = eval(___elt)
            globals().clear()
            globals().update(___old_globals)
            return ___v
        ne = NameExtractor()
        ne.visit(node.elts[0])
        return inner(ne.names, astunparse.unparse(node.elts[0]))

def foo(f):
    parse_tree = ast.parse(inspect.getsource(f).strip()).body[0]
    unescaped = ProcessEscape().visit(parse_tree)

    print(astor.dump_tree(unescaped))
    return lambda *args, **kwargs: None


def gen_square(x):
    return hq[x * x]

@foo
def mse(a: float, b: float):
    return {gen_square(a)}

