import ast
import operator

from .irtypes import Uop, Bop, Cop


class Interpreter(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        from collections import defaultdict
        self.syms = defaultdict(dict)
        self.cur_fun = None

    @staticmethod
    def visit_str(node):
        return node

    def visit_BinOp(self, node):
        tr_op = {
            Bop.And: operator.and_,
            Bop.Or: operator.or_,
            Bop.Mod: operator.mod,
            Bop.Div: operator.truediv,
            Bop.Mul: operator.mul,
            Bop.Add: operator.add,
            Bop.Sub: operator.sub
        }
        left = self.visit(node.left)
        right = self.visit(node.right)
        return tr_op[node.op](left, right)

    def visit_CmpOp(self, node):
        tr_op = {
            Cop.EQ: operator.eq,
            Cop.NE: operator.ne,
            Cop.LT: operator.lt,
            Cop.LE: operator.le,
            Cop.GT: operator.gt,
            Cop.GE: operator.ge
        }
        left = self.visit(node.left)
        right = self.visit(node.right)
        return tr_op[node.op](left, right)

    def visit_UnOp(self, node):
        tr_op = {
            Uop.Not: operator.not_,
            Uop.Neg: operator.neg
        }
        expr = self.visit(node.e)
        return tr_op[node.op](expr)

    def visit_Ref(self, node):
        base = self.syms[self.cur_fun][node.name]
        if node.index:
            index = self.visit(node.index)
            return base[index]
        return base

    def visit_IntConst(self, node):
        return node.val

    def visit_FloatConst(self, node):
        return node.val

    def visit_BoolConst(self, node):
        return node.val

    def visit_Assign(self, node):
        val = self.visit(node.val)
        if node.ref.index:
            index = self.visit(node.ref.index)
            self.syms[self.cur_fun][node.ref.name][index] = val
        else:
            self.syms[self.cur_fun][node.ref.name] = val

    def visit_Block(self, node):
        for stmt in node.body:
            val = self.visit(stmt)
            if val is not None:
                return val

    def visit_If(self, node):
        cond = self.visit(node.cond)
        val = None
        if cond:
            val = self.visit(node.body)
        elif node.else_body:
            val = self.visit(node.else_body)
        return val

    def visit_For(self, node):
        low = self.visit(node.min)
        high = self.visit(node.max)
        for i in range(low, high):
            self.syms[self.cur_fun][node.var] = i
            val = self.visit(node.body)
            if val is not None:
                return val

    def visit_Return(self, node):
        return self.visit(node.val)

    def visit_CastToFloat(self, node):
        return float(self.visit(node.expr))

    def visit_CastToInt(self, node):
        return int(self.visit(node.expr))

    def call_fun(self, node, *args):
        for name, value in zip(node.args, args):
            self.syms[self.cur_fun][name] = value
        ret = self.visit(node.body)
        return ret

