import ast
import contextlib
import ctypes
import functools
import inspect

from llvmlite import ir as llvm
import llvmlite.binding as binding

from .backend import Backend
from .escape import ProcessEscape, SubexprVisitor
from .frontend import Frontend
from .interpreter import Interpreter
from .marshalling import MarshalledArg
from .typechecker import TypeChecker

global_vars = {}
anon_id = 0

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
    # assert len(llvm_mod.functions) == 1
    engine = get_jit_engine()
    native_mod = assemble(llvm_mod)
    if dump_llvm:
        print(native_mod)
    engine.add_module(native_mod)
    engine.finalize_object()
    return engine.get_function_address(llvm_mod.functions[-1].name), native_mod

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

class _FuncCallExtractor(SubexprVisitor):
    def __init__(self):
        self.calls = set()

    def visit_Call(self, node):
        self.generic_visit(node)
        blacklist = set((
            'create_int_array',
            'create_float_array',
            'create_bool_array',
            'range'
        ))
        if node.func.id not in blacklist:
            self.calls.add(node.func.id)
        return node

def _scale(f, *, lazy=True, generate_llvm=True, dump_unescaped=False, dump_ir=False,
         dump_llvm=False, dump_opt=False, anonymous=False, depth=1):
    # get caller's globals and locals for escape evaluation
    _globals = inspect.stack()[depth][0].f_globals
    _locals = inspect.stack()[depth][0].f_locals
    params = inspect.getfullargspec(f)[0]
    source = inspect.getsource(f)
    base_indent = len(source) - len(source.lstrip())
    lines = map(lambda _: _[base_indent:], source.split('\n'))
    source = '\n'.join(lines).strip()
    parse_tree = ast.parse(source).body[0]
    unescaped = ProcessEscape(params, _globals, _locals).visit(parse_tree)

    if dump_unescaped:
        import astunparse
        processed_src = astunparse.unparse(unescaped.body).strip()
        header_src = 'def ___{}_inner({}):\n{}'.format(
                f.__name__,
                ', '.join(params),
                '\n'.join(map(lambda x: '\t' + x, processed_src.split('\n'))))
        print(header_src)

    global_name = f.__name__
    extract = _FuncCallExtractor()
    extract.visit(unescaped)
    deps = extract.calls

    if lazy:
        yield

    for dep in deps:
        dp = eval(dep, _globals, _locals)
        if dep != f.__name__ and not dp.is_compiled:
            dp.compile()

    if generate_llvm:
        func = Frontend().visit(unescaped)
        TypeChecker.analyze(func, global_vars)
        if dump_ir:
            import astor
            print(astor.dump_tree(func))

        llvm_mod, ftype = Backend.generate_llvm(func, global_vars)
        if not anonymous:
            global_vars[global_name] = ftype
        if dump_llvm:
            print(str(llvm_mod))

        func_ptr, opcode = register_module(llvm_mod, dump_opt)

        def interpret(*interpret_args):
            return Interpreter().call_fun(func, *interpret_args)

        native_runner = functools.partial(run_marshalled, llvm_mod.functions[-1], func_ptr)
        native_runner.interpret = interpret
        native_runner.py = f
        native_runner.is_scale = True
        native_runner.is_defined = True
        native_runner.is_compiled = True
        def gen_pretty():
            import astunparse
            processed_src = astunparse.unparse(unescaped.body).strip()
            header_src = 'def ___{}_inner({}):\n{}'.format(
                    f.__name__,
                    ', '.join(params),
                    '\n'.join(map(lambda x: '\t' + x, processed_src.split('\n'))))
            return header_src
        native_runner.pretty = gen_pretty
        native_runner.llvm = lambda: str(list(llvm_mod.functions)[-1])
        native_runner.opcode = lambda: str(''.join(map(str, opcode.functions)))
        def compile_inner(*args, **kwargs):
            raise RuntimeError("already compiled")
        native_runner.compile = compile_inner
        if anonymous:
            global anon_id
            native_runner.scale_name = '<anonymous_{}>'.format(anon_id)
            anon_id += 1
        else:
            native_runner.scale_name = global_name
        return native_runner
    else:
        # convert ast -> python and exec it
        import astunparse
        processed_src = astunparse.unparse(unescaped.body).strip()
        header_src = 'def ___{}_inner({}):\n{}'.format(
                f.__name__,
                ', '.join(params),
                '\n'.join(map(lambda x: '\t' + x, processed_src.split('\n'))))
        exec(header_src, _globals, _locals)
        return _locals['___{}_inner'.format(f.__name__)]

