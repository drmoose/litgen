# ============================================================================
# This file was autogenerated
# It is presented side to side with its source: c_extern_c.h
#    (see integration_tests/bindings/lg_mylib/__init__pyi which contains the full
#     stub code, including this code)
# ============================================================================

# type: ignore

# <litgen_stub> // Autogenerated code below! Do not edit!
####################    <generated_from:c_extern_c.h>    ####################
#
#
# Here, we test litgen with C libraries, such a glfw:
#
# Features:
# - Handle #ifdef __cpluscplus
#    __cpluscplus should be assumed to be always True
# - Handle extern:
#        extern "C" { ... }
#    The code inside such a block should be parsed as if extern was not there.
# - Handle functions with a None instead of empty params:
#        None foo(None)
# - unnamed params:
#        None blah(int)
# - Export #define as variable
#    #define GLFW_KEY_LEFT_BRACKET       91  / * [ * /
#    #define GLFW_PLATFORM_ERROR         0x00010008
#    etc.
#

# #ifdef __cplusplus
#
# #endif
#

def extern_c_add(a: int, b: int) -> int:
    pass

def foo_void_param() -> int:
    pass

def foo_unnamed_param(param_0: int, param_1: bool, param_2: float) -> int:
    pass

# This is zero
# Will be published with is comment
ANSWER_ZERO_COMMENTED = 0

# Will be published with its two comments (incl this one)
# This is one
ANSWER_ONE_COMMENTED = 1

# Will be published
HEXVALUE = 0x43242
# Will be published
OCTALVALUE = 0o43242
# Will be published
STRING = "Hello"
# Will be published
FLOAT = 3.14

# #ifdef __cplusplus
#
# #endif
#
####################    </generated_from:c_extern_c.h>    ####################

# </litgen_stub> // Autogenerated code end!