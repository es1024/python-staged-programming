from scale import scale
from scale.quote import macros, q
import numpy as np
import ast
import operator
import re

def alloc_image_data(w,h): # TODO:
    data = C.malloc(4*w*h)
    return terralib.cast(&float,data)

def loadpbm(filename):
    F = open(filename, "r")
    cur = F.read(1)
    def isspace(cur):
        return cur and (re.search(r'[\s]', cur) or cur == "#")

    def parseWhitespace(cur, F):
        assert(isspace(cur) is True, "expected at least one whitespace character")
        while isspace(cur):
            if cur == "#":
                while cur != "\n":
                    cur = F.read(1)
            cur = F.read(1)
        return cur

    def parseInteger(cur, F):
        assert(cur.isdigit(), "expected a number")
        n = ""
        while cur.isdigit():
            n += cur
            cur = F.read(1)
        assert(int(n), "not a number?")
        return int(n)
    assert(cur == "P", "wrong magic number")
    cur = F.read(1)
    assert(cur == "6", "wrong magic number")
    cur = F.read(1)

    # TODO: Update once image object a thing
    local image = {}
    cur = parseWhitespace(cur, F)
    image.width = parseInteger(cur, F)
    cur = parseWhitespace(cur, F)
    image.height = parseInteger(cur, F)
    cur = parseWhitespace(cur, F)
    local precision = parseInteger(cur, F)
    assert(precision == 255, "only supports 255 as max value")
    assert(isspace(cur), "expected whitespace after precision")
    local data_as_string = F:read(image.width*image.height*3)
    -- read the data as flat data
    local data = alloc_image_data(image.width,image.height)
    for i  in range(image.width*image.height - 1):
        local r,g,b = data_as_string:byte(3*i+1,3*i+3)
        data[i] = math.min(255,(r+g+b)/3.0)
        local x,y = i % 16, math.floor(i / 16)
    image.data = data
    cur = F.read(1)
    assert(cur == nil, "expected EOF")
    return image


local headerpattern = [[
P6
%d %d
%d
]]

def savepbm(image,filename):
    local F = assert(io.open(filename,"wb"), "file could not be opened for writing")
    F:write(string.format(headerpattern, image.width, image.height, 255))
    local function writeNumber(v)
        assert(type(v) == "number","NaN?")
        F:write(string.char(v))
    end
    local floor,max,min,char,data,fwrite = math.floor,math.max,math.min,string.char,image.data,F.write
    for i = 0, image.width*image.height - 1 do
        local v = data[i]
        v = floor(v)
        v = max(0,min(v,255))
        v = char(v)
        fwrite(F,v..v..v)
    end
    F:close()
end

local function newclass(name)
    local cls = {}
    cls.__index = cls
    function cls.new(tbl)
        return setmetatable(tbl,cls)
    end
    function cls.isinstance(x)
        return getmetatable(x) == cls
    end
    function cls:__tostring()
        return "<"..name..">"
    end
    return cls
end

-- represents actual image data
local concreteimage = newclass("concreteimage")
function concreteimage.load(filename)
    return concreteimage.new(loadpbm(filename))
end
function concreteimage:save(filename)
    savepbm(self,filename)
end


-- represents an abstract computation that creates an image
local image  = newclass("image")
function image.constant(const)
    local result = image.new {}
    result.tree = error("NYI - your IR goes here")
    return result
end
function image.input(index)
    local result = image.new {}
    result.tree = error("NYI - your IR goes here")
    return result
end

-- Support constant numbers as images
local function toimage(x)
  if image.isinstance(x) then
    return x
  elseif type(x) == "number" then
    return image.constant(x)
  end
  return nil
end

local function pointwise(self,rhs,op)
    self,rhs = assert(toimage(self),"not an image"),assert(toimage(rhs),"not an image")
    local result = image.new {}
    result.tree = error("NYI - your IR goes here")
    return result
end

function image:__add(rhs)
    return pointwise(self,rhs,function(x,y) return `x + y end)
end
function image:__sub(rhs)
    return pointwise(self,rhs,function(x,y) return `x - y end)
end
function image:__mul(rhs)
    return pointwise(self,rhs,function(x,y) return `x * y end)
end
function image:__div(rhs)
    return pointwise(self,rhs,function(x,y) return `x / y end)
end
-- generate an image that translates the pixels in the new image
function image:shift(sx,sy)
    local result = image.new {}
    result.tree = error("NYI - your IR goes here")
    return result
end

local terra load_data(W : int, H : int, data : &float, x : int, y : int) : float
    while x < 0 do
        x = x + W
    end
    while x >= W do
        x = x - W
    end
    while y < 0 do
        y = y + H
    end
    while y >= H do
        y = y - H
    end
    return data[(y*W + x)]
end
local terra min(x : int, y : int)
    return terralib.select(x < y,x,y)
end

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
