from macropy.core.hquotes import macros, hq
from foo import foo

def gen_square(x):
    return hq[x * x]

with hq as block_of_code:
    a = 1 + 2
    b = a + 3

@foo
def mse(a: float, b: float):
    return {gen_square(a)} - {gen_square(b)}

@foo
def test_block_quotes():
    {block_of_code}
    return b

print(mse(4, 3))
print(test_block_quotes())

