from scale import scale
from scale.quote import macros, q
import numpy as np
import ast
import operator
import re
from PIL import Image

def alloc_image_data(w,h): # TODO:
    data = C.malloc(4*w*h)
    return terralib.cast(&float,data)

def loadpbm(filename):
    im = Image.open(filename)
    return im

def savepbm(im, filename):
    im.save(filename)

# represents a node in the IR
class IRNode:
    def __init__(self, kind, **kwargs):
        self.kind = kind
        for k, v in kwargs:
            setattr(self, k, v)

# represents actual image data
class ConcreteImage:
    def __init__(self, filename):
        F = open(filename, "rb")
        cur = None

        def _next():
            nonlocal cur, F
            cur = F.read(1)
        _next()
        def _isspace():
            return cur and cur in ('\t', '\r', '\n', ' ', '#')
        def _isdigit():
            return '0' <= cur <= '9'
        def _parseWhitespace():
            assert _isspace(), "expected at least one whitespace character"
            while _isspace():
                if cur == "#":
                    _next()
                    while cur != "\n":
                        _next()
                _next()
        def parseInteger():
            assert _isdigit(), "expected a number"
            n = ""
            while isdigit():
                n += cur
                _next()
            return int(n)
        assert(cur == "P", "wrong magic number")
        _next()
        assert(cur == "6", "wrong magic number")
        _next()

        parseWhitespace()
        self.width = parseInteger()
        parseWhitespace()
        self.height = parseInteger()
        parseWhitespace()
        precision = parseInteger()
        assert(precision == 255, "only supports 255 as max value")
        assert(isspace(), "expected whitespace after precision")
        data_as_string = F.read(width*height*3)
        # read the data as flat data
        self.data = [0] * (width * height)
        for i in range(width * height):
            r, g, b = data_as_string[3 * i + 1 : 3 * i + 3]
            data[i] = min(255, (r + g + b) / 3)
            x, y = i % 16, floor(i / 16)
        _next()
        assert cur == None, "expected EOF"

    def save(self, filename):
        pass
        savepbm(self, filename)

# represents an abstract computation that creates an image
class Image:
    def __init__(self, tree=None):
        self.tree = tree

    def constant(const):
        return Image(IRNode(kind='const', value=const))

    def input(index):
        return Image(IRNode(kind='input', index=index))

    def __toimage(x):
        if isinstance(x, Image):
            return x
        elif isinstance(x, int) or isinstance(x, float):
            return Image.constant(x)
        return None

    def __pointwise(self, rhs, op):
        rhs = __toimage(rhs)
        return Image(IRNode(kind='operator', op=op, lhs=self.tree, rhs=rhs.tree))

    def __add__(self, rhs):
        return self.__pointwise(rhs, lambda x, y: q[x + y])

    def __sub__(self, rhs):
        return self.__pointwise(rhs, lambda x, y: q[x - y])

    def __mul__(self, rhs):
        return self.__pointwise(rhs, lambda x, y: q[x * y])

    def __div__(self, rhs):
        return self.__pointwise(rhs, lambda x, y: q[x / y])

    def shift(self, sx, sy):
        return Image(IRNode(kind='shift', sx=sx, sy=sy, value=self.tree))

@scale
def load_data(W: int, H: int, data: [float], x: int, y: int) -> float:
    x = ((x % W) + W) % W
    y = ((y % H) + H) % H
    return data[y * W + x]

@scale
def min(x: int, y: int) -> int:
    if x < y:
        return x
    else:
        return y

local function compile_ir_recompute(tree)
    -- YOUR CODE HERE
    local terra body(W : int, H : int, output : &float, inputs : &&float)
        for y = 0,H do
          for x = 0,W do
            output[(y*W + x)] = [ --[[YOUR CODE HERE]] 0 ]
          end
        end
    end
    return body
end

local function compile_ir_image_wide(tree)
    -- YOUR CODE HERE
end

local function compile_ir_blocked(tree)
    -- YOUR CODE HERE
end

function image:run(method,...)
    if not self[method] then
        local compile_ir
        if "recompute" == method then
            compile_ir = compile_ir_recompute
        elseif "image_wide" == method then
            compile_ir = compile_ir_image_wide
        elseif "blocked" == method then
            compile_ir = compile_ir_blocked
        end
        assert(compile_ir,"unknown method "..tostring(method))
        self[method] = compile_ir(self.tree)
        assert(terralib.isfunction(self[method]),"compile did not return terra function")
        self[method]:compile()
        -- helpful for debug
         self[method]:printpretty(true,false)
        -- self[method]:disas()
    end
    local implementation = self[method]

    local width,height
    local imagedata = {}
    for i,im in ipairs({...}) do
        assert(concreteimage.isinstance(im),"expected a concrete image")
        width,height = width or im.width,height or im.height
        assert(width == im.width and height == im.height, "sizes of inputs do not match")
        imagedata[i] = im.data
    end
    assert(width and height, "there must be at least one input image")
    local inputs = terralib.new((&float)[#imagedata], imagedata)
    local result = concreteimage.new { width = width, height = height }
    result.data = alloc_image_data(width,height)
    implementation(width,height,result.data,inputs)
    return result
end

return { image = image, concreteimage = concreteimage, toimage = toimage }

def alloc_image_data(w,h)
    local data = C.malloc(4*w*h)
    return terralib.cast(&float,data)

@scale
def load_data(W : int, H : int, data : [float], x : int, y : int) -> float:
    x = ((x % W) + W) % W
    y = ((y % H) + H) % H
    return data[y, x]

@scale
def min(x : int, y : int)
    if x < y:
        return x
    return y

def compile_ir_recompute(tree):
    def gen_tree(tree,x,y):
        if isinstance(tree, ast.Num):
            return q[float(tree.n)]
        elif isinstance(tree, ast.List):
            return q[load_data(W,H,inputs[tree.index],x,y)]
        elif isinstance(tree, ast.BinOp):
            tr_op = {
                Bop.And: operator.and_,
                Bop.Or: operator.or_,
                Bop.Mod: operator.mod,
                Bop.Div: operator.truediv,
                Bop.Mul: operator.mul,
                Bop.Add: operator.add,
                Bop.Sub: operator.sub
            }
            lhs = gen_tree(tree.left,x,y)
            rhs = gen_tree(tree.right,x,y)
            return tr_op[node.op](lhs, rhs)
        elif tree.kind == "shift":
            xn, yn = q[x + tree.sx],q[y + tree.sy]
            return gen_tree(tree.value,xn,yn)

    @scale
    def body(W: int, H: int, output: [float], inputs[[float]]) -> int:
        for y in range(H):
          for x in range(W):
            output[(y*W + x)] = {gen_tree(tree,x,y)}
        return 0

    return body
