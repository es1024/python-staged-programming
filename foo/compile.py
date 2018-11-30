import ast
import contextlib
import ctypes
import functools
import inspect

import llvmlite.binding as binding

from .backend import Backend
from .escape import ProcessEscape
from .frontend import Frontend
from .interpreter import Interpreter
from .marshalling import MarshalledArg
from .typechecker import TypeChecker

@functools.lru_cache()
def get_jit_engine():
    binding.initialize()
    binding.initialize_native_target()
    binding.initialize_native_asmprinter()

    target = binding.Target.from_default_triple()
    target_machine = target.create_target_machine()
    backing_module = binding.parse_assembly("")
    return binding.create_mcjit_compiler(backing_module, target_machine)

def assemble(module):
    opt = binding.ModulePassManager()
    builder = binding.PassManagerBuilder()
    builder.opt_level = 3
    builder.populate(opt)
    mod = binding.parse_assembly(str(module))
    mod.verify()
    opt.run(mod)
    return mod

def register_module(llvm_mod, dump_llvm=False):
    assert len(llvm_mod.functions) == 1
    engine = get_jit_engine()
    native_mod = assemble(llvm_mod)
    if dump_llvm:
        print(native_mod)
    engine.add_module(native_mod)
    engine.finalize_object()
    return engine.get_function_address(llvm_mod.functions[0].name)

def run_marshalled(func, func_ptr, *args):
    # Gather argument types
    arg_types = [arg.type for arg in func.args]

    # Create signature
    ret_type = MarshalledArg.to_ctype(func.return_value.type)
    arg_ctypes = [MarshalledArg.to_ctype(arg) for arg in arg_types]
    cfunc = ctypes.CFUNCTYPE(ret_type, *arg_ctypes)(func_ptr)

    # Call the function
    with contextlib.ExitStack() as stack:
        func_args = [stack.enter_context(MarshalledArg(arg, ty)) for arg, ty in zip(args, arg_types)]
        value = cfunc(*func_args)
        if ret_type == ctypes.c_char:
            value = value == b'\x01'
        return value

def _foo(f, generate_llvm=True, dump_unescaped=False, dump_ir=False,
         dump_llvm=False, dump_opt=False, depth=1):
    # get caller's globals and locals for escape evaluation
    _globals = inspect.stack()[depth][0].f_globals
    _locals = inspect.stack()[depth][0].f_locals
    parse_tree = ast.parse(inspect.getsource(f).strip()).body[0]
    unescaped = ProcessEscape(f.__code__.co_varnames, _globals, _locals).visit(parse_tree)

    if dump_unescaped:
        import astunparse
        processed_src = astunparse.unparse(unescaped.body).strip()
        header_src = 'def ___{}_inner({}):\n{}'.format(
                f.__name__,
                ', '.join(f.__code__.co_varnames),
                '\n'.join(map(lambda x: '\t' + x, processed_src.split('\n'))))
        print(header_src)

    if generate_llvm:
        func = Frontend().visit(parse_tree)
        TypeChecker.analyze(func)
        if dump_ir:
            from printer import IRPrinter
            print(IRPrinter().visit(func))

        llvm_mod = Backend.generate_llvm(func)
        if dump_llvm:
            print(str(llvm_mod))

        func_ptr = register_module(llvm_mod, dump_opt)

        def interpret(*interpret_args):
            return Interpreter().call_fun(func, *interpret_args)

        native_runner = functools.partial(run_marshalled, llvm_mod.functions[0], func_ptr)
        native_runner.interpret = interpret
        native_runner.py = f
        return native_runner
    else:
        # convert ast -> python and exec it
        import astunparse
        processed_src = astunparse.unparse(unescaped.body).strip()
        header_src = 'def ___{}_inner({}):\n{}'.format(
                f.__name__,
                ', '.join(f.__code__.co_varnames),
                '\n'.join(map(lambda x: '\t' + x, processed_src.split('\n'))))
        exec(header_src, _globals, _locals)
        return _locals['___{}_inner'.format(f.__name__)]

def foo(*args, **kwargs):
    if len(args) == 1:
        kwargs['depth'] = 2
        return _foo(args[0], **kwargs)
    else:
        return functools.partial(_foo, **kwargs)

