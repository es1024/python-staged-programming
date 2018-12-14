from scale import scale
from scale.quote import macros, q
import numpy as np
import ast
import operator
import re
from PIL import Image

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

def compile_ir_recompute(tree):
    W,H,inputs = symbol(int,"W"),symbol(int,"H"),symbol(&&float,"inputs")

    local function gen_tree(tree,x,y)
        if tree.kind == "const" then
            return `float(tree.value)
        elseif tree.kind == "input" then
            return `load_data(W,H,inputs[tree.index],x,y)
        elseif tree.kind == "operator" then
            local lhs = gen_tree(tree.lhs,x,y)
            local rhs = gen_tree(tree.rhs,x,y)
            return tree.op(lhs,rhs)
        elseif tree.kind == "shift" then
            local xn,yn = `x + tree.sx,`y + tree.sy
            return gen_tree(tree.value,xn,yn)
        end
    end
    local terra body([W], [H], output : &float, [inputs] )
        for y = 0,H do
          for x = 0,W do
            output[(y*W + x)] = [ gen_tree(tree,x,y) ]
          end
        end
    end
    return body
end

local function createloopir(method,tree)
    local num_uses = {}
    local function countuse(tree)
        if num_uses[tree] then
            num_uses[tree] = num_uses[tree] + 1
        else
            num_uses[tree] = 1
            if tree.kind == "shift" then
                countuse(tree.value)
                countuse(tree.value) -- force all shifts to be treated as things that are reified
            elseif tree.kind == "operator" then
                countuse(tree.lhs)
                countuse(tree.rhs)
            end
        end
    end
    countuse(tree)

    local loopir = {}
    local treemap = {}
    local function convert(tree)
        if tree.kind == "const" then
            return tree
        elseif method == "image_wide" and tree.kind == "input" then
            return tree
        end
        if treemap[tree] then return treemap[tree] end
        local ntree
        if tree.kind == "operator" then
            local lhs,rhs = convert(tree.lhs),convert(tree.rhs)
            ntree = { kind = "operator", op = tree.op, lhs = lhs, rhs = rhs }
        elseif tree.kind == "shift" then
            local value = convert(tree.value)
            ntree = { kind = "shift", sx = tree.sx, sy = tree.sy, value = value }
        elseif tree.kind == "input" then
            ntree = tree
        else error("unknown kind") end

        if num_uses[tree] > 1 then
            local store = { kind = "storetemp", value = ntree, maxstencil = 0 }
            table.insert(loopir,store)
            ntree = { kind = "loadtemp", temp = store }
        end
        treemap[tree] = ntree
        return ntree
    end
    local result = convert(tree)
    table.insert(loopir, { kind = "storeresult", value = result, maxstencil = 0 })


    local function updatemaxstencil(tree,expand)
        if tree.kind == "loadtemp" then
            print(tree.temp.maxstencil,expand)
            tree.temp.maxstencil = math.max(tree.temp.maxstencil,expand)
        elseif tree.kind == "operator" then
            updatemaxstencil(tree.lhs,expand)
            updatemaxstencil(tree.rhs,expand)
        elseif tree.kind == "shift" then
            local s = math.max(math.abs(tree.sx),math.abs(tree.sy))
            updatemaxstencil(tree.value,expand + s)
        end
    end
    for i = #loopir,1,-1 do
        local loop = loopir[i]
        updatemaxstencil(loop.value,loop.maxstencil)
    end
    return loopir
end

