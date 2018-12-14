Scale: Staged Programming in Python
==========================
_Alex Fang and Eric Sheng_

Introduction
================

Scale Language
================
Scale is a low-level statically-typed language embedded in Python 3, designed to help users with

    @scale
    def laplace(img: [[int]], out: [[int]], l: int) -> int:
        for i in range(l - 2):
            for j in range(l - 2):
                out[i,j] = img[i + 0,j + 1] + img[i + 2,j + 1] + \
                           img[i + 1,j + 2] + \
                           img[i + 1,j + 0] - 4 * img[i + 1,j + 1]
        return 0
        
To differentiate from Python functions, we use the `@scale` decorator to denote Scale functions. Unlike Python, arguments and return types must be explicitly specified, which allows typesafe runtime code generation through LLVM. Scale supports integers, floats, booleans as basic types, and multidimensional arrays as the primary data structure. Scale's control flow consists of if statements, for loops, and gotos, behaving identically to that of Python. Scale supports function calls to 

Scale uses the Python Abstract Syntax Tree (AST) as an intermediate representation
        

    def gen_square(x):
        return q[x * x]

    @scale
    def mse(a: int, b: int) -> int:
        return {gen_square(a)} - {gen_square(b)}
        
Scale is meta-programmed with Python through select multi-stage programming operators. Escapes allow the use of Python code within Scale functions. Escapes in Scale are represented by curly brackets `{}`, whose contents are evaluated in Python at compile time and has its return value injected into the AST.
Quotes allow for Scale expressions outside of Scale functions. In Scale, quotes are denoted with `q[]`. In the above example, the Scale function calls the Python function within the escape, and the quotes within the Python function allow it to manipulate `x`, which is a variable in Scale.

Results and Evaluation
================

Conclusion
================