def scale(*args, **kwargs):
    if len(args) == 1:
        kwargs['depth'] = 2
        gen = _scale(args[0], **kwargs)
        try:
            next(gen)
        except StopIteration as e:
            return e.value
        else:
            def inner(*args, **kwargs):
                if not inner.is_compiled:
                    inner.compile()
                return inner.func(*args, **kwargs)
            inner.is_scale = True
            inner.is_defined = True
            inner.is_compiled = False
            inner.func = gen
            inner.scale_name = args[0].__name__
            def compile_inner(inner):
                if inner.is_compiled:
                    raise RuntimeError("already compiiled")
                try:
                    next(inner.func)
                except StopIteration as e:
                    for x in dir(e.value):
                        if x[:2] != '__':
                            setattr(inner, x, getattr(e.value, x))
                    inner.func = e.value
            inner.compile = functools.partial(compile_inner, inner)
            return inner
    else:
        return functools.partial(scale, **kwargs)

class _FuncDefTypeExtractor(SubexprVisitor):
    def visit_List(self, node):
        return [self.visit(x) for x in node.elts]

    def visit_Name(self, node):
        if node.id == 'int':
            return TypeChecker.int_type
        if node.id == 'float':
            return TypeChecker.float_type
        if node.id == 'bool':
            return TypChecker.bool_typpe
        return node

    def collapse_to_pointer(self, typ):
        if isinstance(typ, list):
            return llvm.PointerType(self.collapse_to_pointer(typ[0]))
        else:
            return typ

    def visit_FunctionDef(self, node):
        args = []
        for x in node.args.args:
            args.append(self.collapse_to_pointer(self.visit(x.annotation)))
        ret = self.collapse_to_pointer(self.visit(node.returns))

        if len(node.body) != 1 or not isinstance(node.body[0], ast.Pass):
            raise TypeError('expected empty function body')

        self.type = llvm.FunctionType(ret, tuple(args))
        return node

def ___declare(f):
    source = inspect.getsource(f)
    base_indent = len(source) - len(source.lstrip())
    lines = map(lambda _: _[base_indent:], source.split('\n'))
    source = '\n'.join(lines).strip()
    parse_tree = ast.parse(source).body[0]

    global_name = f.__name__

    extract = _FuncDefTypeExtractor()
    extract.visit(parse_tree)

    global_vars[global_name] = extract.type

    def inner(*args, **kwargs):
        raise RuntimeError('function only declared, not defined')
    inner.is_scale = True
    inner.is_defined = False
    inner.is_compiled = False

    def compile_inner(*args, **kwargs):
        raise RuntimeError('cannot compile undefined function')
    inner.compile = compile_inner
    inner.scale_name = global_name

    return inner

def __declare(*args, **kwargs):
    if len(args) == 1:
        return ___declare(args[0], **kwargs)
    else:
        return functools.partial(__declare, **kwargs)

def ___native(f):
    source = inspect.getsource(f)
    base_indent = len(source) - len(source.lstrip())
    lines = map(lambda _: _[base_indent:], source.split('\n'))
    source = '\n'.join(lines).strip()
    parse_tree = ast.parse(source).body[0]

    global_name = f.__name__

    extract = _FuncDefTypeExtractor()
    extract.visit(parse_tree)

    global_vars[global_name] = extract.type

    def inner(*args, **kwargs):
        raise NotImplementedError('calling native function from python not supported')
    inner.is_scale = True
    inner.is_defined = True
    inner.is_compiled = True
    inner.scale_name = global_name

    def compile_inner(*args, **kwargs):
        raise RuntimeError('cannot compile native function declaration')
    inner.compile = compile_inner

    return inner

def __native(*args, **kwargs):
    if len(args) == 1:
        return ___native(args[0], **kwargs)
    else:
        return functools.partial(__native, **kwargs)

varid = 0
def __newvar():
    global varid
    name = '__scale_generated_var_{}'.format(varid)
    varid += 1
    return ast.Name(id=name)

def __var(name):
    return ast.Name(id=name)

scale.declare = __declare
scale.native = __native
scale.anonymous = functools.partial(scale, anonymous=True)
scale.newvar = __newvar
scale.var = __var

