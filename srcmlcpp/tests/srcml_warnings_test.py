import os, sys; _THIS_DIR = os.path.dirname(__file__); sys.path.append(_THIS_DIR + "/../..")

import srcmlcpp
from srcmlcpp.srcml_warnings import SrcMlExceptionDetailed
from srcmlcpp.srcml_options import SrcmlOptions


def test_warnings():
    options = SrcmlOptions()
    options.flag_show_python_callstack = True
    code = "void foo(int a);"

    cpp_unit = srcmlcpp.code_to_cpp_unit(options, code, filename="main.h")
    decl = cpp_unit.block_children[0]

    got_exception = False
    try:
        raise SrcMlExceptionDetailed(decl.srcml_element, "Artificial exception", options)
    except srcmlcpp.SrcMlException as e:
        got_exception = True
        msg = str(e)
        for part in ["test_warning", "function_decl", "main.h:1:1", "void foo", "Artificial exception"]:
            assert part in msg
    assert got_exception == True