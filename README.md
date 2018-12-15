Scale: Staged Programming in Python
==========================
_Alex Fang and Eric Sheng_

Introduction
================
In order to improve performance, a common approach is to use multiple languages to target the specific tasks involved. This can typically be split into a higher level language to describe behavior and implement tasks not reliant on speed, and a lower level language to produce high performance code. This general idea allows user to choose the level of abstraction per task, which leads to the idea of multi-stage programming. In multi-stage programming, code compilation happens in multiple stages, which allows it to take advantage of information available from the function definition for optimization in performance. By using information gained, such as argument types and return types, the code is then compiled into code generated specifically for that version of the function defined.

Multi-stage programming allows for the development of compiled implementations of DSLs without requiring the time and expertise normally required for writing a compiler. This is because the higher level language's operators can be overloaded for the operators and expressions wanted in the new DSL, which will then have an appropriate intermediate representation that can be generate code in a lower level language that can be compiled to generate efficient code. This is convenient as it allows users to use the higher level language to experiment and describe their program while having the performance close to the lower level language. Previous work done in this area includes Terra, which is embedded and metaprogrammed in Lua. With Terra, DSLs can be written in Lua and then compiled into high performance Terra code.

In order to to target the ideas of multi-stage programming and Python, we introduce Scale. Given the recent popularity of Python due to its capabilities in many subfields of computer science and its general accessibility, we believe it would be beneficial to have more tools for building DSLs in Python.  Within Python there are libraries like MacroPy, which we rely on in Scale, which implements syntactic macros to transform the Python abstract syntax tree (AST). In the following sections, we will describe the Scale language and show examples of how it can be used.

Scale Language
================
Scale is a low-level statically-typed language embedded in Python 3, designed to help users with staged programming and writing DSLs in Python.

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
        
To differentiate from Python functions, we use the `@scale` decorator to denote Scale functions. Unlike Python, arguments and return types must be explicitly specified, which allows typesafe runtime code generation through LLVM. Scale supports integers, floats, booleans as basic types, and multidimensional arrays as the primary data structure. Scale's control flow consists of if statements, for loops, and gotos, behaving identically to that of Python. Scale supports both function calls to other Scale methods, and also supports C functions by decorating the function with`@scale.native`.

Scale uses the Python AST as an intermediate representation.
        

    def gen_square(x):
        return q[x * x]

    @scale
    def mse(a: int, b: int) -> int:
        return {gen_square(a)} - {gen_square(b)}
        
Scale is meta-programmed with Python through select multi-stage programming operators. Escapes allow the use of Python code within Scale functions. Escapes in Scale are represented by curly brackets `{}`, whose contents are evaluated in Python at compile time and has its return value injected into the AST.
Quasiquotes allow for Scale expressions outside of Scale functions, and are denoted with `q[]`. They return the AST of the expression within it, generating it using the captured value of Scale variables if present. In the above example, the Scale function calls the Python function within the escape, and the quasiquotes within the Python function allow it to manipulate `x`, which is a variable in Scale.

Scale also supports block quotes using the syntax `with q as stmt:`. Although escapes are not supported within these blocks, the same effect can be achieved through unquotes, `u[]`, which takes the value within the brackets and injects it into the AST assigned to `stmt`.


Results and Evaluation
================
######Brainfuck Example

######Simple Image Processing DSL Example

Conclusion
================
The natural next step for this project would be to extend the language to additional features, such as allowing for more complicated scoping rules, creating objects, and additional structures. In order to gauge performance of Scale, we would also measure speed of implementations in Scale against benchmarks in C and Python, along with implementing a more complicated DSL in Scale. We hope that the initially developed version of Scale is not only extended to be more practically useful for users, but also can serve as a baseline or inspiration for further work in developing DSLs and tools for developing DSLs in Python.
