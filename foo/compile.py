import ast
import inspect

from .escape import ProcessEscape

def foo(f):
    # get caller's globals and locals for escape evaluation
    _globals = inspect.stack()[1][0].f_globals
    _locals = inspect.stack()[1][0].f_locals.copy()
    parse_tree = ast.parse(inspect.getsource(f).strip()).body[0]
    unescaped = ProcessEscape(_globals, _locals).visit(parse_tree)

    # import astor
    # print(astor.dump_tree(unescaped.body))

    # convert ast -> python and exec it
    import astunparse
    processed_src = astunparse.unparse(unescaped.body).strip()
    header_src = 'def ___{}_inner({}):\n{}'.format(
            f.__name__,
            ', '.join(f.__code__.co_varnames),
            '\n'.join(map(lambda x: '\t' + x, processed_src.split('\n'))))
    exec(header_src, _globals, _locals)
    print(header_src)
    return _locals['___{}_inner'.format(f.__name__)]

