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
To differentiate from Python functions, we use the @scale decorator to denote Scale functions. Unlike Python, arguments and return types must be explicitly specified, which allows typesafe runtime code generation through LLVM. Scale supports integers, floats, booleans as basic types, and multidimensional arrays as the primary data structure. Scale's control flow consists of if statements, for loops, and gotos, behaving identically to that of Python.
        

    def gen_square(x):
        return q[x * x]

    @scale
    def mse(a: int, b: int) -> int:
        return {gen_square(a)} - {gen_square(b)}

Results and Evaluation
================

Conclusion
================
