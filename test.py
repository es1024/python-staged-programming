from foo import foo
from foo.quote import macros, q

def gen_square(x):
    return q[x * x]

a = 1
with q as block_of_code:
    a = a + 2
    b = a + 3

@foo
def array_of_array(a: [[int]]) -> int:
    b = a[2]
    return b[2]
@foo
def create_len_array(n: int) -> float:
    a =  create_float_array(5)
    a[4] = 5.5
    return a[4]

@foo
def ret5() -> int:
    return 5

@foo
def call_test() -> int:
    five = ret5()
    return five

@foo
def index_test(a: [int]) -> int:
    a[1] = 1
    return a[1]
@foo
def array1_test(a: [int]) -> int:
    b = [1,2,3]
    c = b[1] + b[2]
    d = b[1] + c
    b[2] = d + a[0]
    return d

@foo
def array2_test(a: [int]) -> [int]:
    return a

@foo
def mse(a: float, b: float) -> float:
    return {gen_square(a)} - {gen_square(b)}

@foo(dump_unescaped=True, dump_llvm=True)
def test_block_quotes(a: int) -> int:
    {block_of_code}
    return b

@foo(dump_unescaped=True)
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


@foo.declare
def factorial1(n: int) -> int:
    pass

@foo.declare
def factorial2(n: int) -> int:
    pass

@foo(dump_unescaped=True, dump_llvm=True)
def factorial1(n: int) -> int:
    if n == 1:
        return 1
    return n * factorial2(n - 1)

@foo(dump_unescaped=True, dump_llvm=True)
def factorial2(n: int) -> int:
    if n == 1:
        return 1
    return n * factorial2(n - 1)
print([factorial1(i) for i in range(1, 10)])

