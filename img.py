from scale import *
from scale.quote import macros, q, name, ast_literal
from llvmlite import ir as llvm
from math import floor, ceil
import numpy as np
import ast
import operator
import re

@scale.native
def malloc(x: int) -> [float]:
    pass

@scale.native
def free(x: [float]) -> int:
    pass

# represents a node in the IR
class IRNode:
    def __init__(self, kind, **kwargs):
        self.kind = kind
        for k, v in kwargs.items():
            setattr(self, k, v)

# represents actual image data
class ConcreteImage:
    def __init__(self, width=None, height=None, data=None):
        self.width = width
        self.height = height
        self.data = data

    def load(self, filename):
        with open(filename, "rb") as F:
            cur = None

            def _next():
                nonlocal cur, F
                cur = F.read(1)
            _next()
            def _isspace():
                return cur and cur in (b'\t', b'\r', b'\n', b' ', b'#')
            def _isdigit():
                return b'0' <= cur <= b'9'
            def _parseWhitespace():
                assert _isspace(), "expected at least one whitespace character"
                while _isspace():
                    if cur == b"#":
                        _next()
                        while cur != b"\n":
                            _next()
                    _next()
            def _parseInteger():
                assert _isdigit(), "expected a number"
                n = ""
                while _isdigit():
                    n += cur.decode('utf-8')
                    _next()
                return int(n)
            assert cur == b"P", "wrong magic number"
            _next()
            assert cur == b"6", "wrong magic number"
            _next()

            _parseWhitespace()
            self.width = _parseInteger()
            _parseWhitespace()
            self.height = _parseInteger()
            _parseWhitespace()
            precision = _parseInteger()
            assert precision == 255, "only supports 255 as max value"
            assert _isspace(), "expected whitespace after precision"
            data_as_string = F.read(self.width * self.height *3)
            # read the data as flat data
            self.data = [0.0] * (self.width * self.height)
            for i in range(self.width * self.height):
                r, g, b = data_as_string[3 * i + 0 : 3 * i + 3]
                self.data[i] = min(255, (r + g + b) / 3)
                x, y = i % 16, floor(i / 16)
            _next()
            assert cur == b'', "expected EOF"

    def save(self, filename):
        with open(filename, "wb") as F:
            F.write(bytes('P6\n{} {}\n{}\n'.format(self.width, self.height, 255), encoding='utf-8'))
            for i in range(self.width * self.height):
                v = self.data[i]
                v = floor(v)
                v = max(0, min(v, 255))
                F.write(bytes(v))
                F.write(bytes(v))
                F.write(bytes(v))

# represents an abstract computation that creates an image
class Image:
    def __init__(self, tree=None):
        self.tree = tree

    def constant(const):
        return Image(IRNode(kind='const', value=const))

    def input(index):
        return Image(IRNode(kind='input', index=index))

    def toimage(x):
        if isinstance(x, Image):
            return x
        elif isinstance(x, int) or isinstance(x, float):
            return Image.constant(x)
        return None

    def __pointwise(self, rhs, op):
        rhs = Image.toimage(rhs)
        return Image(IRNode(kind='operator', op=op, lhs=self.tree, rhs=rhs.tree))

    def __add__(self, rhs):
        return self.__pointwise(rhs, lambda x, y: q[ast_literal[x] + ast_literal[y]])

    def __sub__(self, rhs):
        return self.__pointwise(rhs, lambda x, y: q[ast_literal[x] - ast_literal[y]])

    def __mul__(self, rhs):
        return self.__pointwise(rhs, lambda x, y: q[ast_literal[x] * ast_literal[y]])

    def __div__(self, rhs):
        return self.__pointwise(rhs, lambda x, y: q[ast_literal[x] / ast_literal[y]])

    def shift(self, sx, sy):
        return Image(IRNode(kind='shift', sx=sx, sy=sy, value=self.tree))

    def run(self, method, *args):
        if not hasattr(self, method):
            if method == 'recompute':
                compile_ir = compile_ir_recompute
            elif method == 'image_wide':
                compile_ir = compile_ir_image_wide
            elif method == 'blocked':
                compile_ir = compile_ir_blocked
            else:
                raise ValueError("unknown method")
            setattr(self, method, compile_ir(self.tree))
            getattr(self, method).compile()
        implementation = getattr(self, method)
        imagedata = [None] * len(args)
        width = None
        height = None
        for i, im in enumerate(args):
            assert isinstance(im, ConcreteImage), "expected a concrete image"
            width, height = width or im.width, height or im.height
            assert width == im.width and height == im.height, "input size mismatch"
            imagedata[i] = im.data
        assert width and height, "there must be at least one input image"
        inputs = imagedata
        result = ConcreteImage(width, height, [0]*(width * height))
        implementation(width, height, result.data, inputs)
        return result

