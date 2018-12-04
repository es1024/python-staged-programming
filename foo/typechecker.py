import ast

from llvmlite import ir as llvm
from . import irtypes as ir

def assign(f):
    def wrap(self, node):
        rv = f(self, node)
        node.type = rv
        return rv
    return wrap

class TypeChecker(ast.NodeVisitor):
    int_type = llvm.IntType(32)
    float_type = llvm.DoubleType()
    bool_type = llvm.IntType(1)

    @staticmethod
    def analyze(func, global_vars):
        func.signature = TypeChecker(global_vars).visit(func)

    def __init__(self, global_vars):
        super(TypeChecker, self).__init__()
        self.symbol_table = {}
        self.return_type = None
        for n, typ in global_vars.items():
            self.symbol_table[n] = typ

    def visit_FuncDef(self, node):
        type_builder = LLVMTypeBuilder()
        self.return_type = type_builder.visit(node.return_type)
        argument_types = list(map(type_builder.visit, node.arg_types))
        for i in range(len(node.args)):
            self.symbol_table[node.args[i]] = argument_types[i]
        self.visit(node.body)
        return llvm.FunctionType(self.return_type, tuple(argument_types))

    def visit_FuncCall(self, node):
        if node.name not in self.symbol_table:
            raise NotImplementedError('function not found')
        node.type = self.symbol_table[node.name].return_type
        return node.type

    def visit_Array(self, node):
        if len(self.node.elts) == 0:
            raise NotImplementedError('array declared empty without type')
        typ = self.visit(self.node.elts[0])
        for i in node.elts:
            if typ != self.visit(i):
                raise NotImplementedError('array contains multiple types')
        return llvm.ArrayType(typ, len(self.node.elts))

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if node.op == ir.Bop.Add or node.op == ir.Bop.Sub or \
            node.op == ir.Bop.Mul or node.op == ir.Bop.Div or node.op == ir.Bop.Mod:
            if left == TypeChecker.int_type and right == TypeChecker.float_type:
                node.left = ir.CastToFloat(node.left)
                self.visit(node.left)
                node.type = TypeChecker.float_type
                return node.type
            elif left == TypeChecker.float_type and right == TypeChecker.int_type:
                node.right = ir.CastToFloat(node.right)
                self.visit(node.right)
                node.type = TypeChecker.float_type
                return node.type
            elif left == TypeChecker.int_type and right == TypeChecker.int_type:
                node.type = TypeChecker.int_type
                return node.type
            elif left == TypeChecker.float_type and right == TypeChecker.float_type:
                node.type = TypeChecker.float_type
                return node.type
            else:
                raise NotImplementedError("Operation argument not supported")
        elif node.op == ir.Bop.And or node.op == ir.Bop.Or:
            if left == TypeChecker.bool_type and right == TypeChecker.bool_type:
                node.type = TypeChecker.bool_type
                return node.type
            raise NotImplementedError("Operation argument not supported")
        raise NotImplementedError()

    def visit_CmpOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        if left == TypeChecker.int_type and right == TypeChecker.float_type:
            node.left = ir.CastToFloat(node.left)
            self.visit(node.left)
        elif left == TypeChecker.float_type and right == TypeChecker.int_type:
            node.right = ir.CastToFloat(node.right)
            self.visit(node.right)
        elif left == TypeChecker.int_type and right == TypeChecker.int_type:
            pass
        elif left == TypeChecker.float_type and right == TypeChecker.float_type:
            pass
        else:
            raise NotImplementedError("Operation argument not supported")
        if node.op == ir.Cop.EQ or node.op == ir.Cop.NE or \
            node.op == ir.Cop.LT or node.op == ir.Cop.GT or \
            node.op == ir.Cop.LE or node.op == ir.Cop.GE:
            node.type = TypeChecker.bool_type
            return node.type
        raise NotImplementedError()

    def visit_UnOp(self, node):
        arg = self.visit(node.e)
        if node.op == ir.Uop.Neg:
            if arg == TypeChecker.int_type:
                node.type = TypeChecker.int_type
            elif arg == TypeChecker.float_type:
                node.type = TypeChecker.float_type
            else:
                raise NotImplementedError("Operation argument not supported")
            return node.type
        elif node.op == ir.Uop.Not:
            node.type = TypeChecker.bool_type
            return node.type
        raise NotImplementedError()

    def visit_Ref(self, node):
        if node.name not in self.symbol_table:
            raise NotImplementedError("Reference not assigned")
        if node.index != None:
            i = self.visit(node.index)
            if i != TypeChecker.int_type:
                raise NotImplementedError()
            node.type = self.symbol_table[node.name].pointee
        else:
            node.type = self.symbol_table[node.name]
        return node.type

    def visit_IntConst(self, node):
        node.type = TypeChecker.int_type
        return node.type

    def visit_FloatConst(self, node):
        node.type = TypeChecker.float_type
        return node.type

    def visit_BoolConst(self, node):
        node.type = TypeChecker.bool_type
        return node.type

    def visit_CastToFloat(self, node):
        arg = self.visit(node.expr)
        if arg != TypeChecker.int_type:
            raise NotImplementedError("Only casts int to float")
        node.type = TypeChecker.float_type
        return node.type

    def visit_CastToInt(self, node):
        arg = self.visit(node.expr)
        if arg != TypeChecker.float_type:
            raise NotImplementedError("Only casts float to int")
        node.type = TypeChecker.int_type
        return node.type

    def visit_Assign(self, node):
        if node.ref.name in self.symbol_table:
            if node.ref.index:
                if self.symbol_table[node.ref.name].pointee != self.visit(node.val):
                    raise NotImplementedError("Inconsistent Type")
            elif self.visit(node.ref) != self.visit(node.val):
                raise NotImplementedError('Inconsistent type')
            self.symbol_table[node.ref.name] = self.visit(node.val)
            return None
        else:
            node.ref.type = self.visit(node.val)
            self.symbol_table[node.ref.name] = node.ref.type
            return None
        raise NotImplementedError("Assignment issue")

    def visit_Return(self, node):
        if self.visit(node.val) != self.return_type:
            raise NotImplementedError("Inconsistent return type")

    def visit_Block(self, node):
        for stmt in node.body:
            self.visit(stmt)

    def visit_If(self, node):
        self.visit(node.cond)
        self.visit(node.body)
        if node.else_body:
            self.visit(node.else_body)

    def visit_For(self, node):
        low = self.visit(node.min)
        high = self.visit(node.max)
        if low != TypeChecker.int_type or high != TypeChecker.int_type:
            raise NotImplementedError()
        self.visit(ir.Assign(ir.Ref(node.var), node.min))
        self.visit(node.body)

# Used to parse function signatures.
class LLVMTypeBuilder(ast.NodeVisitor):
    def __init__(self):
        super(LLVMTypeBuilder, self).__init__()

    def visit_Name(self, node: ast.Name):
        if node.id == 'int':
            return TypeChecker.int_type
        if node.id == 'float':
            return TypeChecker.float_type
        if node.id == 'bool':
            return TypeChecker.bool_type
        raise NotImplementedError('Type names must be either int or float')

    def visit_List(self, node: ast.List):
        if len(node.elts) != 1 or not isinstance(node.elts[0], ast.Name):
            raise NotImplementedError('only Lists over simple types allowed')
        return llvm.PointerType(self.visit(node.elts[0]))

    def generic_visit(self, node):
        raise NotImplementedError('Unsupported type expression')
