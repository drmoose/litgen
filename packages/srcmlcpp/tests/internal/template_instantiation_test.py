import pytest

from codemanip import code_utils

from srcmlcpp.srcml_types import *
import srcmlcpp


def code_first_function_decl(code: str) -> CppFunctionDecl:
    srcml_options = srcmlcpp.SrcmlOptions()
    r = srcmlcpp.srcmlcpp_main.code_first_function_decl(srcml_options, code)
    return r


def code_first_struct(code: str) -> CppStruct:
    srcml_options = srcmlcpp.SrcmlOptions()
    r = srcmlcpp.srcmlcpp_main.code_first_struct(srcml_options, code)
    return r


def test_instantiate_function():
    #
    # simple instantiation
    #
    code = "template<typename T> T f();"
    f = code_first_function_decl(code)
    f_inst = f.with_instantiated_template(TemplateInstantiation.from_type_str("int"))
    code_utils.assert_are_codes_equal(f_inst, "template</*typename T=int*/> int f<int>();")

    #
    # simple instantiation with specifiers
    #
    code = "template<typename T> void f(T * v);"
    f = code_first_function_decl(code)
    f_inst = f.with_instantiated_template(TemplateInstantiation.from_type_str("const int"))
    code_utils.assert_are_codes_equal(f_inst, "template</*typename T=const int*/> void f<const int>(const int * v);")

    #
    # progressive instantiation for multiple template parameters
    #
    code = "template<typename T, class U> T f(const U& u);"
    f = code_first_function_decl(code)
    f_inst_1 = f.with_instantiated_template(TemplateInstantiation.from_type_str("int"))
    assert f_inst_1 is not None
    code_utils.assert_are_codes_equal(f_inst_1, "template</*typename T=int, class U*/> int f<int>(const U & u);")
    f_inst_2 = f_inst_1.with_instantiated_template(TemplateInstantiation.from_type_str("double"))
    assert f_inst_2 is not None
    code_utils.assert_are_codes_equal(
        f_inst_2, "template</*typename T=int, class U=double*/> int f<int, double>(const double & u);"
    )

    #
    # we should not be able to further instantiate f_inst_2, since it is fully specialized
    #
    with pytest.raises(AssertionError):
        _ = f_inst_2.with_instantiated_template(TemplateInstantiation.from_type_str("double"))

    #
    # direct multiple instantiation
    #
    code = "template<typename T, class U> T f(const U& u);"
    f = code_first_function_decl(code)
    f_inst = f.with_instantiated_template(
        TemplateInstantiation.from_instantiations(
            [TemplateInstantiationPart("int"), TemplateInstantiationPart("double")]
        )
    )
    code_utils.assert_are_codes_equal(
        f_inst, "template</*typename T=int, class U=double*/> int f<int, double>(const double & u);"
    )

    #
    # instantiate a non templated function
    # (it is valid if this function is a non template method of a template class)
    # In this case, we *have* to specify the template name
    #
    code = "T f();"
    f = code_first_function_decl(code)
    f_inst = f.with_instantiated_template(TemplateInstantiation.from_type_str("int", "T"))
    code_utils.assert_are_codes_equal(f_inst, "int f();")

    #
    # instantiate a non templated function with a template name that it does not use
    # In that case, with_instantiated_template should return None to indicate that no change is needed.
    #
    code = "T f();"
    f = code_first_function_decl(code)
    f_inst = f.with_instantiated_template(TemplateInstantiation.from_type_str("int", "U"))
    assert f_inst is None

    #
    # instantiate with complex dependent parameter type
    #
    code = "template<typename T> T sum2(array<T, 2> values);"
    f = code_first_function_decl(code)
    f_inst = f.with_instantiated_template(TemplateInstantiation.from_type_str("vector<int>"))
    code_utils.assert_are_codes_equal(
        f_inst, "template</*typename T=vector<int>*/> vector<int> sum2<vector<int>>(array<vector<int>, 2> values);"
    )


def test_instantiate_class():
    code = """
    template<typename T>
    struct Foo
    {
        T value0, value1;
        int x, y;

        std::array<T, 2> getValue(const T& m);

        struct Inner
        {
            T inner_values[2];
        };

        std::function<T(T)> my_function();
    };
    """
    struct = code_first_struct(code)
    struct_inst = struct.with_instantiated_template(TemplateInstantiation.from_type_str("int"))
    logging.warning("\n" + str(struct_inst))
    code_utils.assert_are_codes_equal(
        str(struct_inst),
        """
        /*template<typename T=int>*/ struct Foo
        {
            public:// <default_access_type/>
                int value0;
                int value1;
                int x;
                int y;

                std::array<int, 2> getValue(const int & m);

                struct Inner
                {
                    public:// <default_access_type/>
                        int inner_values[2];
                };

                std::function<int(int)> my_function();
        };
    """,
    )
