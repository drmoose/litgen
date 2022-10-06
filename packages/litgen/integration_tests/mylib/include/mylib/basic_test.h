#pragma once
#include "mylib/api_marker.h"

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

// Subtracts two numbers: this will be the function's __doc__ since my_sub does not have an end-of-line comment
MY_API int my_sub(int a, int b) { return a - b; }


// Title that should be published as a top comment in python stub (pyi) and thus not part of __doc__
// (the end-of-line comment will supersede this top comment)
MY_API inline int my_add(int a, int b) { return a + b; } // Adds two numbers


// my_mul should have no user doc (but it will have a typing doc generated by pybind)
// (do not remove the next empty line, or this comment would become my_mul's doc!)

MY_API int my_mul(int a, int b) { return a * b; }

// This should not be published, as it is not marked with MY_API
int my_div(int a, int b) { return a / b;}


// This is a generic function for python, accepting (*args, **kwargs) as arguments
MY_API int my_generic_function(pybind11::args args, const pybind11::kwargs& kwargs)
{
    int r = args.size() + 2 * kwargs.size();
    return r;
}

// Vectorizable functions example
//    Numeric functions (i.e. function accepting and returning only numeric params or py::array), can be vectorized
//    i.e. they will accept numpy arrays as an input.
//
// Auto-vectorization is enabled via the following options:
//     options.fn_namespace_vectorize__regex: str = r"^MathFunctions$"
//     options.fn_vectorize__regex = r".*"
//
namespace MathFunctions // MY_API
{
    MY_API double vectorizable_sum(float x, double y)
    {
        return (double) x + y;
    }
}

/*
For info, below is the python pyi stub that is published for this file:

def my_sub(a: int, b: int) -> int:
    """ Subtracts two numbers: this will be the __doc__ since my_sub does not have an end-of-line comment"""
    pass


# Title that should be published as a top comment in python stub (pyi) and thus not part of __doc__
# (the end-of-line comment will supersede the top comment)
def my_add(a: int, b: int) -> int:
    """ Adds two numbers"""
    pass


# my_mul should have no user doc (but it will have a typing doc generated by pybind)
# (do not remove the next empty line, or this comment would become my_mul's doc!)

def my_mul(a: int, b: int) -> int:
    pass

def my_generic_function(*args, **kwargs) -> int:
    """ This is a generic function for python, accepting (*args, **kwargs) as arguments"""
    pass

 # <submodule MathFunctions>
class MathFunctions: # Proxy class that introduces typings for the *submodule* MathFunctions
    # (This corresponds to a C++ namespace. All method are static!)
    """ Vectorizable functions example
        Numeric functions (i.e. function accepting and returning only numeric params or py::array), can be vectorized
        i.e. they will accept numpy arrays as an input.

     Auto-vectorization is enabled via the following options:
         options.fn_namespace_vectorize__regex: str = r"^MathFunctions$"
         options.fn_vectorize__regex = r".*"
         options.fn_vectorize_prefix = "v_"
         options.fn_vectorize_suffix = "_v"
    """
    def vectorizable_sum(x: float, y: float) -> float:
        pass
    def vectorizable_sum(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        pass

# </submodule MathFunctions>

*/
