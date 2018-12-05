import ast
import functools

import llvmlite.ir as llvm

from .typechecker import TypeChecker
from .irtypes import Uop, Bop, Cop, Ref, IntConst


class Backend(ast.NodeVisitor):
    def __init__(self, name, global_vars):
        super(Backend, self).__init__()
        self.module = llvm.Module(name=name)
        self.builder = None
        self.func = None
        self.function_type = None
        self.global_vars = {}
        self.symbol_table = {}
        self.prologue = None

        for name, typ in global_vars.items():
            self.global_vars[name] = llvm.Function(self.module, typ, name)

    @staticmethod
    def generate_llvm(func, global_vars):
        visitor = Backend(func.name, global_vars)
        visitor.visit(func)
        return (visitor.module, visitor.function_type)

    def visit_FuncDef(self, node):
        self.function_type = function_type = node.signature

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

    def visit_FuncCall(self, node):
        if node.name == "create_int_array" or node.name == "create_float_array" or node.name == "create_bool_array":
            if len(node.args) == 1:
                v = node.args[0]
                if isinstance(v, IntConst):
                    return self.builder.alloca(node.type.pointee, v.val)
            raise NotImplementedError('creating array function takes in a single int constant')
        elif node.name in self.global_vars:
            return self.builder.call(self.global_vars[node.name], node.args)
        raise NotImplementedError('function being called missing')

    def visit_Array(self, node):
        ptr = self.builder.alloca(node.type.pointee, len(node.elts))
        for i in range(len(node.elts)):
            ptr_shift = self.builder.gep(ptr, [self.const(i)])
            self.builder.store(self.visit(node.elts[i]), ptr_shift)
        return ptr

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
        ptr = self.builder.gep(self.symbol_table[node.name], [self.visit(node.index)])
        return self.builder.load(ptr)
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
            ptr = self.builder.gep(self.symbol_table[ref.name], [self.visit(ref.index)])
            self.builder.store(v, ptr)
 
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

        old_symbols = self.symbol_table.copy()

        self.builder = llvm.IRBuilder(iblock)
        self.visit(node.body)
        iblock = self.builder.block
        self.builder.branch(jblock)

        if_symbols = self.symbol_table
        self.symbol_table = old_symbols.copy()

        self.builder = llvm.IRBuilder(eblock)
        if node.else_body:
            self.visit(node.else_body)
            eblock = self.builder.block
        self.builder.branch(jblock)

        else_symbols = self.symbol_table
        self.symbol_table = old_symbols.copy()

        self.builder = llvm.IRBuilder(jblock)

        if_sk = set(if_symbols.keys())
        else_sk = set(else_symbols.keys())

        for s in if_sk:
            typ = if_symbols[s].type
            phi = self.builder.phi(typ)
            phi.add_incoming(if_symbols[s], iblock)
            if s in else_sk:
                phi.add_incoming(else_symbols[s], eblock)
            else:
                phi.add_incoming(llvm.Constant(typ, 0), eblock)
            self.symbol_table[s] = phi
        else_sk = else_sk.difference(if_sk)
        for s in else_sk:
            typ = else_symbols[s].type
            phi = self.builder.phi(typ)
            phi.add_incoming(else_symbols[s], eblock)
            phi.add_incoming(llvm.Constant(typ, 0), iblock)

    def visit_For(self, node):
        bblock = self.func.append_basic_block()
        self.builder.branch(bblock)
        self.builder = llvm.IRBuilder(bblock)

        mn = self.visit(node.min)
        mx = self.visit(node.max)
        ref = Ref(name=node.var)
        ref.type = TypeChecker.int_type
        self.assign(ref, mn, TypeChecker.int_type)

        cblock = self.func.append_basic_block()
        iblock = self.func.append_basic_block()
        self.builder.branch(cblock)

        self.builder = llvm.IRBuilder(cblock)
        for s in self.symbol_table.keys():
            typ = self.symbol_table[s].type
            phi = self.builder.phi(typ)
            phi.add_incoming(self.symbol_table[s], bblock)
            self.symbol_table[s] = phi

        self.builder = llvm.IRBuilder(iblock)
        old_symbols = self.symbol_table.copy()
        self.visit(node.body)
        new_iblock = self.builder.block
        self.assign(ref, self.builder.add(self.visit(ref), llvm.Constant(TypeChecker.int_type, 1)), TypeChecker.int_type)
        self.builder.branch(cblock)

        jblock = self.func.append_basic_block()

        self.builder = llvm.IRBuilder(cblock)

        old_sk = set(old_symbols.keys())
        new_sk = set(self.symbol_table.keys())
        for k in new_sk:
            if k in old_sk:
                old_symbols[k].add_incoming(self.symbol_table[k], new_iblock)
                self.symbol_table[k] = old_symbols[k]
            else:
                typ = self.symbol_table[k].type
                phi = self.builder.phi(typ)
                phi.add_incoming(self.symbol_table[k], new_iblock)
                phi.add_incoming(llvm.Constant(typ, 0), bblock)
                self.symbol_table[k] = phi

        vref = self.visit(ref)
        cond = self.builder.icmp_signed('<', vref, mx)
        self.builder.cbranch(cond, iblock, jblock)

        self.builder = llvm.IRBuilder(jblock)

    def generic_visit(self, node):
        raise NotImplementedError


