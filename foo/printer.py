import ast

from .irtypes import Uop, Bop, Cop


class IRPrinter(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.indent_width = 4

    def indent(self, text: str) -> str:
        indentation = (' ' * self.indent_width)
        return indentation + text.replace('\n', '\n' + indentation)

    @staticmethod
    def visit_str(node):
        return node

    def visit_Uop(self, node):
        tr = {Uop.Neg: '-', Uop.Not: 'not'}
        return tr[node]

    def visit_Bop(self, node):
        tr = {Bop.Add: '+', Bop.Sub: '-', Bop.Mul: '*', Bop.Div: '/', Bop.Mod: '%', Bop.And: 'and', Bop.Or: 'or'}
        return tr[node]

    def visit_Cop(self, node):
        tr = {Cop.EQ: '==', Cop.NE: '!=', Cop.LT: '<', Cop.GT: '>', Cop.LE: '<=', Cop.GE: '>='}
        return tr[node]

    def visit_BinOp(self, node):
        return '({}) {} ({})'.format(self.visit(node.left), self.visit(node.op), self.visit(node.right))

    def visit_CmpOp(self, node):
        return '({}) {} ({})'.format(self.visit(node.left), self.visit(node.op), self.visit(node.right))

    def visit_UnOp(self, node):
        return '{}({})'.format(self.visit(node.op), self.visit(node.e))

    def visit_Ref(self, node):
        name = node.name
        index = self.visit(node.index) if node.index else None
        return name if not index else '{}[{}]'.format(name, index)

    def visit_IntConst(self, node):
        return str(node.val)

    def visit_FloatConst(self, node):
        return str(node.val)

    def visit_BoolConst(self, node):
        return str(node.val)

    def visit_CastToInt(self, node):
        return "int({})".format(self.visit(node.expr))

    def visit_CastToFloat(self, node):
        return "float({})".format(self.visit(node.expr))

    def visit_Assign(self, node):
        return '{} = {}'.format(self.visit(node.ref), self.visit(node.val))

    def visit_Block(self, node):
        return '\n'.join(self.visit(stmt) for stmt in node.body)

    def visit_If(self, node):
        cond = self.visit(node.cond)
        body = self.visit(node.body)
        else_body = self.visit(node.else_body) if node.else_body else None
        out = 'if {}:\n{}'.format(cond, self.indent(body))
        if else_body:
            out += '\nelse:\n{}'.format(self.indent(else_body))
        return out

    def visit_For(self, node):
        return 'for {} in range({}, {}):\n{}'.format(
            self.visit(node.var),
            self.visit(node.min),
            self.visit(node.max),
            self.indent(self.visit(node.body)))

    def visit_Return(self, node):
        return 'return {}'.format(self.visit(node.val))

    def visit_FuncDef(self, node):
        return 'def {}({}):\n{}'.format(
            self.visit(node.name),
            ', '.join(self.visit(arg) for arg in node.args),
            self.indent(self.visit(node.body)))

