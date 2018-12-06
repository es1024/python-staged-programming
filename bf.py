from foo import *
from foo.quote import macros, q
"""
ilocal stmts = terralib.newlist()

    --loop over each character in the BF code
    for i = 1,#code do
        local c = code:sub(i,i)
        local stmt
        --generate the corresponding Terra statement
        --for each BF operator
        if c == ">" then
            stmt = quote ptr = ptr + 1 end
        elseif c == "<" then
            stmt = quote ptr = ptr - 1 end
        elseif c == "+" then
            stmt = quote data[ptr] = data[ptr] + 1 end
        elseif c == "-" then
            stmt = quote data[ptr] = data[ptr] - 1 end
        elseif c == "." then
            stmt = quote C.putchar(data[ptr]) end
        elseif c == "," then
            stmt = quote data[ptr] = C.getchar() end
        elseif c == "[" then
            error("Implemented below")
        elseif c == "]" then
            error("Implemented below")
        else
            error("unknown character "..c)
        end
        stmts:insert(stmt)
    end
"""

@foo.native
def putchar(n: int) -> int: pass

@foo.native
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

    @foo.anonymous
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

