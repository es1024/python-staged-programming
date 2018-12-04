from foo import foo
from foo.quote import macros, q

def gen_square(x):
    return q[x * x]

a = 1
with q as block_of_code:
    a = a + 2
    b = a + 3

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

