from .compile import scale
from . import quote

import ast as _ast

goto = _ast.Name('goto', _ast.Load())
label = _ast.Name('label', _ast.Load())

