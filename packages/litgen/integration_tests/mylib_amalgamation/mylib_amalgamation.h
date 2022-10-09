// THIS FILE WAS GENERATED AUTOMATICALLY. DO NOT EDIT.

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/mylib_main/mylib.h                                                               //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
#include "api_marker.h"


//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/basic_test.h included by mylib/mylib_main/mylib.h                                //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

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
namespace MathFunctions
{
    MY_API double vectorizable_sum(float x, double y)
    {
        return (double) x + y;
    }
}

// Ignored namespace example:
// By default, any namespace whose name contains "internal" or "detail" will be excluded.
// See LitgenOptions.namespace_exclude__regex
namespace Detail
{
    MY_API int foo() { return 42; }
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/header_filter_test.h included by mylib/mylib_main/mylib.h                        //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

// Here, we test that functions placed under unknown preprocessor conditions are not exported by default
// You could choose to add them anyway with:
//    options.srcml_options.header_filter_acceptable_suffixes += "|OBSCURE_OPTION"

#ifdef OBSCURE_OPTION
MY_API int ObscureFunction() { return 42; }
#endif

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/c_style_array_test.h included by mylib/mylib_main/mylib.h                        //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//
// C Style array tests
//


// Tests with const array: since the input numbers are const, their params are published as List[int],
// and the python signature will be:
// -->    def add_c_array2(values: List[int]) -> int:
// (and the runtime will check that the list size is exactly 2)
MY_API inline int const_array2_add(const int values[2]) { return values[0] + values[1];}


// Test with a modifiable array: since the input array is not const, it could be modified.
// Thus, it will be published as a function accepting Boxed values:
// -->    def array2_modify(values_0: BoxedUnsignedLong, values_1: BoxedUnsignedLong) -> None:
MY_API inline void array2_modify(unsigned long values[2])
{
    values[0] = values[1] + values[0];
    values[1] = values[0] * values[1];
}

struct Point2
{
    int x, y;
};

// Test with a modifiable array that uses a user defined struct.
// Since the user defined struct is mutable in python, it will not be Boxed,
// and the python signature will be:
//-->    def get_points(out_0: Point2, out_1: Point2) -> None:
MY_API inline void array2_modify_mutable(Point2 out[2]) { out[0] = {0, 1}; out[1] = {2, 3}; }

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/c_style_buffer_to_pyarray_test.h included by mylib/mylib_main/mylib.h            //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include <stdint.h>
#include <stddef.h>

//
// C Style buffer to py::array tests
//
// litgen is able to recognize and transform pairs of params whose C++ signature resemble
//     (T* data, size_t|int count)
// Where
//   * `T` is a *known* numeric type, or a templated type
//   * `count` name resemble a size
//        (see LitgenOptions.fn_params_buffer_size_names__regex)
//

// add_inside_buffer: modifies a buffer by adding a value to its elements
// Will be published in python as:
// -->    def add_inside_buffer(buffer: np.ndarray, number_to_add: int) -> None:
// Warning, the python function will accept only uint8 numpy arrays, and check it at runtime!
MY_API inline void add_inside_buffer(uint8_t* buffer, size_t buffer_size, uint8_t number_to_add)
{
    for (size_t i  = 0; i < buffer_size; ++i)
        buffer[i] += number_to_add;
}

// buffer_sum: returns the sum of a *const* buffer
// Will be published in python as:
// -->    def buffer_sum(buffer: np.ndarray, stride: int = -1) -> int:
MY_API inline int buffer_sum(const uint8_t* buffer, size_t buffer_size, size_t stride= sizeof(uint8_t))
{
    int sum = 0;
    for (size_t i  = 0; i < buffer_size; ++i)
        sum += (int)buffer[i];
    return sum;
}

// add_inside_two_buffers: modifies two mutable buffers
// litgen will detect that this function uses two buffers of same size.
// Will be published in python as:
// -->    def add_inside_two_buffers(buffer_1: np.ndarray, buffer_2: np.ndarray, number_to_add: int) -> None:
MY_API inline void add_inside_two_buffers(uint8_t* buffer_1, uint8_t* buffer_2, size_t buffer_size, uint8_t number_to_add)
{
    for (size_t i  = 0; i < buffer_size; ++i)
    {
        buffer_1[i] += number_to_add;
        buffer_2[i] += number_to_add;
    }
}

// templated_mul_inside_buffer: template function that modifies an array by multiplying its elements by a given factor
// litgen will detect that this function can be published as using a numpy array.
// It will be published in python as:
// -->    def mul_inside_buffer(buffer: np.ndarray, factor: float) -> None:
//
// The type will be detected at runtime and the correct template version will be called accordingly!
// An error will be thrown if the numpy array numeric type is not supported.
template<typename T> MY_API void templated_mul_inside_buffer(T* buffer, size_t buffer_size, double factor)
{
    for (size_t i  = 0; i < buffer_size; ++i)
        buffer[i] *= (T)factor;
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/c_string_list_test.h included by mylib/mylib_main/mylib.h                        //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include "string.h"

//
// C String lists tests:
//   Two consecutive params (const char *, int | size_t) are exported as List[str]
//
// The following function will be exported with the following python signature:
// -->    def c_string_list_total_size(items: List[str], output_0: BoxedInt, output_1: BoxedInt) -> int:
//
MY_API inline size_t c_string_list_total_size(const char * const items[], int items_count, int output[2])
{
    size_t total = 0;
    for (size_t i = 0; i < items_count; ++i)
        total += strlen(items[i]);
    output[0] = (int)total;
    output[1] = (int)(total + 1);
    return total;
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/modifiable_immutable_test.h included by mylib/mylib_main/mylib.h                 //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include <string>

//
// Modifiable immutable python types test
//

// litgen adapts functions params that use modifiable pointer or reference to a type
// that is immutable in python.
// On the C++ side, these params are modifiable by the function.
// We need to box them into a Boxed type to ensure that any modification made by C++
// is visible when going back to Python.
//
// Note: immutable data types in python are
//   - Int, Float, String (correctly handled by litgen)
//   - Complex, Bytes (not handled)
//   - Tuple (not handled)


/////////////////////////////////////////////////////////////////////////////////////////////
// Test Part 1: in the functions below, the value parameters will be "Boxed"
//
// This is caused by the following options during generation:
//     options.fn_params_replace_modifiable_immutable_by_boxed__regex = code_utils.join_string_by_pipe_char([
//         r"^Toggle",
//         r"^Modify",
//      ])
/////////////////////////////////////////////////////////////////////////////////////////////


// Test with pointer:
// Will be published in python as:
// -->    def toggle_bool_pointer(v: BoxedBool) -> None:
MY_API void ToggleBoolPointer(bool *v)
{
    *v = !(*v);
}

// Test with nullable pointer
// Will be published in python as:
// -->    def toggle_bool_nullable(v: BoxedBool = None) -> None:
MY_API void ToggleBoolNullable(bool *v = NULL)
{
    if (v != NULL)
        *v = !(*v);
}

// Test with reference
// Will be published in python as:
// -->    def toggle_bool_reference(v: BoxedBool) -> None:
MY_API void ToggleBoolReference(bool &v)
{
    v = !(v);
}

// Test modifiable String
// Will be published in python as:
// -->    def modify_string(s: BoxedString) -> None:
MY_API void ModifyString(std::string* s) { (*s) += "hello"; }


/////////////////////////////////////////////////////////////////////////////////////////////
//
// Test Part 2: in the functions below, the python return type is modified:
// the python functions will return a tuple:
//     (original_return_value, modified_parameter)
//
// This is caused by the following options during generation:
//
//     options.fn_params_output_modifiable_immutable_to_return__regex = r"^Change"
/////////////////////////////////////////////////////////////////////////////////////////////


// Test with int param + int return type
// Will be published in python as:
// --> def change_bool_int(label: str, value: int) -> Tuple[bool, int]:
MY_API bool ChangeBoolInt(const char* label, int * value)
{
    *value += 1;
    return true;
}

// Will be published in python as:
// -->    def change_void_int(label: str, value: int) -> int:
MY_API void ChangeVoidInt(const char* label, int * value)
{
    *value += 1;
}

// Will be published in python as:
// -->    def change_bool_int2(label: str, value1: int, value2: int) -> Tuple[bool, int, int]:
MY_API bool ChangeBoolInt2(const char* label, int * value1, int * value2)
{
    *value1 += 1;
    *value2 += 2;
    return false;
}

// Will be published in python as:
// -->    def change_void_int_default_null(label: str, value: Optional[int] = None) -> Tuple[bool, Optional[int]]:
MY_API bool ChangeVoidIntDefaultNull(const char* label, int * value = nullptr)
{
    if (value != nullptr)
        *value += 1;
    return true;
}

// Will be published in python as:
// -->    def change_void_int_array(label: str, value: List[int]) -> Tuple[bool, List[int]]:
MY_API bool ChangeVoidIntArray(const char* label, int value[3])
{
    value[0] += 1;
    value[1] += 2;
    value[2] += 3;
    return true;
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/overload_test.h included by mylib/mylib_main/mylib.h                             //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//
// litgen is able to detect automatically the presence of overloads that require
// to use `py::overload_cast<...>` when publishing
//

//
// overload on free functions
//

MY_API int add_overload(int a, int b) { return a + b; } // type: ignore
MY_API int add_overload(int a, int b, int c) { return a + b + c; } // type: ignore

//
// overload on methods
//

struct FooOverload
{
    MY_API int add_overload(int a, int b) { return a + b; } // type: ignore
    MY_API int add_overload(int a, int b, int c) { return a + b + c; } // type: ignore
};

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/enum_test.h included by mylib/mylib_main/mylib.h                                 //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

// BasicEnum: a simple C-style enum
enum BasicEnum
{
    // C-style enums often contain a prefix that is the enum name in itself, in order
    // not to pollute the parent namespace.
    // Since enum members do not leak to the parent namespace in python, litgen will remove the prefix by default.

    BasicEnum_a = 1, // This will be exported as BasicEnum.a
    BasicEnum_aa,    // This will be exported as BasicEnum.aa
    BasicEnum_aaa,   // This will be exported as BasicEnum.aaa

    // Lonely comment

    // This is value b
    BasicEnum_b,

    BasicEnum_count // By default this "count" item is not exported: see options.enum_flag_skip_count
};


// ClassEnum: a class enum that should be published
enum class ClassEnum
{
    On = 0,
    Off,
    Unknown
};


// EnumDetail should not be published, as its name ends with "Detail"
// (see `options.enum_exclude_by_name__regex = "Detail$"` inside autogenerate_mylib.py)
enum class EnumDetail
{
    On,
    Off,
    Unknown
};

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/class_test.h included by mylib/mylib_main/mylib.h                                //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include <stdio.h>
#include <vector>


// This is the class doc. It will be published as MyClass.__doc__
class MyClass
{
public:
    MyClass(int factor = 10, const std::string& message = "hello"): factor(factor), message(message) {}
    ~MyClass() {}


    ///////////////////////////////////////////////////////////////////////////
    // Simple struct members
    ///////////////////////////////////////////////////////////////////////////
    int factor = 10, delta = 0;
    std::string message;


    ///////////////////////////////////////////////////////////////////////////
    // Stl container members
    ///////////////////////////////////////////////////////////////////////////

    // By default, modifications from python are not propagated to C++ for stl containers
    // (see https://pybind11.readthedocs.io/en/stable/advanced/cast/stl.html)
    std::vector<int> numbers;
    // However you can call dedicated modifying methods
    MY_API void append_number_from_cpp(int v) { numbers.push_back(v); }


    ///////////////////////////////////////////////////////////////////////////
    // Fixed size *numeric* array members
    //
    // They will be published as a py::array, and modifications will be propagated
    // on both sides transparently.
    ///////////////////////////////////////////////////////////////////////////

    int values[2] = {0, 1};
    bool flags[3] = {false, true, false};
    // points is a fixed size array, but not of a numeric type. It will *not* be published!
    Point2 points[2];

    static const int const_static_value = 101;
    static int static_value;

    ///////////////////////////////////////////////////////////////////////////
    // Simple methods
    ///////////////////////////////////////////////////////////////////////////

    // calc: example of simple method
    MY_API int calc(int x) { return x * factor + delta; }
    // set_message: another example of simple method
    MY_API void set_message(const std::string & m) { message = m;}

    // unpublished_method: this function should not be published (no MY_API marker)
    int unpublished_method(int x) { return x * factor + delta + 3;}

    ///////////////////////////////////////////////////////////////////////////
    // Static method
    ///////////////////////////////////////////////////////////////////////////

    // Returns a static message
    MY_API static std::string static_message() { return std::string("Hi!"); }
};


// Struct_Detail should not be published, as the options exclude classes whose name end in "Detail".
// See this line in autogenerate_mylib.py:
//      options.class_exclude_by_name__regex = "Detail$"
struct Struct_Detail
{
    int a = 0;
};


// MySingletonClass: demonstrate how to instantiate a singleton
// - The instance method shall return with return_value_policy::reference
// - The destructor may be private
class MySingletonClass
{
public:
    int value = 0;

    MY_API static MySingletonClass& instance() // py::return_value_policy::reference
    {
        static MySingletonClass instance;
        return instance;
    }
private:
    // For a singleton class, the destructor is typically private
    // This will be mentioned in the pydef code:
    // see https://pybind11.readthedocs.io/en/stable/advanced/classes.html#non-public-destructors
    ~MySingletonClass() {}
};


const int MyClass::const_static_value;
int MyClass::static_value = 102;


// This struct is final, and thus cannot be inherited from python
struct MyFinalClass final
{
    MY_API int foo() { return 42; };
};


// This class accepts dynamic attributes
// see autogenerate_mylib.py:
//     options.class_dynamic_attributes__regex = r"Dynamic$"
struct MyStructDynamic
{
    int cpp_member = 1;
};

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/class_inheritance_test.h included by mylib/mylib_main/mylib.h                    //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include <memory>


namespace Animals
{
    struct Animal
    {
        MY_API Animal(const std::string &name) : name(name) { }
        std::string name;

        virtual ~Animal() = default;
    };

    struct Dog : Animal
    {
        MY_API Dog(const std::string &name) : Animal(name + "_dog") { }
        MY_API virtual std::string bark() const { return "BIG WOOF!"; }

        virtual ~Dog() = default;
    };

}

namespace Home
{
    struct Pet
    {
        MY_API bool is_pet() const { return true; }
    };

    struct PetDog: public Animals::Dog, public Pet
    {
        MY_API PetDog(const std::string &name): Animals::Dog(name), Pet() {}
        MY_API virtual std::string bark() const { return "woof"; }

        virtual ~PetDog() = default;
    };

}

// Test that downcasting works: the return type is Animal, but it should bark!
MY_API std::unique_ptr<Animals::Animal> make_dog()
{
    return std::make_unique<Animals::Dog>("Rolf");
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/class_adapt_test.h included by mylib/mylib_main/mylib.h                          //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include <cstddef>
#include <cstdint>

struct Color4
{
    // The constructor params will automatically be "adapted" into std::array<uint8_t, 4>
    MY_API Color4(const uint8_t _rgba[4])
    {
        for (size_t i = 0; i < 4; ++i)
            rgba[i] = _rgba[i];
    }

    // This member will be stored as a modifiable numpy array
    uint8_t rgba[4];
};

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/class_virtual_test.h included by mylib/mylib_main/mylib.h                        //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////


/*
This test will exercise the following options:

    # class_expose_protected_methods__regex:
    # regex giving the list of class names for which we want to expose protected methods.
    # (by default, only public methods are exposed)
    # If set, this will use the technique described at
    # https://pybind11.readthedocs.io/en/stable/advanced/classes.html#binding-protected-member-functions)
    class_expose_protected_methods__regex: str = ""

    # class_expose_protected_methods__regex:
    # regex giving the list of class names for which we want to be able to override virtual methods
    # from python.
    # (by default, this is not possible)
    # If set, this will use the technique described at
    # https://pybind11.readthedocs.io/en/stable/advanced/classes.html#overriding-virtual-functions-in-python
    #
    # Note: if you want to override protected functions, also fill `class_expose_protected_methods__regex`
    class_override_virtual_methods_in_python__regex: str = ""
 */

namespace Root
{
    namespace Inner
    {
        class MyVirtualClass
        {
        public:
            virtual ~MyVirtualClass() = default;

            MY_API std::string foo_concrete(int x, const std::string& name)
            {
                std::string r =
                      std::to_string(foo_virtual_protected(x))
                    + "_" + std::to_string(foo_virtual_public_pure())
                    + "_" + foo_virtual_protected_const_const(name);
                return r;
            }

            MY_API virtual int foo_virtual_public_pure() const = 0;
        protected:
            MY_API virtual int foo_virtual_protected(int x) const { return 42 + x; }
            MY_API virtual std::string foo_virtual_protected_const_const(const std::string& name) const {
                return std::string("Hello ") + name;
            }
        };

        // Here, we test Combining virtual functions and inheritance
        // See https://pybind11.readthedocs.io/en/stable/advanced/classes.html#combining-virtual-functions-and-inheritance
        class MyVirtualDerivate: public MyVirtualClass
        {
        public:
            MyVirtualDerivate(): MyVirtualClass() {};
            MY_API int foo_virtual_public_pure() const override { return 53; };
            MY_API virtual int foo_derivate() { return 48; }
        };
    }
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/return_value_policy_test.h included by mylib/mylib_main/mylib.h                  //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//
// return_value_policy:
//
// If a function has an end-of-line comment which contains `return_value_policy::reference`,
// and if this function returns a pointer or a reference, litgen will automatically add
// `pybind11::return_value_policy::reference` when publishing it.
//
// Notes: `reference` could be replaced by `take_ownership`, or any other member of `pybind11::return_value_policy`
//
// You can also set a global options for matching functions names that return a reference or a pointer
//     see
//             LitgenOptions.fn_return_force_policy_reference_for_pointers__regex
//     and
//             LitgenOptions.fn_return_force_policy_reference_for_references__regex: str = ""


struct MyConfig
{
    //
    // For example, singletons (such as the method below) should be returned as a reference,
    // otherwise python might destroy the singleton instance as soon as it goes out of scope.
    //

    MY_API static MyConfig& Instance() // py::return_value_policy::reference
    {
        static MyConfig instance;
        return instance;
    }

    int value = 0;
};

MY_API MyConfig* MyConfigInstance() { return & MyConfig::Instance(); } // py::return_value_policy::reference

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/inner_class_test.h included by mylib/mylib_main/mylib.h                          //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////


namespace SomeNamespace
{
    struct ParentStruct
    {
        struct InnerStruct
        {
            int value;

            InnerStruct(int value = 10) : value(value) {}
            MY_API int add(int a, int b) { return a + b; }
        };

        enum class InnerEnum
        {
            Zero = 0,
            One,
            Two,
            Three
        };

        InnerStruct inner_struct;
        InnerEnum inner_enum = InnerEnum::Three;
    };
} // namespace SomeNamespace

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/mix_adapters_class_test.h included by mylib/mylib_main/mylib.h                   //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// More complex tests, where we combine litgen function adapters with classes and namespace
//
// The main intent of these tests is to verify that the generated code compiles.
// The corresponding python test file will not test all these functions
// (as they are in fact copy/pasted/adapted from other tests)
//



namespace SomeNamespace
{
    struct Blah
    {
        MY_API void ToggleBoolPointer(bool *v)//, int vv[2])
        {
            *v = !(*v);
        }

        MY_API void ToggleBoolPointerGetPoints(bool *v, int vv[2])
        {
            *v = !(*v);
        }


        MY_API void ModifyString(std::string* s) { (*s) += "hello"; }



        MY_API bool ChangeBoolInt(const char* label, int * value)
        {
            *value += 1;
            return true;
        }


        MY_API inline void add_inside_buffer(uint8_t* buffer, size_t buffer_size, uint8_t number_to_add)
        {
            for (size_t i  = 0; i < buffer_size; ++i)
                buffer[i] += number_to_add;
        }

        template<typename T> MY_API void templated_mul_inside_buffer(T* buffer, size_t buffer_size, double factor)
        {
            for (size_t i  = 0; i < buffer_size; ++i)
                buffer[i] *= (T)factor;
        }

        MY_API inline int const_array2_add(const int values[2]) { return values[0] + values[1];}

        MY_API inline size_t c_string_list_total_size(const char * const items[], int items_count, int output[2])
        {
            size_t total = 0;
            for (size_t i = 0; i < items_count; ++i)
                total += strlen(items[i]);
            output[0] = (int)total;
            output[1] = (int)(total + 1);
            return total;
        }

    }; // struct Blah


    namespace SomeInnerNamespace
    {
        MY_API void ToggleBoolPointer(bool *v)//, int vv[2])
        {
            *v = !(*v);
        }

        MY_API void ToggleBoolPointerGetPoints(bool *v, int vv[2])
        {
            *v = !(*v);
        }


        MY_API void ModifyString(std::string* s) { (*s) += "hello"; }



        MY_API bool ChangeBoolInt(const char* label, int * value)
        {
            *value += 1;
            return true;
        }


        MY_API inline void add_inside_buffer(uint8_t* buffer, size_t buffer_size, uint8_t number_to_add)
        {
            for (size_t i  = 0; i < buffer_size; ++i)
                buffer[i] += number_to_add;
        }

        template<typename T> MY_API void templated_mul_inside_buffer(T* buffer, size_t buffer_size, double factor)
        {
            for (size_t i  = 0; i < buffer_size; ++i)
                buffer[i] *= (T)factor;
        }

        MY_API inline int const_array2_add(const int values[2]) { return values[0] + values[1];}

        MY_API inline size_t c_string_list_total_size(const char * const items[], int items_count, int output[2])
        {
            size_t total = 0;
            for (size_t i = 0; i < items_count; ++i)
                total += strlen(items[i]);
            output[0] = (int)total;
            output[1] = (int)(total + 1);
            return total;
        }

    } // namespace SomeInnerNamespace

}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/namespace_test.h included by mylib/mylib_main/mylib.h                            //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////


MY_API int FooRoot() { return 42; }

namespace details // MY_API This namespace should be excluded (see options.namespace_exclude__regex)
{
    MY_API int FooDetails() { return 43; }
}

namespace // MY_API This anonymous namespace should be excluded
{
    MY_API int LocalFunction() { return 44; }
}

namespace Mylib  // MY_API This namespace should not be outputted as a submodule (it is considered a root namespace)
{
    // this is an inner namespace (this comment should become the namespace doc)
    namespace Inner
    {
        MY_API int FooInner() { return 45; }
    }

    // This is a second occurrence of the same inner namespace
    // The generated python module will merge these occurrences
    // (and this comment will be ignored, since the Inner namespace already has a doc)
    namespace Inner
    {
        MY_API int FooInner2() { return 46; }
    }
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/operators.h included by mylib/mylib_main/mylib.h                                 //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

struct IntWrapper
{
    int value;
    IntWrapper(int v) : value(v) {}

    // arithmetic operators
    MY_API IntWrapper operator+(IntWrapper b) { return IntWrapper{ value + b.value}; }
    MY_API IntWrapper operator-(IntWrapper b) { return IntWrapper{ value - b.value }; }

    // Unary minus operator
    MY_API IntWrapper operator-() { return IntWrapper{ -value }; }

    // Comparison operator
    MY_API bool operator<(IntWrapper b) { return value < b.value; }

    // Two overload of the += operator
    MY_API IntWrapper operator+=(IntWrapper b) { value += b.value; return *this; }
    MY_API IntWrapper operator+=(int b) { value += b; return *this; }

    // Two overload of the call operator, with different results
    MY_API int operator()(IntWrapper b) { return value * b.value + 2; }
    MY_API int operator()(int b) { return value * b + 3; }
};


struct IntWrapperSpaceship
{
    int value;

    IntWrapperSpaceship(int v): value(v) {}

    // Test spaceship operator, which will be split into 5 operators in Python!
    // ( <, <=, ==, >=, >)
    // Since we have two overloads, 10 python methods will be built
    MY_API int operator<=>(IntWrapperSpaceship& o) { return value - o.value; }
    MY_API int operator<=>(int& o) { return value - o; }
};

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/call_policies_test.h included by mylib/mylib_main/mylib.h                        //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

#include <iostream>

struct CallGuardLogger;


// ============================================================================
// call_guard
// ============================================================================
// If you add a comment to the function with reads:
//     py::call_guard<YourCallGuard>()
// Then, it will be taken into account
// See https://pybind11.readthedocs.io/en/stable/advanced/functions.html#call-guard
// The comment may be a comment on previous line or an end-of-line comment

MY_API void call_guard_tester() // py::call_guard<CallGuardLogger>()
{
    std::cout << "call_guard_tester\n";
}


// ============================================================================
// keep-alive
// ============================================================================
// If you add a comment to the function with reads:
//     py::keep-alive<1, 2>()
// Then, it will be taken into account
// See https://pybind11.readthedocs.io/en/stable/advanced/functions.html#keep-alive
// The comment may be a comment on previous line or an end-of-line comment
//
// (No integration test implemented for this)


// ============================================================================
// return value policy
// => see doc inside return_value_policy_test.h
// ============================================================================


// ============================================================================
// CallGuardLogger: dummy call guard for the tests
// ============================================================================
struct CallGuardLogger
{
    CallGuardLogger() {
        ++nb_construct;
    }
    ~CallGuardLogger() {
        ++nb_destroy;
    }

    static int nb_construct;
    static int nb_destroy;
};

int CallGuardLogger::nb_construct = 0;
int CallGuardLogger::nb_destroy = 0;

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/template_function_test.h included by mylib/mylib_main/mylib.h                    //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////


// AddTemplated is a template function that will be implemented for the types ["int", "double", "std::string"]
//
// See inside autogenerate_mylib.py:
//     options.fn_template_options.add_specialization(r"^AddTemplated$", ["int", "double", "std::string"])

template<typename T>
MY_API T AddTemplated(T a, T b)
{
    return  a + b;
}


// SumVectorAndCArray is a template function that will be implemented for the types ["int", "std::string"]
//
// Here, we test two additional thing:
//  - nesting of the T template parameter into a vector
//  - mixing template and function parameter adaptations (here other_values[2] will be transformed into a List[T]
//
// See inside autogenerate_mylib.py:
//     options.fn_template_options.add_specialization(r"^SumVector", ["int", "std::string"])

template<typename T>
MY_API T SumVectorAndCArray(std::vector<T> xs, const T other_values[2])
{
    T sum = T{};
    for (const T & v: xs )
        sum += v;
    sum += other_values[0];
    sum += other_values[1];
    return sum;
}


// Same test, as a method

struct FooTemplateFunctionTest
{
    template<typename T>
    MY_API T SumVectorAndCArray(std::vector<T> xs, const T other_values[2])
    {
        T sum = T{};
        for (const T & v: xs )
            sum += v;
        sum += other_values[0];
        sum += other_values[1];
        return sum;
    }
};

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/template_class_test.h included by mylib/mylib_main/mylib.h                       //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////


//  MyTemplateClass is a template class that will be implemented for the types ["int", "std::string"]
//
// See inside autogenerate_mylib.py:
//        options.class_template_options.add_specialization(
//            class_name_regex=r"^MyTemplateClass$",  # r".*" => all classes
//        cpp_types_list=["int", "double"],  # instantiated types
//        naming_scheme=litgen.TemplateNamingScheme.camel_case_suffix,
//        )

template<typename T>
struct MyTemplateClass
{
public:
    std::vector<T> values;

    // Standard constructor
    MyTemplateClass() {}

    // Constructor that will need a parameter adaptation
    MyTemplateClass(const T v[2]) {
        values.push_back(v[0]);
        values.push_back(v[1]);
    }

    // Standard method
    MY_API T sum()
    {
        T r = {};
        for (const auto & x: values)
            r += x;
        return r;
    }

    // Method that requires a parameter adaptation
    MY_API T sum2(const T v[2])
    {
        return sum() + v[0] + v[1];
    }
};


//////////////////////////////////////////////////////////////////////////////////////////////////////////////////
//                       mylib/mylib_main/mylib.h continued                                                     //
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//#include "mylib/sandbox.h"
