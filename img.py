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