@scale
def load_data(W: int, H: int, data: [float], x: int, y: int) -> float:
    x = ((x % W) + W) % W
    y = ((y % H) + H) % H
    return data[y * W + x]

def compile_ir_recompute(tree):
    W = scale.var('W')
    H = scale.var('H')
    inputs = scale.var('inputs')

    def gen_tree(tree,x,y):
        if tree.kind == "const":
            return q[u[float(tree.value)]]
        elif tree.kind == "input":
            return q[load_data(W,H,inputs[u[tree.index]],x,y)]
        elif tree.kind == "operator":
            lhs = gen_tree(tree.lhs,x,y)
            rhs = gen_tree(tree.rhs,x,y)
            print(lhs, rhs)
            return tree.op(lhs,rhs)
        elif tree.kind == "shift":
            xn, yn = q[ast_literal[x] + u[tree.sx]],q[ast_literal[y] + u[tree.sy]]
            return gen_tree(tree.value,xn,yn)

    @scale.anonymous
    def body(W: int, H: int, output : [float], inputs: [[float]]) -> int:
        for y in range(H):
          for x in range(W):
            output[(y*W + x)] = { gen_tree(tree,x,y) }
        return 0

    return body


def createloopir(method, tree):
    num_uses = {}
    def countuse(tree):
        nonlocal num_uses
        if num_uses[tree]:
            num_uses[tree] = num_uses[tree] + 1
        else:
            num_uses[tree] = 1
            if tree.kind == 'shift':
                countuse(tree.value)
                countuse(tree.value) # force all shifts to be treated as things that are reified
            elif tree.kiind == 'operator':
                countuse(tree.lhs)
                countuse(tree.rhs)
    countuse(tree)

    loopir = []
    treemap = {}
    def convert(tree):
        nonlocal loopir, treemap
        if tree.kind == 'const':
            return tree
        elif method == 'image_wide' and tree.kind == 'input':
            return tree
        if treemap[tree]: return treemap[tree]
        if tree.kind == 'operator':
            lhs = convert(tree.lhs)
            rhs = convert(tree.rhs)
            ntree = IRNode(kind='operator', op=tree.op, lhs=lhs, rhs=rhs)
        elif tree.kind == 'shift':
            value = convert(tree.value)
            ntree = IRNode(kind='shift', sx=tree.sx, sy=tree.sy, value=value)
        elif tree.kind == 'input':
            ntree = tree
        else:
            raise ValueError('unknown kind')

        if num_uses[tree] > 1:
            store = IRNode(kind='storetemp', value=ntree, maxstencil=0)
            loopir.append(store)
            ntree = IRNode(kind='loadtemp', temp=store)
        treemap[tree] = ntree
        return nntree

    result = convert(tree)
    loopir.append(loopir, IRNode(kind='storeresult', value=result, maxstencil=0))

    def updatemaxstencil(tree, expand):
        if tree.kind == 'loadtemp':
            print(tree.temp.maxstencil, exppand)
            tree.temp.maxstencil = max(tree.temp.maxstecil, expand)
        elif tree.kind == 'operator':
            updatemaxstencil(tree.lhs, expand)
            updatemaxstencil(tree.rhs, expand)
        elif tree.kind == 'shift':
            s = max(abs(tree.sx), abs(tree.sy))
            updatemaxstencil(tree.value, expand + s)

    for i in range(len(loopir) - 1, -1, -1): # loop to 0? TODO
        loop = loopir[i]
        updatemaxstencil(loop.value, loop.maxstencil)
    return loopir

