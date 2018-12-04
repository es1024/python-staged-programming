import ast
from enum import Enum

"""
Expr = BinOp(Bop op, Expr left, Expr right)
     | CmpOp(Cop op, Expr left, Expr right)
     | UnOp(Uop op, Expr e)
     | Ref(Str name, Expr? index)
     | FloatConst(float val)
     | IntConst(int val)
     | FuncCall(Str name, Expr* args)

Uop = Neg | Not
Bop = Add | Sub | Mul | Div | Mod | And | Or
Cop = EQ | NE | LT | GT | LE | GE

Stmt = Assign(Ref ref, Expr val)
     | Block(Stmt* body)
     | If(Expr cond, Stmt body, Stmt? elseBody)
     | For(Str var, Expr min, Expr max, Stmt body)
     | Return(Expr val)
     | FuncDef(Str name, Str* args, Stmt body)
"""

class Uop(Enum):
    Neg = 0
    Not = 1


class Bop(Enum):
    Add = 0
    Sub = 1
    Mul = 2
    Div = 3
    Mod = 4
    And = 5
    Or = 6


class Cop(Enum):
    EQ = 0
    NE = 1
    LT = 2
    GT = 3
    LE = 4
    GE = 5


class FuncCall(ast.AST):
    _fields = ['name', 'args']

class IntConst(ast.AST):
    _fields = ['val', ]


class FloatConst(ast.AST):
    _fields = ['val', ]


class BoolConst(ast.AST):
    _fields = ['val', ]


class UnOp(ast.AST):
    _fields = ['op', 'e']


class BinOp(ast.AST):
    _fields = ['op', 'left', 'right']


class CmpOp(ast.AST):
    _fields = ['op', 'left', 'right']


class Ref(ast.AST):
    _fields = ['name', 'index']

    def __init__(self, name, index=None, *args, **kwargs):
        super().__init__(name, index, *args, **kwargs)


class CastToFloat(ast.AST):
    """Promotes an int type to a float type"""
    _fields = ['expr']


class CastToInt(ast.AST):
    """Truncates a float type to an int type"""
    _fields = ['expr']


class Return(ast.AST):
    _fields = ['val', ]


class Assign(ast.AST):
    _fields = ['ref', 'val']


class If(ast.AST):
    _fields = ['cond', 'body', 'else_body']

    def __init__(self, cond, body, else_body=None, *args, **kwargs):
        super().__init__(cond, body, else_body, *args, **kwargs)


class For(ast.AST):
    _fields = ['var', 'min', 'max', 'body']


class Block(ast.AST):
    _fields = ['body', ]


class FuncDef(ast.AST):
    _fields = ['name', 'args', 'body']

