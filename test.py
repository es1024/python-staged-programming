from scale import scale
from scale.quote import macros, q
import numpy as np

arr = np.arange(9).reshape((3,3)).tolist()

@scale
def double_i(a: [[int]]) -> int:
    return a[1,1]
print(double_i([[0,1,2],[3,4,5]]))

@scale
def sum_for(a: [[int]], l: int) -> int:
    s = 0
    for i in range(l):
        for j in range(l):
            s += a[i,j]
    return s
print(sum_for(arr, len(arr)))

@scale
def laplace(img: [[int]], out: [[int]], l: int) -> int:
    for i in range(l-2):
        for j in range(l-2):
            out[i,j] = img[i+0,j+1] + img[i+2,j+1] + img[i+1,j+2] + img[i+1,j+0] - 4 * img[i+1,j+1]
    return out[14,14]
img = np.random.randint(0, 100,(28,28))
print(laplace(img.tolist(), np.random.randint(0,1,(26, 26)).tolist(), 28))
test_index = 14
print(img[test_index+0,test_index+1] + img[test_index+2,test_index+1] + img[test_index+1,test_index+2] + img[test_index+1,test_index+0] - 4 * img[test_index+1,test_index+1])
'''
def gen_square(x):
    return q[x * x]

a = 1
with q as block_of_code:
    a = a + 2
    b = a + 3

@scale
def n1(x: int) -> int:
    return x

@scale
def n2(x: int) -> int:
    d = n1(x)
    c = 1
    return x
n2.compile()

@scale
def array_of_array(a: [[int]]) -> int:
    b = a[2]
    return b[2]
@scale
def create_len_array(n: int) -> float:
    a =  create_float_array(5)
    a[4] = 5.5
    return a[4]

@scale
def ret5() -> int:
    return 5

@scale
def call_test() -> int:
    five = ret5()
    return five

@scale
def index_test(a: [int]) -> int:
    a[1] = 1
    return a[1]
@scale
def array1_test(a: [int]) -> int:
    b = [1,2,3]
    c = b[1] + b[2]
    d = b[1] + c
    b[2] = d + a[0]
    return d

@scale
def array2_test(a: [int]) -> [int]:
    return a

@scale
def mse(a: float, b: float) -> float:
    return {gen_square(a)} - {gen_square(b)}

@scale(dump_unescaped=True, dump_llvm=True)
def test_block_quotes(a: int) -> int:
    {block_of_code}
    return b

@scale(dump_unescaped=True)
def test_block_quotes_captured() -> int:
    {block_of_code}
    return b

def python_mse(a: float, b: float) -> float:
    return a * a + b * b


print(mse(4.0, 3.0))
print(test_block_quotes_captured())
print(test_block_quotes(2))
a = 3
print(test_block_quotes_captured())
print(test_block_quotes(2))
print(index_test([1,2,3]))
print(array1_test([5,5,5]))
print(create_len_array(1))
print(array_of_array([[1,2,3,4],[5,6,7,8],[4,7,8]]))
print(call_test())


@scale.declare
def factorial1(n: int) -> int:
    pass

@scale.declare
def factorial2(n: int) -> int:
    pass

@scale(dump_unescaped=True, dump_llvm=True)
def factorial1(n: int) -> int:
    if n == 1:
        return 1
    return n * factorial2(n - 1)

@scale(dump_unescaped=True, dump_llvm=True)
def factorial2(n: int) -> int:
    if n == 1:
        return 1
    return n * factorial2(n - 1)
print([factorial1(i) for i in range(1, 10)])
'''