def compile_ir_image_wide(tree):
    loopir = createloopir("image_wide", tree)

    W, H, inputs = q[name[W]], q[name[H]], q[name[inputs]]
    output = q[name[output]]

    statements = []
    cleanup = []
    temptoptr = {}
    def gen_tree(tree,x,y):
        if tree.kind == "const":
            return q[float(tree.value)]
        elif tree.kind == "input":
            return q[load_data(W,H,inputs[u[tree.index]],x,y)]
        elif tree.kind == "operator":
            lhs = gen_tree(tree.lhs,x,y)
            rhs = gen_tree(tree.rhs,x,y)
            return tree.op(lhs,rhs)
        elif tree.kind == "shift":
            xn, yn = q[x + u[tree.sx]], q[y + u[tree.sy]]
            return gen_tree(tree.value,xn,yn)
        elif tree.kind == "loadtemp":
            assert temptoptr[tree.temp], "no temporary?"
            ptr = temptoptr[tree.temp]
            return q[load_data(W,H,ptr,x,y)]
        else:
            raise Exception("unknown kind")

    for i, loop in enumerate(loopir):
        data = q[name[data]]
        if loop.kind == "storetemp":
            ptr = q[malloc(W * H * 8)]
            with q as cleanup_stmt:
                _ = free(data)
            cleanup.append(cleanup_stmt)
            temptoptr[loop] = data
        elif loop.kind == "storeresult":
            ptr = output
        with q as loopcode:
            data = ptr
            for y in range(H):
                for x in range(W):
                    data[y*W+x] = u[gen_tree(loop.value,x,y)]
        statements.append(loopcode)

    @scale.anonymous
    def body(W: int, H: int, output: [float], inputs: [[float]]) -> int:
        {statements}
        {cleanup}
        return 0
    return body

def compile_ir_blocked(tree):
    BLOCK_SIZE = 128
    loopir = createloopir("blocked", tree)

    W, H, inputs = q[name[W]], q[name[H]], q[name[inputs]]
    output = q[name[output]]
    beginx, beginy = q[name[beginx]], q[name[beginy]]
    statements = []
    temptoptr = {}
    def gen_tree(tree, x, y):
        if tree.kind == 'const':
            return q[float(u[tree.value])]
        elif tree.kind == 'input':
            return q[load_data(W, H, inputs[u[tree.index]], beginx + x, beginy + y)]
        elif tree.kind == 'operator':
            lhs = gen_tree(tree.lhs, x, y)
            rhs = gen_tree(tree.rhs, x, y)
            return tree.op(lhs, rhs)
        elif tree.kind == 'shift':
            xn, yn = q[x + u[tree.sx]], q[y + u[tree.sy]]
            return gen_tree(tree.value, xn, yn)
        elif tree.kind == 'loadtemp':
            maxstencil = tree.temp.maxstencil
            assert temptoptr[tree.temp], "no temporary?"
            ptr = temptoptr[tree.temp]
            stride = BLOCK_SIZE + 2 * maxstencil
            start = maxstencil + stride * maxstencil
            return q[ptr[start + stride * y + x]]
        else:
            raise Exception("unknown kind")

    for i, loop in enumerate(loopir):
        if loop.kind == "storetemp":
            stride = 2*loop.maxstencil + BLOCK_SIZE
            data = q[name[data]] # needs to be unique TODO
            temptoptr[loop] = data
            loopbegin, loopend = -loop.maxstencil, BLOCK_SIZE + loop.maxstencil
            start = loop.maxstencil + stride*loop.maxstencil
            assert start + loopbegin * stride + loopbegin == 0
            assert start + (loopend-1) * stride + loopend - 1 == stride*stride - 1
            with q as loopcode:
                for y in range(loopbegin, loopend + 1):
                    for x in range(loopbegin, loopend + 1):
                        data[start+y*stride+x] = u[gen_tree(loop.value,x,y)]
        elif loop.kind == "storeresult":
            with q as loopcode:
                start = output + beginy*W + beginx
                for y in range(min(H - beginy,BLOCK_SIZE) + 1):
                    for x in range(min(W - beginx,BLOCK_SIZE) + 1):
                        start[y*W + x] = u[gen_tree(loop.value,x,y)]
        statements.append(loopcode)

    @scale.anonymous
    def body(W: int, H: int, output: [float], inputs: [[float]]):
        for beginy in range(0, {H}, {BLOCK_SIZE}):
            for beginx in range(0, {W}, {BLOCK_SIZE}):
                {statements}
    return body

