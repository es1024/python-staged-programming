from foo import foo
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
def compile(code, N):
    def body(data, ptr):
        stmts = [] # ???
        for i in range(len(code)):
            c = code[i]
            if c == '>':
                with q as stmt: ptr = ptr + 1
            elif c == '<':
                with q as stmt: ptr = ptr - 1
            elif c == '+':
                with q as stmt: data[ptr] = data[ptr] + 1
            elif c == '-':
                with q as stmt: data[ptr] = data[ptr] - 1
            elif c == '.':
                raise NotImplementedError
            elif c == ',':
                raise NotImplementedError
            elif c == '[':
                raise NotImplementedError
            elif c == ']':
                raise NotImplementedError
            stmts.append(stmt)
        return stmts

    data = [0] * N

    @foo(dump_llvm=True)
    def inner(data: [int]) -> int:
        for i in range(N):
            data[i] = 0
        ptr = 0
        { body(data, ptr) }
        return data[ptr]

    return lambda: inner(data)

z = compile('+', 2)
print(z())