local function compile_ir_image_wide(tree)
    local loopir = createloopir("image_wide",tree)

    local W,H,inputs = symbol(int,"W"),symbol(int,"H"),symbol(&&float,"inputs")
    local output = symbol(&float,"output")

    local statements = {}
    local cleanup = {}
    local temptoptr = {}
    local function gen_tree(tree,x,y)
        if tree.kind == "const" then
            return `float(tree.value)
        elseif tree.kind == "input" then
            return `load_data(W,H,inputs[tree.index],x,y)
        elseif tree.kind == "operator" then
            local lhs = gen_tree(tree.lhs,x,y)
            local rhs = gen_tree(tree.rhs,x,y)
            return tree.op(lhs,rhs)
        elseif tree.kind == "shift" then
            local xn,yn = `x + tree.sx,`y + tree.sy
            return gen_tree(tree.value,xn,yn)
        elseif tree.kind == "loadtemp" then
            local ptr = assert(temptoptr[tree.temp],"no temporary?")
            return `load_data(W,H,ptr,x,y)
        else error("unknown kind") end
    end
    for i,loop in ipairs(loopir) do
        local data = symbol(&float,"data")
        local ptr
        if loop.kind == "storetemp" then
            ptr = `[&float](C.malloc(W*H*sizeof(float)))
            table.insert(cleanup,quote
                C.free(data)
            end)
            temptoptr[loop] = data
        elseif loop.kind == "storeresult" then
            ptr = output
        end
        local loopcode = quote
            var [data] = ptr
            for y = 0,H do
                for x = 0,W do
                    data[y*W+x] = [gen_tree(loop.value,x,y)]
                end
            end
        end
        table.insert(statements,loopcode)
    end
    local terra body([W], [H], [output], [inputs] )
        [statements]
        [cleanup]
    end
    return body
end

local function compile_ir_blocked(tree)
    local BLOCK_SIZE = 128
    local loopir = createloopir("blocked",tree)

    local W,H,inputs = symbol(int,"W"),symbol(int,"H"),symbol(&&float,"inputs")
    local output = symbol(&float,"output")
    local beginy,beginx = symbol(int,"beginy"),symbol(int,"beginx")
    local statements = {}
    local temptoptr = {}
    local function gen_tree(tree,x,y)
        if tree.kind == "const" then
            return `float(tree.value)
        elseif tree.kind == "input" then
            return `load_data(W,H,inputs[tree.index],beginx + x,beginy + y)
        elseif tree.kind == "operator" then
            local lhs = gen_tree(tree.lhs,x,y)
            local rhs = gen_tree(tree.rhs,x,y)
            return tree.op(lhs,rhs)
        elseif tree.kind == "shift" then
            local xn,yn = `x + tree.sx,`y + tree.sy
            return gen_tree(tree.value,xn,yn)
        elseif tree.kind == "loadtemp" then
            local maxstencil = tree.temp.maxstencil
            local ptr = assert(temptoptr[tree.temp],"no temporary?")
            local stride = BLOCK_SIZE+2*maxstencil
            local start = maxstencil + stride*maxstencil
            return `ptr[start + stride*y + x]
        else error("unknown kind") end
    end
    for i,loop in ipairs(loopir) do
        local loopcode
        if loop.kind == "storetemp" then
            local stride = 2*loop.maxstencil + BLOCK_SIZE
            local data = symbol(float[stride*stride],"data")
            temptoptr[loop] = data
            local loopbegin,loopend = -loop.maxstencil,BLOCK_SIZE + loop.maxstencil
            local start = loop.maxstencil + stride*loop.maxstencil
            assert(start + loopbegin * stride + loopbegin == 0)
            assert(start + (loopend-1) * stride + loopend - 1 == stride*stride - 1)
            loopcode = quote
                var [data]
                for y = loopbegin,loopend do
                    for x = loopbegin,loopend do
                        data[start+y*stride+x] = [gen_tree(loop.value,x,y)]
                        --C.printf("temp %d,%d = %f\n",beginx + x, beginy + y,data[start+y*stride+x])
                    end
                end
                --C.printf("--------------------\n")
            end
        elseif loop.kind == "storeresult" then
            loopcode = quote
                var start = output + beginy*W + beginx
                for y = 0,min(H - beginy,BLOCK_SIZE) do
                    for x = 0,min(W - beginx,BLOCK_SIZE) do
                        start[y*W + x] = [gen_tree(loop.value,x,y)]
                        --C.printf("%d,%d = %f\n",beginx + x, beginy + y,start[y*W+x])
                    end
                end
            end
        end
        table.insert(statements,loopcode)
    end
    local terra body([W], [H], [output], [inputs] )
        for [beginy] = 0,H,BLOCK_SIZE do
            for [beginx] = 0,W,BLOCK_SIZE do
                [statements]
            end
        end
    end
    return body
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
