import ast

from llvmlite import ir as llvm
from .irtypes import Uop, Bop, Cop, Assign

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
    def analyze(func):
        func.signature = TypeChecker().visit(func)

    def __init__(self):
        super(TypeChecker, self).__init__()
        self.symbol_table = {}
        self.return_type = None

    def visit_FuncDef(self, node):
        type_builder = LLVMTypeBuilder()
        self.return_type = type_builder.visit(node.return_type)
        argument_types = list(map(type_builder.visit, node.arg_types))
        for arg, arg_type in zip(node.args, argument_types):
            self.symbol_table[arg] = arg_type
        btype = None
        if node.body:
            btype = self.visit(node.body)
        if btype != self.return_type:
            raise TypeError('bad return type')
        return llvm.FunctionType(self.return_type, tuple(argument_types))

    def visit_Block(self, node):
        for b in node.body:
            btype = self.visit(b)
            if btype is not None:
                if btype != self.return_type:
                    raise NotImplementedError('bad return type')
                return btype

    @assign
    def visit_IntConst(self, node):
        return self.int_type

    @assign
    def visit_FloatConst(self, node):
        return self.float_type

    @assign
    def visit_BoolConst(self, node):
        return self.bool_type

    @assign
    def visit_UnOp(self, node):
        if node.op == Uop.Neg:
            etype = self.visit(node.e)
            if etype == self.bool_type:
                raise NotImplementedError('Cannot negate boolean')
            return etype
        else:
            etype = self.visit(node.e)
            return self.bool_type

    @assign
    def visit_BinOp(self, node):
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)
        if node.op in [Bop.Add, Bop.Sub, Bop.Mul, Bop.Mod]:
            if self.bool_type in [left_type, right_type] and left_type != right_type:
                raise NotImplementedError('boolean mixed arithmetic not supported')
            if left_type != right_type:
                return self.float_type
            else:
                return left_type
        elif node.op == Bop.Div:
            return self.float_type
        else:
            if left_type != right_type:
                raise NotImplementedError('boolop must have same type')
            return left_type

    @assign
    def visit_CmpOp(self, node):
        left_type = self.visit(node.left)
        right_type = self.visit(node.right)

        if self.bool_type in [left_type, right_type] and left_type != right_type:
                raise NotImplementedError('cannot compare boolean with nonboolean')
        return self.bool_type

    @assign
    def visit_Ref(self, node):
        try:
            rtype = self.symbol_table[node.name]
        except KeyError:
            raise TypeError('ref undefined')
        if node.index is None:
            return rtype
        if rtype in [self.int_type, self.float_type, self.bool_type]:
            raise TypeError('cannot dereference int/float/bool')
        if self.visit(node.index) != self.int_type:
            raise TypeError('cannot use non-integer indices')
        return rtype.pointee

    @assign
    def visit_CastToFloat(self, node):
        self.visit(node.expr)
        return self.float_type

    @assign
    def visit_CastToInt(self, node):
        self.visit(node.expr)
        return self.int_type

    def visit_Return(self, node):
        rtype = self.visit(node.val)
        if rtype != self.return_type:
            raise TypeError('bad return type')
        return rtype

    def visit_Assign(self, node):
        if node.ref.name in self.symbol_table:
            self.visit(node.ref)
            if node.ref.index is None:
                ltype = self.symbol_table[node.ref.name]
            else:
                ltype = self.symbol_table[node.ref.name].pointee
            rtype = self.visit(node.val)
            if ltype != rtype:
                raise TypeError('type mismatch in assignment')
        else:
            rtype = self.visit(node.val)
            if node.ref.index is None:
                self.symbol_table[node.ref.name] = rtype
            else:
                raise TypeError('cannot dereference None')

    def visit_If(self, node):
        btype = self.visit(node.cond)
        btype = self.visit(node.body)
        if node.else_body:
            etype = self.visit(node.else_body)
        else:
            etype = None
        if btype is not None:
            if btype != self.return_type:
                raise TypeError('bad return type')
        if etype is not None:
            if etype != self.return_type:
                raise TypeError('bad return type')
        if btype is not None and etype is not None:
            return self.return_type

    def visit_For(self, node):
        if self.visit(node.min) != self.int_type or self.visit(node.max) != self.int_type:
            raise NotImplementedError('for only supports integer indices')
        if node.var in self.symbol_table:
            if self.symbol_table[node.var] != self.int_type:
                raise TypeError('type mismatch in assignment')
        else:
            self.symbol_table[node.var] = self.int_type
        return self.visit(node.body)


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
