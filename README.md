Scale: Staged Programming in Python
==========================
_Alex Fang and Eric Sheng_

Introduction
---------------
In order to improve performance, a common approach is to use multiple languages to target the specific tasks involved. This can typically be split into a higher level language to describe behavior and implement tasks not reliant on speed, and a lower level language to produce high performance code. This general idea allows user to choose the level of abstraction per task, which leads to the idea of multi-stage programming. In multi-stage programming, code compilation happens in multiple stages, which allows it to take advantage of information available from the function definition for optimization in performance. By using information gained, such as argument types and return types, the code is then compiled into code generated specifically for that version of the function defined.

Multi-stage programming allows for the development of compiled implementations of DSLs without requiring the time and expertise normally required for writing a compiler. This is because the higher level language's operators can be overloaded for the operators and expressions wanted in the new DSL, which will then have an appropriate intermediate representation that can be generate code in a lower level language that can be compiled to generate efficient code. This is convenient as it allows users to use the higher level language to experiment and describe their program while having the performance close to the lower level language. Previous work done in this area includes Terra, which is embedded and metaprogrammed in Lua. With Terra, DSLs can be written in Lua and then compiled into high performance Terra code.

In order to to target the ideas of multi-stage programming and Python, we introduce Scale. Given the recent popularity of Python due to its capabilities in many subfields of computer science and its general accessibility, we believe it would be beneficial to have more tools for building DSLs in Python.  Within Python there are libraries like MacroPy, which we rely on in Scale, which implements syntactic macros to transform the Python abstract syntax tree (AST). In the following sections, we will describe the Scale language and show examples of how it can be used.

Scale Language
---------------
Scale is a low-level statically-typed language embedded in Python 3, designed to help users with staged programming and writing DSLs in Python.

```python
@scale.declare
def laplace(img: [[int]], out: [[int]], l: int) -> int: pass

@scale
def laplace(img: [[int]], out: [[int]], l: int) -> int:
    for i in range(l - 2):
        for j in range(l - 2):
            out[i,j] = img[i + 0,j + 1] + img[i + 2,j + 1] + \
                       img[i + 1,j + 2] + \
                       img[i + 1,j + 0] - 4 * img[i + 1,j + 1]
    return 0

@scale.native
def putchar(n: int) -> int: pass
```
        
To differentiate Scale functions from Python functions, we use the `@scale` decorator to denote Scale functions. Unlike Python, arguments and return types must be explicitly specified, which allows typesafe runtime code generation through LLVM. Scale supports integers, floats, booleans as basic types, and multidimensional arrays as its primary data structure. Scale's control flow consists of if statements, for loops, behaving similarly to that of Python. Scale supports both function calls to other Scale methods, and calls to functions in libc (after declaring the function with `@scale.native`). Scale also supports function declarations for Scale functions that are defined later, via the `@scale.declare` decorator.

Scale also supports the `goto` construct, which, while often not considered best practice for writing code, is frequently useful for generating code:
```
a = 'labelA'

@scale
def test(x: int) -> int:
    label ^{a}
    x = getchar()
    if x != 89: # 'Y'
        goto ^'labelA'
    return x
```
Labels are strings, allowing for use of escapes (see below) to generate the label.

Scale uses the Python AST as an intermediate representation.
        
```python
def gen_square(x):
    return q[x * x]

@scale
def mse(a: int, b: int) -> int:
    return {gen_square(a)} - {gen_square(b)}
```

Scale is meta-programmed with Python through select multi-stage programming operators. Escapes allow the use of Python code within Scale functions. Escapes in Scale are represented by curly brackets `{}`, whose contents are evaluated in Python at compile time and has its return value injected into the AST.
Quasiquotes allow for Scale expressions outside of Scale functions, and are denoted with `q[]`. They return the AST of the expression within it, generating it using the captured value of Scale variables if present. In the above example, the Scale function calls the Python function within the escape, and the quasiquotes within the Python function allow it to manipulate `x`, which is a variable in Scale.
Scale also supports block quotes using the syntax `with q as stmt:`. Although escapes are not supported within these blocks, the same effect can be achieved through unquotes, `u[]`, which takes the value within the brackets and injects it into the AST assigned to `stmt`.

Scale also supports passing around Scale variables as values in Python: a Scale variable `x` can be passed around Python via the object returned by `scale.var('x')`, and a new unnamed Scale variable can be created in Python via `scale.newvar()`. For example:

```python
stmts = []
for i in range(10):
    x = scale.newvar()
    with q as stmt:
        x = 1
    stmts.append(stmt)

@scale
def f() -> int:
    {stmts}
    # do something ...
    return ...
```

will create and assign to 10 fresh variables the integer value 1.

One can also view the generated code of a Scale function from Python:

```python
@scale
def scale_function(...) -> int:
    # do something
    return ...

scale_function.compile()
print(scale_function.pretty()) # prints the scale function's source, but with all escapes processed
print(scale_function.opcode()) # prints the generated and optimized LLVM instructions
```

Scale evaluates escapes at function definition time, but defers compilation to either first use of the function, or to the first call of `function.compile()`, allowing unused functions to never be compiled, while still maintaining an intuitive idea of what value is captured by escapes:

```python
a = 0
def f() -> int:
    return a
a = 1
print(f()) # prints 0
```

Finally, Scale supports anonymous functions:

```python
@scale.anonymous
def foo() -> int:
    ...
``

Here, `foo` contains a wrapper to an anonymous Scale function. It can be called from Python, but cannot be called from Scale with its name. This functionality is useful for Python functions that generate Scale functions to be used from Python, as it avoids name conflicts in the generated LLVM code.

Results and Evaluation
---------------
#### Brainfuck Example
In this section, we describe a simple compiler for the turing-complete language [brainfuck](https://esolangs.org/wiki/brainfuck), written in Python and compiled to LLVM with Scale (see bf.py for the full source), in a manner similar to the [brainfuck compiler example for Terra](http://terralang.org/#compiling-a-language).

We place all of the logic for the compiler in the `compile` method:

```python
def compile(code, N):
    def body(data, ptr):
        """ to be implemented below """

    @scale.anonymous
    def inner() -> int:
        data = create_int_array(N)
        for i in range(N):
            data[i] = 0
        ptr = 0
        { body(data, ptr) }
        return data[ptr]

    return inner
```

The `body` method will generate Scale statements, which are then stitched into the Scale AST in the `inner` method before getting compiled down to LLVM. The code in the `inner` method just creates an array of length `N` (the tape), initializes it to 0, and then uses an escape to call `body(data, ptr)` and inject the resulting Scale statements into the body. The values passed into `body` for `data` and `ptr` are the named Scale variables `data` and `ptr`, which can be used to generate statements with those variables. The `inner` method is declared as an anonymous function, as it makes no sense for other Scale functions defined later to call `inner()`.

The implementation for `body` for supporting `+`, `-`, `<`, and `>` is fairly straightforward: we just loop through the brainfuck source passed in to `compile`, and generate the corresponding Scale statement for that command:

```python
def body(data, ptr):
    stmts = []
    for i in range(len(code)):
        c = code[i]
        if c == '>':
            with q as stmt: ptr = (ptr + 1) % N
        elif c == '<':
            with q as stmt: ptr = (ptr + N - 1) % N
        elif c == '+':
            with q as stmt: data[ptr] = data[ptr] + 1
        elif c == '-':
            with q as stmt: data[ptr] = data[ptr] - 1
        else:
            continue
        stmts.append(stmt)
    return stmts
```

Here, we return a list of Scale statements (generated with quasiquote blocks), that play around with the `data` and `ptr` Scale variables that were passed in. Scale allows for escapes to evaluate to expressions, statements, or list of statements. `N` here is not a Scale variable, but rather, a Python variable. Its value is captured from the value of N at the time that `body` is called.

To implement `.` and `,` (writing/reading from standard I/O), we can call `getchar` and `putchar` from libc. We must first declare these (anywhere in scope in Python from the place where we quote, such as at the top of the file):

```python
@scale.native
def putchar(n: int) -> int: pass

@scale.native
def getchar() -> int: pass
```

These functions cannot be called directly from Python, but we can use them inside Scale functions. Adding support for `.` and `,` is then fairly straightforward:

```python
def body(data, ptr):
    ...
    for i in range(len(code)):
        c = code[i]
        elif c == '.':
            with q as stmt: _ = putchar(data[ptr])
        elif c == ',':
            with q as stmt: data[ptr] = getchar()
        ...
```

A limitation of Scale right now is that we only support statements that assign to variables (hence why we assign the return value of `putchar` to a variable `_`). This limitation does not prevent us from calling libc functions like `free` that return void, however, as we can declare such functions to return `int` and assign it to a throwaway variable (e.g. one created with `scale.newvar()`).

To implement `[` and `]` (the loop commands), we can utilize the `goto` construct in Scale:

```python
def body(data, ptr):
    stmts = []
    jump_i = 0
    jumpstack = []
    ...
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
    ...
```
Here, `stmt` is actually several statements. Scale will flatten the list of statements before injecting into the AST, so nested lists of statements are allowed (and equivalent to simple unnested lists).

We now have a working brainfuck compiler. Due to limitations with [MacroPy](https://github.com/lihaoyi/macropy), we cannot directly execute code from a file that uses macros, but we can run:

```python
import macropy.activate     # required from MacroPy
from bf import *            # import everything from bf.py

f = compile('+++++++[>+++++++<-]>-.', 2) # BF program that writes a single ASCII 0 to STDOUT
f() # prints '0'
```

from a different file.

Printing the generated LLVM code with `print(f.opcode())` indicates that the entire program has been reduced to printing and returning a constant:
```
define i32 @inner() local_unnamed_addr #0 {
.77:
  %.153 = tail call i32 @putchar(i32 48)
  ret i32 48
}
```

#### Simple Image Processing DSL Example
In this section, we describe a Simple Image Processing DSL built using Python and Scale. This DSL supports addition, subtraction, multiplication and division operations on images, using constants, reading from a list of input images, and accessing images using a offset. The IR is implemented as a Python object before being translated to the Python/Scale AST. The IR is compiled into Scale code through three different strategies: 1. looping over each pixel and computing pixel values individually; 2. ; 3. .

Conclusion
---------------
The natural next step for this project would be to extend the language to additional features, such as allowing for more complicated scoping rules, creating objects, and additional structures. In order to gauge performance of Scale, we would also measure speed of implementations in Scale against benchmarks in C and Python, along with implementing a more complicated DSL in Scale. We hope that the initially developed version of Scale is not only extended to be more practically useful for users, but also can serve as a baseline or inspiration for further work in developing DSLs and tools for developing DSLs in Python.
