import ctypes

import numpy
from llvmlite import ir as llvm

from .typechecker import TypeChecker


class MarshalledArg(object):
    def __init__(self, py_arg, llvm_ty):
        self.py_arg = py_arg
        self.llvm_ty = llvm_ty

        self.copy_back = False
        self.ctype = MarshalledArg.to_ctype(llvm_ty)
        self._as_parameter_ = self.wrap_value(py_arg)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.copy_back:
            if isinstance(self.py_arg, list):
                for i in range(len(self.py_arg)):
                    self.py_arg[i] = self._as_parameter_[i]

    @staticmethod
    def to_ctype(ir_type, in_ptr=False):
        if isinstance(ir_type, llvm.IntType):
            if ir_type.width == 32:
                return ctypes.c_int32
            if ir_type.width == 1:
                return ctypes.c_char
        if isinstance(ir_type, llvm.DoubleType):
            return ctypes.c_double
        if isinstance(ir_type, llvm.PointerType) and not in_ptr:
            return ctypes.POINTER(MarshalledArg.to_ctype(ir_type.pointee, in_ptr=True))
        raise NotImplementedError('No ctype available for {}'.format(ir_type))

    def wrap_value(self, arg):
        if self.llvm_ty == TypeChecker.int_type and isinstance(arg, int):
            return arg
        if self.llvm_ty == TypeChecker.bool_type and isinstance(arg, bool):
            return arg
        if self.llvm_ty == TypeChecker.float_type and isinstance(arg, float):
            return arg
        if isinstance(self.llvm_ty, llvm.PointerType):
            el_ty = self.to_ctype(self.llvm_ty.pointee)
            self.copy_back = True
            if isinstance(arg, list):
                return ctypes.cast((el_ty * len(arg))(*arg), self.ctype)
            elif isinstance(arg, numpy.ndarray):
                if el_ty == ctypes.c_double and arg.dtype != numpy.double:
                    raise ValueError('expected double ndarray, got {}'.format(arg.dtype))
                elif el_ty == ctypes.c_int32 and arg.dtype != numpy.int32:
                    raise ValueError('expected int32 ndarray, got {}'.format(arg.dtype))
                elif el_ty == ctypes.c_bool:
                    raise NotImplementedError('arrays of bools')
                return arg.ctypes.data_as(self.ctype)
            else:
                raise NotImplementedError('Passing {} to c arrays'.format(type(arg)))
        raise NotImplementedError('Not sure how to handle arguments of type {}'.format(type(arg)))

