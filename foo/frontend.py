import ast
import functools

from . import irtypes as ir


class Frontend(ast.NodeVisitor):
    """
    Translate a Python AST to our IR. Modified from CS294-141 assignment 2.
    """

    @staticmethod
    def type_name(obj):
        return obj.__class__.__name__

    def generic_visit(self, node):
        raise NotImplementedError('AST node type \'{}\' not implemented.'.format(self.type_name(node)))

    def visit_NameConstant(self, node):
        if node.value is not None:
            return ir.BoolConst(node.value)
        raise NotImplementedError('None keyword not supported')

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id == 'int':
                if len(node.args) != 1:
                    raise NotImplementedError('Casts expect single argument')
                arg = self.visit(node.args[0])
                return ir.CastToInt(arg)
            if node.func.id == 'float':
                if len(node.args) != 1:
                    raise NotImplementedError('Casts expect single argument')
                arg = self.visit(node.args[0])
                return ir.CastToFloat(arg)
            else:
                args = []
                for i in node.args:
                    args.append(self.visit(i))
                return ir.FuncCall(node.func.id, args)
        raise NotImplementedError('Problem with function name: ' + ast.dump(node))

    def visit_List(self, node):
        return ir.Array([self.visit(elt) for elt in node.elts]) 

    def visit_BinOp(self, node):
        # BinOp(expr left, operator op, expr right)
        # operator = Add | Sub | Mult | MatMult | Div | Mod | Pow | LShift | RShift | BitOr | BitXor | BitAnd | FloorDiv
        translate_op = {ast.Add: ir.Bop.Add, ast.Sub: ir.Bop.Sub, ast.Mult: ir.Bop.Mul,
                        ast.Div: ir.Bop.Div, ast.Mod: ir.Bop.Mod}
        op = translate_op.get(type(node.op), None)
        if not op:
            raise NotImplementedError(
                'BinOp \'{}\' not among Add, Sub, Mult, Div, Mod'.format(Frontend.type_name(node.op)))
        lhs = self.visit(node.left)
        rhs = self.visit(node.right)
        if op == ir.Bop.Div:
            lhs = ir.CastToFloat(lhs)
            rhs = ir.CastToFloat(rhs)
        return ir.BinOp(op=op, left=lhs, right=rhs)

    def visit_BoolOp(self, node):
        # BoolOp(boolop op, expr* values)
        # boolop = And | Or
        # This should be syntactically impossible in Python.
        assert len(node.values) >= 2
        assert type(node.op) in {ast.And, ast.Or}

        op = ir.Bop.And if isinstance(node.op, ast.And) else ir.Bop.Or
        values = [self.visit(t) for t in node.values]
        return functools.reduce(lambda y, x: ir.BinOp(op=op, left=x, right=y), values[::-1])

    @staticmethod
    def tr_op(op):
        translate_op = {ast.Eq: ir.Cop.EQ, ast.NotEq: ir.Cop.NE, ast.Lt: ir.Cop.LT,
                        ast.LtE: ir.Cop.LE, ast.Gt: ir.Cop.GT, ast.GtE: ir.Cop.GE}
        op_ = translate_op.get(type(op), None)
        if not op_:
            raise NotImplementedError(
                'CmpOp \'{}\' not among Eq, NotEq, Lt, LtE, Gt, GtE'.format(Frontend.type_name(op)))
        return op_

    def visit_Compare(self, node):
        # Compare(expr left, cmpop* ops, expr* comparators)
        # cmpop = Eq | NotEq | Lt | LtE | Gt | GtE | Is | IsNot | In | NotIn
        assert len(node.ops) == len(node.comparators)
        if len(node.comparators) != 1:
            raise NotImplementedError('chained comparisons')
        return ir.CmpOp(
            op=(self.tr_op(node.ops[0])),
            left=(self.visit(node.left)),
            right=(self.visit(node.comparators[0])))

    def visit_UnaryOp(self, node):
        # UnaryOp(unaryop op, expr operand)
        # unaryop = Invert | Not | UAdd | USub
        if isinstance(node.op, ast.UAdd):
            return self.visit(node.operand)
        translate_op = {ast.Not: ir.Uop.Not, ast.USub: ir.Uop.Neg}
        op = translate_op.get(type(node.op), None)
        if not op:
            raise NotImplementedError(
                'UnaryOp \'{}\' not among Not, UAdd, USub'.format(Frontend.type_name(node.op)))
        expr = self.visit(node.operand)
        return ir.UnOp(op=op, e=expr)

    def visit_Name(self, node):
        # Name(identifier id, expr_context ctx)
        # expr_context = Load | Store | Del | AugLoad | AugStore | Param
        assert not hasattr(node, 'ctx') or type(node.ctx) in {ast.Load, ast.Store}
        return ir.Ref(node.id)

    def visit_Subscript(self, node):
        # Subscript(expr value, slice slice, expr_context ctx)
        # slice = Slice(expr? lower, expr? upper, expr? step)
        #  | ExtSlice(slice* dims)
        #  | Index(expr value)
        assert type(node.ctx) in {ast.Load, ast.Store}

        ref = self.visit(node.value)
        if not isinstance(ref, ir.Ref) or ref.index:
            raise NotImplementedError('Subscripts can only be applied to base names')
        if not isinstance(node.slice, ast.Index):
            raise NotImplementedError('Array slicing not supported. Can only use particular indices')
        index = self.visit(node.slice.value)
        ref.index = index
        return ref

    def visit_Num(self, node):
        # Num(object n) -- a number as a PyObject.
        if isinstance(node.n, int):
            return ir.IntConst(val=node.n)
        if isinstance(node.n, float):
            return ir.FloatConst(val=node.n)
        raise NotImplementedError('{} is not int or float'.format(Frontend.type_name(node.n)))

    def visit_Assign(self, node):
        # Assign(expr* targets, expr value)
        if len(node.targets) != 1:
            raise NotImplementedError('chained assignment')
        return ir.Assign(ref=(self.visit(node.targets[0])), val=(self.visit(node.value)))

    def visit_AugAssign(self, node):
        # AugAssign(expr target, operator op, expr value)
        value = ast.BinOp(left=node.target, op=node.op, right=node.value)
        return self.visit(ast.Assign(targets=[node.target], value=value))

    def visit_If(self, node):
        # If(expr test, stmt* body, stmt* orelse)
        return ir.If(self.visit(node.test), self.make_block(node.body), self.make_block(node.orelse))

    def extract_loop_bounds(self, node):
        # matches: range(<expr>, <expr>)
        if not isinstance(node, ast.Call):
            raise NotImplementedError('For loop ranges must be given as range(expr, expr)')
        if not isinstance(node.func, ast.Name):
            raise NotImplementedError('For loop ranges must be given as range(expr, expr)')
        if node.func.id != 'range':
            raise NotImplementedError('For loop ranges must be given as range(expr, expr)')
        if node.keywords:
            raise NotImplementedError('For loop ranges must be given as range(expr, expr)')
        assert isinstance(node.args, list)
        if len(node.args) == 2:
            return self.visit(node.args[0]), self.visit(node.args[1])
        if len(node.args) == 1:
            return ir.IntConst(0), self.visit(node.args[0])
        raise NotImplementedError('For loop ranges must be given as range(expr, expr)')

    def visit_For(self, node):
        # For(expr target, expr iter, stmt* body, stmt* orelse)
        var = self.visit(node.target)
        if not isinstance(var, ir.Ref) or var.index:
            raise NotImplementedError('For loop variable must be simple name')
        if node.orelse:
            raise NotImplementedError('Else on for loops not supported')
        low, high = self.extract_loop_bounds(node.iter)
        return ir.For(var=var.name, min=low, max=high, body=(self.make_block(node.body)))

    def visit_Return(self, node):
        # Return(expr? value)
        if node.value is None:
            raise NotImplementedError('functions must return a value')
        return ir.Return(self.visit(node.value))

    def make_block(self, statements):
        assert isinstance(statements, list)
        body = list(map(self.visit, statements))
        return ir.Block(body) if body else None

    def visit_FunctionDef(self, node):
        # FunctionDef(identifier name, arguments args,
        #             stmt* body, expr* decorator_list, expr? returns)

        if node.args.defaults:
            raise NotImplementedError('arguments cannot have default values')
        if node.args.kwarg or node.args.kw_defaults or node.args.kwonlyargs:
            raise NotImplementedError('functions cannot have keyword arguments')
        if node.args.vararg:
            raise NotImplementedError('functions cannot accept variable numbers of arguments')

        args = [arg.arg for arg in node.args.args]
        assert isinstance(node.body, list)
        body = self.make_block(node.body)

        func = ir.FuncDef(name=node.name, args=args, body=body)
        func.arg_types = [arg.annotation for arg in node.args.args]
        if any(ty is None for ty in func.arg_types):
            raise NotImplementedError('functions must specify types for all arguments')
        func.return_type = node.returns
        if func.return_type is None:
            raise NotImplementedError('functions must specify return types')
        return func

    def visit_Expr(self, node):
        if isinstance(node.value, list):
            return ir.Block([self.visit(v) for v in node.value])
        else:
            return ir.Block([self.visit(node.value)])

