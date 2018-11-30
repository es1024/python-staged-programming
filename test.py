from macropy.core.hquotes import macros, hq
from foo import foo

def gen_square(x):
    return hq[x * x]

a = 1
with hq as block_of_code:
    a = a + 2
    b = a + 3

@foo
def mse(a: float, b: float) -> float:
    return {gen_square(a)} - {gen_square(b)}

@foo(dump_unescaped=True)
def test_block_quotes() -> int:
    {block_of_code}
    return b

def python_mse(a: float, b: float) -> float:
    return a * a + b * b

print(mse(4.0, 3.0))
print(test_block_quotes())
a = 3
print(test_block_quotes())

