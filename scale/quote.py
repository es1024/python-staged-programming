from macropy.core.macros import Macros
from macropy.core.hquotes import hq, ast, name, ast_repr, ast_literal, Captured, Literal

macros = Macros()

@macros.expr
def q(tree, **kw):
    return hq(tree, **kw)

@macros.block
def q(tree, target, **kw):
    tree = hq(tree, **kw)
    return [ast.Assign([target], tree)]

macros.expose_unhygienic(ast)
macros.expose_unhygienic(ast_repr)
macros.expose_unhygienic(Captured)
macros.expose_unhygienic(Literal)

