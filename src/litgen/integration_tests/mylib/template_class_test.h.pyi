# ============================================================================
# This file was autogenerated
# It is presented side to side with its source: template_class_test.h
#    (see integration_tests/bindings/lg_mylib/__init__pyi which contains the full
#     stub code, including this code)
# ============================================================================

# type: ignore
from typing import List
from typing import overload

# <litgen_stub> // Autogenerated code below! Do not edit!
####################    <generated_from:template_class_test.h>    ####################

#  MyTemplateClass is a template class that will be implemented for the types ["int", "std::string"]
#
# See inside autogenerate_mylib.py:
#        options.class_template_options.add_specialization(
#            class_name_regex=r"^MyTemplateClass$",  # r".*" => all classes
#        cpp_types_list=["int", "double"],  # instantiated types
#        naming_scheme=litgen.TemplateNamingScheme.camel_case_suffix,
#        )

#  ------------------------------------------------------------------------
#      <template specializations for class MyTemplateClass>
class MyTemplateClass_int:  # Python specialization for MyTemplateClass<int>
    values: List[int]

    @overload
    def __init__(self) -> None:
        """Standard constructor"""
        pass
    @overload
    def __init__(self, v: List[int]) -> None:
        """Constructor that will need a parameter adaptation"""
        pass
    def sum(self) -> int:
        """Standard method"""
        pass
    def sum2(self, v: List[int]) -> int:
        """Method that requires a parameter adaptation"""
        pass

class MyTemplateClass_string:  # Python specialization for MyTemplateClass<std::string>
    values: List[str]

    @overload
    def __init__(self) -> None:
        """Standard constructor"""
        pass
    @overload
    def __init__(self, v: List[str]) -> None:
        """Constructor that will need a parameter adaptation"""
        pass
    def sum(self) -> str:
        """Standard method"""
        pass
    def sum2(self, v: List[str]) -> str:
        """Method that requires a parameter adaptation"""
        pass

#      </template specializations for class MyTemplateClass>
#  ------------------------------------------------------------------------
####################    </generated_from:template_class_test.h>    ####################

# </litgen_stub> // Autogenerated code end!
