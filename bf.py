from scale import *
from scale.quote import macros, q

@scale.native
def putchar(n: int) -> int: pass

@scale.native
def getchar() -> int: pass

def compile(code, N):
    def body(data, ptr):
        stmts = []
        jump_i = 0
        jumpstack = []
        for i in range(len(code)):
            c = code[i]
            if c == '>':
                with q as stmt: ptr = (ptr + 1) % N
            elif c == '<':
                with q as stmt: ptr = (ptr + N - 1) % N
            elif c == '+':
                with q as stmt: data[ptr] = (data[ptr] + 1) % 256
            elif c == '-':
                with q as stmt: data[ptr] = (data[ptr] + 255) % 256
            elif c == '.':
                with q as stmt: _ = putchar(data[ptr])
            elif c == ',':
                with q as stmt: data[ptr] = getchar() % 256
            elif c == '[':
                target = ('before_' + str(jump_i), 'after_' + str(jump_i))
                jumpstack.append(target)
                jump_i += 1
                with q as stmt:
                    label ^(u[target[0]])
                    if data[ptr] == 0:
                        goto ^(u[target[1]])
            elif c == ']':
                target = jumpstack.pop()
                with q as stmt:
                    goto ^(u[target[0]])
                    label ^(u[target[1]])
            else:
                continue
            stmts.append(stmt)
        return stmts

    @scale.anonymous
    def inner() -> int:
        data = create_int_array(N)
        for i in range(N):
            data[i] = 0
        ptr = 0
        { body(data, ptr) }
        return data[ptr]

    return inner

hello_world = compile('++++++++++[>+++++++>++++++++++>+++>+<<<<-]>++.>+.+++++++..+++.>++.<<+++++++++++++++.>.+++.------.--------.>+.>.', 256)
hello_world()
# cat = compile(',+[-.,+]', 1)
# cat()

