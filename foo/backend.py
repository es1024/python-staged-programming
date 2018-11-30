import ast
import functools

import llvmlite.ir as llvm

from .typechecker import TypeChecker
from .irtypes import Uop, Bop, Cop, Ref


class Backend(ast.NodeVisitor):
    def __init__(self, name):
        super(Backend, self).__init__()
        self.module = llvm.Module(name=name)
        self.builder = None
        self.func = None
        self.symbol_table = {}
        self.prologue = None

    @staticmethod
    def generate_llvm(func):
        visitor = Backend(func.name)
        visitor.visit(func)
        return visitor.module

    def visit_FuncDef(self, node):
        function_type = node.signature

        # Create the function from the module and signature
        self.func = llvm.Function(self.module, function_type, node.name)

        prologue = self.func.append_basic_block()
        self.builder = llvm.IRBuilder(prologue)

        args = self.func.args
        for name, arg in zip(node.args, args):
            self.symbol_table[name] = arg

        self.visit(node.body)
        self.builder.unreachable()

        return self.func

    def visit_Block(self, node):
        if not node.body:
            return
        block = self.func.append_basic_block()
        self.builder.branch(block)
        self.builder = llvm.IRBuilder(block)
        for b in node.body:
            self.visit(b)

    def const(self, v):
        if type(v) == int:
            return llvm.Constant(TypeChecker.int_type, v)
        elif type(v) == float:
            return llvm.Constant(TypeChecker.float_type, v)
        elif type(v) == bool:
            return llvm.Constant(TypeChecker.bool_type, v)
        else:
            raise NotImplementedError('bad type')

    def boolcast(self, v, orig_type):
        if orig_type == TypeChecker.int_type:
            return self.builder.select(
                self.builder.icmp_signed('==', v, self.const(0)),
                self.const(False),
                self.const(True)
            )
        elif orig_type == TypeChecker.float_type:
            return self.builder.select(
                self.builder.fcmp_ordered('==', v, self.const(0.0)),
                self.const(False),
                self.const(True)
            )
        else:
            return v

    def visit_IntConst(self, node):
        return self.const(node.val)

    def visit_FloatConst(self, node):
        return self.const(node.val)

    def visit_BoolConst(self, node):
        return self.const(node.val)

    def visit_UnOp(self, node):
        v = self.visit(node.e)

        op = None
        if node.op == Uop.Neg:
            if node.type == TypeChecker.int_type:
                op = self.builder.neg
            else:
                op = functools.partial(self.builder.fmul, self.const(-1.0))
        else:
            def not_op(e):
                bc = self.boolcast(e, node.e.type)
                return self.builder.not_(bc)
            op = not_op

        return op(v)

    def visit_BinOp(self, node):
        if node.op in {Bop.And, Bop.Or}:
            return self.visit_BoolOp(node)

        left = self.visit(node.left)
        right = self.visit(node.right)
        if node.type == TypeChecker.float_type:
            if node.left.type != TypeChecker.float_type:
                left = self.builder.sitofp(left, TypeChecker.float_type)
            if node.right.type != TypeChecker.float_type:
                right = self.builder.sitofp(right, TypeChecker.float_type)

        op = None
        if node.op == Bop.Add:
            if node.type == TypeChecker.float_type:
                op = self.builder.fadd
            else:
                op = self.builder.add
        elif node.op == Bop.Sub:
            if node.type == TypeChecker.float_type:
                op = self.builder.fsub
            else:
                op = self.builder.sub
        elif node.op == Bop.Mul:
            if node.type == TypeChecker.float_type:
                op = self.builder.fmul
            else:
                op = self.builder.mul
        elif node.op == Bop.Div:
            op = self.builder.fdiv
        elif node.op == Bop.Mod:
            if node.type == TypeChecker.float_type:
                op = self.builder.frem
            else:
                op = self.builder.srem

        return op(left, right)

    def visit_BoolOp(self, node):
        lblock = self.func.append_basic_block()
        block = lblock
        self.builder.branch(block)
        self.builder = llvm.IRBuilder(block)
        left = self.visit(node.left)

        rblock = self.func.append_basic_block()
        tblock = self.func.append_basic_block()
        
        leftbool = self.boolcast(left, node.left.type)
        bcond = self.const(node.op == Bop.And)
        self.builder.cbranch(
            self.builder.icmp_signed('==', leftbool, bcond),
            rblock,
            tblock
        )

        block = rblock
        self.builder = llvm.IRBuilder(block)
        right = self.visit(node.right)
        self.builder.branch(tblock)

        block = tblock
        self.builder = llvm.IRBuilder(block)

        v = self.builder.phi(node.type)
        v.add_incoming(left, lblock)
        v.add_incoming(right, rblock)

        return v

    def visit_CmpOp(self, node):
        op = {Cop.EQ: '==', Cop.NE: '!=', Cop.LT: '<', Cop.GT: '>', Cop.LE: '<=', Cop.GE: '>='}[node.op]
        left = self.visit(node.left)
        right = self.visit(node.right)
        if node.left.type == TypeChecker.float_type or node.right.type == TypeChecker.float_type:
            if node.left.type != TypeChecker.float_type:
                left = self.builder.sitofp(left, TypeChecker.float_type)
            if node.right.type != TypeChecker.float_type:
                right = self.builder.sitofp(right, TypeChecker.float_type)
            cmp_ = self.builder.fcmp_ordered(op, left, right)
        elif node.left.type == TypeChecker.int_type:
            cmp_ = self.builder.icmp_signed(op, left, right)
        else:
            cmp_ = self.builder.icmp_unsigned(op, left, right)
        return self.builder.select(cmp_, self.const(True), self.const(False))

    def visit_Ref(self, node):
        base = self.symbol_table[node.name]
        if node.index is None:
            return base
        index = self.visit(node.index)
        if node.type == TypeChecker.bool_type:
            sz = 1
        else:
            sz = 4
        index = self.builder.mul(index, self.const(sz))
        base = self.builder.ptrtoint(base, TypeChecker.int_type)
        addr = self.builder.add(base, index)
        addr = self.builder.inttoptr(addr, node.type.as_pointer())
        return self.builder.load(addr)

    def visit_CastToFloat(self, node):
        if node.expr.type == TypeChecker.float_type:
            return self.visit(node.expr)
        else:
            expr = self.visit(node.expr)
            return self.builder.sitofp(expr, TypeChecker.float_type)

    def visit_CastToInt(self, node):
        if node.expr.type == TypeChecker.float_type:
            expr = self.visit(node.expr)
            return self.builder.fptosi(expr, TypeChecker.int_type)
        elif node.expr.type == TypeChecker.bool_type:
            expr = self.visit(node.expr)
            return self.builder.zext(expr, TypeChecker.int_type)
        else:
            return self.visit(node.expr)

    def visit_Return(self, node):
        v = self.visit(node.val)
        self.builder.ret(v)
        block = self.func.append_basic_block()
        self.builder = llvm.IRBuilder(block)

    def assign(self, ref, v, vtype):
        if ref.name in self.symbol_table:
            if ref.index is None:
                self.symbol_table[ref.name] = v
                return
            base = self.symbol_table[ref.name]
            index = self.visit(ref.index)
            if vtype == TypeChecker.bool_type:
                sz = 1
            else:
                sz = 4
            index = self.builder.mul(index, self.const(sz))
            base = self.builder.ptrtoint(base, TypeChecker.int_type)
            addr = self.builder.add(base, index)
            addr = self.builder.inttoptr(addr, vtype.as_pointer())
            self.builder.store(v, addr)
        else:
            self.symbol_table[ref.name] = v
    
    def visit_Assign(self, node):
        v = self.visit(node.val)
        self.assign(node.ref, v, node.val.type)

    def visit_If(self, node):
        cond = self.boolcast(self.visit(node.cond), node.cond.type)
        iblock = self.func.append_basic_block()
        eblock = self.func.append_basic_block()
        jblock = self.func.append_basic_block()
        
        cond = self.builder.icmp_unsigned('==', cond, self.const(True))
        self.builder.cbranch(cond, iblock, eblock)

        self.builder = llvm.IRBuilder(iblock)
        self.visit(node.body)
        self.builder.branch(jblock)

        self.builder = llvm.IRBuilder(eblock)
        if node.else_body:
            self.visit(node.else_body)
        self.builder.branch(jblock)

        self.builder = llvm.IRBuilder(jblock)

    def visit_For(self, node):
        mn = self.visit(node.min)
        mx = self.visit(node.max)
        ref = Ref(name=node.var)
        ref.type = TypeChecker.int_type
        self.assign(ref, mn, TypeChecker.int_type)

        iblock = self.func.append_basic_block()
        cblock = self.func.append_basic_block()
        jblock = self.func.append_basic_block()
        self.builder.branch(cblock)
        
        self.builder = llvm.IRBuilder(iblock)
        self.visit(node.body)
        self.builder.branch(cblock)

        self.builder = llvm.IRBuilder(cblock)
        vref = self.visit(ref)
        cond = self.builder.icmp_signed('<', vref, mx)
        self.builder.cbranch(cond, iblock, jblock)

        self.builder = llvm.IRBuilder(jblock)

    def generic_visit(self, node):
        raise NotImplementedError


