from dataclasses import dataclass
from typing import cast

from munch import Munch  # type: ignore

from srcmlcpp.srcml_types import *

from litgen.internal import cpp_to_python
from litgen.internal.context.litgen_context import LitgenContext
from litgen import LitgenOptions
from litgen.internal.adapted_types.adapted_decl import AdaptedDecl
from litgen.internal.adapted_types.adapted_element import AdaptedElement


@dataclass
class AdaptedParameter(AdaptedElement):
    def __init__(self, lg_context: LitgenContext, param: CppParameter) -> None:
        super().__init__(lg_context, param)

    # override
    def cpp_element(self) -> CppParameter:
        return cast(CppParameter, self._cpp_element)

    # override
    def _str_stub_lines(self) -> List[str]:
        raise NotImplementedError()

    # override
    def _str_pydef_lines(self) -> List[str]:
        raise NotImplementedError()

    def is_modifiable_python_immutable_fixed_size_array(self) -> bool:
        is_python_immutable = self.adapted_decl().is_immutable_for_python()

        type_modifiers = self.cpp_element().decl.cpp_type.modifiers
        type_specifiers = self.cpp_element().decl.cpp_type.specifiers

        has_no_modifiers = type_modifiers == []
        is_fixed_size_array = self.cpp_element().decl.is_c_array_known_fixed_size()
        is_const = "const" in type_specifiers

        r = has_no_modifiers and is_fixed_size_array and is_python_immutable and not is_const
        return r

    def is_modifiable_python_immutable_ref_or_pointer(self) -> bool:
        is_python_immutable = self.adapted_decl().is_immutable_for_python()

        type_modifiers = self.cpp_element().decl.cpp_type.modifiers
        type_specifiers = self.cpp_element().decl.cpp_type.specifiers

        is_reference_or_pointer = (type_modifiers == ["*"]) or (type_modifiers == ["&"])
        is_const = "const" in type_specifiers
        is_modifiable = is_reference_or_pointer and not is_const
        r = is_modifiable and is_python_immutable
        return r

    def adapted_decl(self) -> AdaptedDecl:
        adapted_decl = AdaptedDecl(self.lg_context, self.cpp_element().decl)
        return adapted_decl


@dataclass
class AdaptedFunction(AdaptedElement):
    """
    AdaptedFunction is at the heart of litgen's function and parameters transformations.

    Note: AdaptedFunction will handle function, methods and constructors

    Litgen may apply some adaptations to function  parameters:
        * c buffers are transformed to py::arrays
        * c strings lists are transformed to List[string]
        * c arrays are boxed or transformed to List
        * variadic format params are discarded
        * (etc.)

    AdaptedFunction may contain two cpp functions:
        * self._cpp_element / self.cpp_element() will contain the original C++ function declaration
        * self.cpp_adapted_function is an adapted C++ function where some parameters might have been adapted.

    Below is a full concrete example in order to clarify.

    1/ Given this C++ function
            ````cpp
            // This is foo's doc:
            //     :param buffer & count: modifiable buffer and its size
            //     :param out_values: output double values
            //     :param in_flags: input bool flags
            //     :param text and ... : formatted text
            void Foo(uint8_t * buffer, size_t count, double out_values[2], const bool in_flags[2], const char* text, ...);
            ````

    2/ Then the generated python callable function will have the following signature in the stub:

        ````python
        def foo(
            buffer: numpy.ndarray,                             # The C buffer was transformed into a py::array
            out_values_0: BoxedDouble,                         # modifiable array params were "Boxed"
            out_values_1: BoxedDouble,
            in_flags: List[bool],                              # const array params are passed as a list
            text: str                                          # Variadic ("...") params are removed from the signature
            ) -> None:
            ''' This is foo's doc:
            :param buffer: modifiable buffer and its size
            :param out_values: output float values
            :param in_flags: input bool flags
            :param text and ... : formatted text
            '''
            pass
        ````

    3/ And the `cpp_adapted_function` C++ signature would be:
        ````cpp
        void Foo(
            py::array & buffer,
            BoxedDouble & out_values_0, BoxedDouble & out_values_1,
            const std::array<bool, 2>& in_flags,
            const char * text);
        ````

    4/ And `cpp_adapter_code` would contains some C++ code that defines several lambdas in order to adapt
    the new C++ signature to the original one.
    It will be generated by `apply_all_adapters` and it will look like:

        ````cpp
        auto Foo_adapt_c_buffers = [](               // First lambda that calls Foo()
            py::array & buffer,
            double out_values[2],
            const bool in_flags[2],
            const char * text, ... )
        {
            // ... Some glue code
            Foo(static_cast<uint8_t *>(buffer_from_pyarray), static_cast<size_t>(buffer_count), out_values, in_flags, text, );
        };

        auto Foo_adapt_fixed_size_c_arrays = [&Foo_adapt_c_buffers](   // Second lambda that calls the first lambda
            py::array & buffer,
            BoxedDouble & out_values_0, BoxedDouble & out_values_1,
            const std::array<bool, 2>& in_flags,
            const char * text, ... )
        {
            // ... Some glue code
            Foo_adapt_c_buffers(buffer, out_values_raw, in_flags.data(), text, );
        };

        auto Foo_adapt_variadic_format = [&Foo_adapt_fixed_size_c_arrays]( // Third lambda that calls the second lambda
            py::array & buffer,                                            // This is the lambda that is published
            BoxedDouble & out_values_0,                                    // as a python interface!
            BoxedDouble & out_values_1,
            const std::array<bool, 2>& in_flags,
            const char * text)
        {
            // ... Some glue code
            Foo_adapt_fixed_size_c_arrays(buffer, out_values_0, out_values_1, in_flags, "%s", text);
        };
        ````

    5/ And `lambda_to_call` will contain the name of the lambda that is published
      (in our example, it is "Foo_adapt_variadic_format")
    """

    cpp_adapted_function: CppFunctionDecl
    cpp_adapter_code: Optional[str] = None
    lambda_to_call: Optional[str] = None
    return_value_policy: str = ""
    is_overloaded: bool = False
    is_type_ignore: bool = False
    is_vectorize_impl: bool = False

    def __init__(
        self,
        lg_context: LitgenContext,
        function_infos: CppFunctionDecl,
        is_overloaded: bool,
        initial_lambda_to_call: Optional[str] = None,
    ) -> None:
        from litgen.internal import adapt_function_params
        from litgen.internal.adapted_types import operators

        self.cpp_adapted_function = function_infos
        operators.raise_if_unsupported_operator(self.cpp_adapted_function)

        self.cpp_adapter_code = None
        self.lambda_to_call = initial_lambda_to_call
        super().__init__(lg_context, function_infos)
        self._fill_return_value_policy()
        self._fill_is_type_ignore()

        self.is_overloaded = is_overloaded
        if code_utils.does_match_regex(self.options.fn_force_overload__regex, self.cpp_element().function_name):
            self.is_overloaded = True

        if self.cpp_element().is_inferred_return_type():
            self.cpp_element().cpp_element_comments.comment_end_of_line += "\n(C++ auto return type)"

        adapt_function_params.apply_all_adapters(self)
        self._store_replacement_in_context()

    @staticmethod
    def is_function_publishable(options: LitgenOptions, cpp_function: CppFunctionDecl) -> bool:
        if code_utils.does_match_regex(options.fn_exclude_by_name__regex, cpp_function.function_name):
            return False
        elif len(options.srcml_options.functions_api_prefixes_list()) > 0 and options.fn_exclude_non_api:
            if not hasattr(cpp_function, "return_type"):
                return True
            has_api_prefix = False
            for api_prefix in options.srcml_options.functions_api_prefixes_list():
                if api_prefix in cpp_function.return_type.specifiers:
                    has_api_prefix = True
            return has_api_prefix
        else:
            return True

    # override
    def cpp_element(self) -> CppFunctionDecl:
        return cast(CppFunctionDecl, self._cpp_element)

    def shall_vectorize(self) -> bool:
        ns_name = self.cpp_element().cpp_scope(include_self=False).str_cpp()
        match_ns_name = code_utils.does_match_regex(self.options.fn_namespace_vectorize__regex, ns_name)
        match_fn_name = code_utils.does_match_regex(self.options.fn_vectorize__regex, self.cpp_element().function_name)
        r = match_ns_name and match_fn_name and not self.is_vectorize_impl
        return r

    def _store_replacement_in_context(self) -> None:
        return
        # the replacement below is too broad: should take the scope into account!
        # can_replace = True
        # if self.cpp_adapted_function.is_constructor() or self.cpp_adapted_function.is_method():
        #     can_replace = False
        # if can_replace:
        #     regex_replacement = RegexReplacement(
        #         rf"\b{self.cpp_adapted_function.function_name}\b", self.function_name_python()
        #     )
        #     self.lg_context.replacements_cache.store_replacement(regex_replacement)

    def is_method(self) -> bool:
        return self.cpp_element().is_method()

    def is_constructor(self) -> bool:
        r = self.cpp_element().is_constructor()
        return r

    def glue_override_virtual_methods_in_python(self, implemented_class: str) -> List[str]:
        assert self.cpp_element().is_virtual_method()

        template_code = code_utils.unindent_code(
            """
        {return_type} {function_name_cpp}({param_list}){maybe_const} override
        {
        {_i_}{PYBIND11_OVERRIDE_NAME}(
        {_i_}{_i_}{return_type}, // return type
        {_i_}{_i_}{implemented_class}, // parent class
        {_i_}{_i_}"{function_name_python}", // function name (python)
        {_i_}{_i_}{function_name_cpp}{maybe_comma_if_has_params} // function name (c++)
        {_i_}{_i_}{param_names} // params
        {_i_});
        }
        """,
            flag_strip_empty_lines=True,
        )

        parent_struct = self.cpp_element().parent_struct_if_method()
        has_params = len(self.cpp_element().parameter_list.parameters) > 0
        is_pure_virtual = self.cpp_element().is_pure_virtual
        assert parent_struct is not None

        replacements = Munch()
        replacements.PYBIND11_OVERRIDE_NAME = (
            "PYBIND11_OVERRIDE_PURE_NAME" if is_pure_virtual else "PYBIND11_OVERRIDE_NAME"
        )
        replacements._i_ = self.options.indent_cpp_spaces()
        replacements.return_type = self.cpp_element().return_type.str_return_type()
        replacements.function_name_cpp = self.cpp_element().function_name
        replacements.function_name_python = cpp_to_python.function_name_to_python(
            self.options, self.cpp_element().function_name
        )
        replacements.maybe_const = " const" if self.cpp_element().is_const() else ""
        replacements.implemented_class = implemented_class
        replacements.param_list = self.cpp_element().parameter_list.str_types_names_default_for_signature()
        replacements.maybe_comma_if_has_params = "," if has_params else ""

        lines_replacements = Munch()
        lines_replacements.param_names = (
            self.cpp_element().parameter_list.str_names_only_for_call() if has_params else None
        )

        code = code_utils.process_code_template(template_code, replacements, lines_replacements)
        lines = code.split("\n")
        return lines

    def function_name_python(self) -> str:
        from litgen.internal.adapted_types import operators

        if self.is_constructor():
            return "__init__"
        elif self.cpp_adapted_function.is_operator():
            r = operators.cpp_to_python_operator_name(self.cpp_adapted_function)
            return r
        else:
            r = cpp_to_python.function_name_to_python(self.options, self.cpp_adapted_function.function_name)
            return r

    def return_type_python(self) -> str:
        if self.cpp_element().is_inferred_return_type():
            return "Any"
        if self.is_constructor():
            return "None"
        else:
            return_type_cpp = self.cpp_adapted_function.str_full_return_type()
            return_type_python = cpp_to_python.type_to_python(self.options, return_type_cpp)
            return return_type_python

    def adapted_parameters(self) -> List[AdaptedParameter]:
        r: List[AdaptedParameter] = []
        for param in self.cpp_adapted_function.parameter_list.parameters:
            adapted_param = AdaptedParameter(self.lg_context, param)
            r.append(adapted_param)
        return r

    def _paramlist_call_python(self) -> List[str]:
        cpp_parameters = self.cpp_adapted_function.parameter_list.parameters
        r = []
        for param in cpp_parameters:
            param_name_python = cpp_to_python.var_name_to_python(self.options, param.decl.decl_name)
            param_type_cpp = param.decl.cpp_type.str_code()

            # Handle *args and **kwargs
            param_type_cpp_simplified = (
                param_type_cpp.replace("const ", "").replace("pybind11::", "py::").replace(" &", "")
            )
            if param_type_cpp_simplified == "py::args":
                r.append("*args")
                continue
            if param_type_cpp_simplified == "py::kwargs":
                r.append("**kwargs")
                continue

            param_type_python = cpp_to_python.type_to_python(self.options, param_type_cpp)
            if self.is_vectorize_impl:
                param_type_python = "np.ndarray"

            param_default_value = cpp_to_python.var_value_to_python(self.lg_context, param.default_value())

            param_code = f"{param_name_python}: {param_type_python}"
            if len(param_default_value) > 0:
                param_code += f" = {param_default_value}"

            r.append(param_code)

        if self.is_method() and not self.cpp_adapted_function.is_static_method():
            r = ["self"] + r
        return r

    #
    # _str_stub_lines()
    #
    # override
    def _str_stub_lines(self) -> List[str]:

        # Handle <=> (aka spaceship) operator, which is split in 5 operators!
        from litgen.internal.adapted_types import operators

        if operators.is_spaceship_operator(self):
            new_functions = operators.cpp_split_spaceship_operator(self)
            r = []
            for new_function in new_functions:
                r += new_function._str_stub_lines()
            return r

        if self.is_type_ignore:
            comment_python_type_ignore = "  # type: ignore"
        else:
            comment_python_type_ignore = ""

        # Fill a comment that will be written as an indication in the python stub
        comment_python_overridable = ""
        if self.cpp_element().is_virtual_method():
            parent_struct = self.cpp_element().parent_struct_if_method()
            assert parent_struct is not None
            is_overridable = code_utils.does_match_regex(
                self.options.class_override_virtual_methods_in_python__regex, parent_struct.class_name
            )
            if is_overridable:
                comment_python_overridable = " # overridable"
                if self.cpp_element().is_pure_virtual:
                    comment_python_overridable += " (pure virtual)"

        function_name_python = self.function_name_python()
        if self.is_vectorize_impl:
            function_name_python = (
                self.options.fn_vectorize_prefix + function_name_python + self.options.fn_vectorize_suffix
            )
        function_def_code = f"def {function_name_python}("

        return_code = f") -> {self.return_type_python()}:"
        if self.is_vectorize_impl:
            return_code = ") -> np.ndarray:"

        params_strs = self._paramlist_call_python()

        # Try to add function decl + all params and return type on the same line
        def function_name_and_params_on_one_line() -> Optional[str]:
            first_code_line_full = function_def_code
            first_code_line_full += ", ".join(params_strs)
            first_code_line_full += return_code
            first_code_line_full += comment_python_type_ignore + comment_python_overridable
            if (
                self.options.python_max_line_length <= 0
                or len(first_code_line_full) < self.options.python_max_line_length
            ):
                return first_code_line_full
            else:
                return None

        # Else put params one by line
        def function_name_and_params_line_by_line() -> List[str]:
            params_strs_comma = []
            for i, param_str in enumerate(params_strs):
                if i < len(params_strs) - 1:
                    params_strs_comma.append(param_str + ", ")
                else:
                    params_strs_comma.append(param_str)
            lines = (
                [function_def_code + comment_python_type_ignore + comment_python_overridable]
                + params_strs_comma
                + [return_code]
            )
            return lines

        all_on_one_line = function_name_and_params_on_one_line()

        title_lines = [all_on_one_line] if all_on_one_line is not None else function_name_and_params_line_by_line()
        body_lines: List[str] = []

        r = self._str_stub_layout_lines(title_lines, body_lines)
        r = self._cpp_original_code_lines() + r

        if self.cpp_adapted_function.is_static_method():
            r = ["# (static method)"] + r

        if self.shall_vectorize():
            new_vectorized_function = copy.copy(self)
            new_vectorized_function.is_vectorize_impl = True
            r += new_vectorized_function._str_stub_lines()

        return r

    #
    # _str_pydef_lines()
    #

    def _pydef_pyarg_list(self) -> List[str]:
        pyarg_strs: List[str] = []
        for param in self.cpp_adapted_function.parameter_list.parameters:
            adapted_decl = AdaptedDecl(self.lg_context, param.decl)

            # Skip *args and **kwarg
            param_type_cpp = adapted_decl.cpp_element().cpp_type.str_code()
            param_type_cpp_simplified = (
                param_type_cpp.replace("const ", "").replace("pybind11::", "py::").replace(" &", "")
            )
            if param_type_cpp_simplified in ["py::args", "py::kwargs"]:
                continue

            pyarg_str = adapted_decl._str_pydef_as_pyarg()
            pyarg_strs.append(pyarg_str)
        return pyarg_strs

    def _fill_is_type_ignore(self) -> None:
        token = "type: ignore"

        # Try to find it in eol comment (and clean eol comment if found)
        eol_comment = self.cpp_element().cpp_element_comments.comment_end_of_line
        if token in eol_comment:
            self.is_type_ignore = True
            eol_comment = eol_comment.replace(token, "").lstrip()
            if eol_comment.lstrip().startswith("//"):
                eol_comment = eol_comment.lstrip()[2:]
            self.cpp_element().cpp_element_comments.comment_end_of_line = eol_comment

    def _fill_return_value_policy(self) -> None:
        """Parses the return_value_policy from the function end of line comment
        For example:
            // A static instance (which python shall not delete, as enforced by the marker return_policy below)
            static Foo& Instance() { static Foo instance; return instance; }       // return_value_policy::reference
        """
        token = "return_value_policy::"

        # Try to find it in eol comment (and clean eol comment if found)
        eol_comment = self.cpp_element().cpp_element_comments.comment_end_of_line
        maybe_return_policy = code_utils.find_word_after_token(eol_comment, token)
        if maybe_return_policy is not None:
            self.return_value_policy = maybe_return_policy
            eol_comment = eol_comment.replace(token + self.return_value_policy, "").rstrip()
            if eol_comment.lstrip().startswith("//"):
                eol_comment = eol_comment.lstrip()[2:]
            self.cpp_element().cpp_element_comments.comment_end_of_line = eol_comment
        else:
            comment_on_previous_lines = self.cpp_element().cpp_element_comments.comment_on_previous_lines
            maybe_return_policy = code_utils.find_word_after_token(comment_on_previous_lines, token)
            if maybe_return_policy is not None:
                self.return_value_policy = maybe_return_policy
                comment_on_previous_lines = comment_on_previous_lines.replace(token + self.return_value_policy, "")
                self.cpp_element().cpp_element_comments.comment_on_previous_lines = comment_on_previous_lines

        # Finally add a comment
        if len(self.return_value_policy) > 0:
            comment_on_previous_lines = self.cpp_element().cpp_element_comments.comment_on_previous_lines
            if len(comment_on_previous_lines) > 0 and comment_on_previous_lines[-1] != "\n":
                comment_on_previous_lines += "\n"
            comment_on_previous_lines += f"return_value_policy::{self.return_value_policy}"
            self.cpp_element().cpp_element_comments.comment_on_previous_lines = comment_on_previous_lines

        # Take options.fn_force_return_policy_reference_for_pointers into account
        function_name = self.cpp_adapted_function.function_name
        options = self.options
        returns_pointer = self.cpp_element().returns_pointer()
        returns_reference = self.cpp_element().returns_reference()
        matches_regex_pointer = code_utils.does_match_regex(
            options.fn_return_force_policy_reference_for_pointers__regex, function_name
        )
        matches_regex_reference = code_utils.does_match_regex(
            options.fn_return_force_policy_reference_for_references__regex, function_name
        )

        if (matches_regex_pointer and returns_pointer) or (matches_regex_reference and returns_reference):
            self.return_value_policy = "reference"

    def _pydef_return_str(self) -> str:
        """Creates the return part of the pydef"""

        template_code = "{return_or_nothing}{self_prefix}{function_to_call}({params_call_inner})"

        return_or_nothing = "" if self.cpp_adapted_function.returns_void() else "return "
        self_prefix = "self." if (self.is_method() and self.lambda_to_call is None) else ""
        # fill function_to_call
        function_to_call = (
            self.lambda_to_call if self.lambda_to_call is not None else self.cpp_adapted_function.function_name
        )
        # Fill params_call_inner
        params_call_inner = self.cpp_adapted_function.parameter_list.str_names_only_for_call()

        code = code_utils.replace_in_string(
            template_code,
            {
                "return_or_nothing": return_or_nothing,
                "self_prefix": self_prefix,
                "function_to_call": function_to_call,
                "params_call_inner": params_call_inner,
            },
        )
        return code

    def _pydef_end_arg_docstring_returnpolicy(self) -> str:
        template_code = code_utils.unindent_code(
            """
            {_i_}{maybe_py_arg}{maybe_comma}
            {_i_}{maybe_docstring}{maybe_comma}
            {_i_}{maybe_return_value_policy}{maybe_comma}"""
        )[1:]

        # Standard replacements dict (r) and replacement dict with possible line removal (l)
        replace_tokens = Munch()
        replace_lines = Munch()

        # fill _i_
        replace_tokens._i_ = self.options.indent_cpp_spaces()

        # fill maybe_py_arg
        pyarg_codes = self._pydef_pyarg_list()
        if len(pyarg_codes) > 0:
            replace_lines.maybe_py_arg = ", ".join(pyarg_codes)
        else:
            replace_lines.maybe_py_arg = None

        # fill maybe_docstring
        comment = self.comment_pydef_one_line()
        if len(comment) == 0:
            replace_lines.maybe_docstring = None
        else:
            replace_lines.maybe_docstring = f'"{comment}"'

        # Fill maybe_return_value_policy
        return_value_policy = self.return_value_policy
        if len(return_value_policy) > 0:
            replace_lines.maybe_return_value_policy = f"pybind11::return_value_policy::{return_value_policy}"
        else:
            replace_lines.maybe_return_value_policy = None

        # Process template
        code = code_utils.process_code_template(
            input_string=template_code,
            replacements=replace_tokens,
            replacements_with_line_removal_if_not_found=replace_lines,
            flag_replace_maybe_comma=True,
        )

        code = code + ")"
        if not self.is_method():
            code = code + ";"

        return code

    def _pydef_method_creation_part(self) -> str:
        """Create the first code line of the pydef"""
        template_code = code_utils.unindent_code(
            """
            {module_or_class}.{def_maybe_static}("{function_name_python}",{location}
            """,
            flag_strip_empty_lines=True,
        )

        # Standard replacements dict (r) and replacement dict with possible line removal (l)
        replace_tokens = Munch()

        # fill module_or_class, function_name, location
        parent_cpp_module_var_name = cpp_to_python.cpp_scope_to_pybind_var_name(self.options, self.cpp_element())
        replace_tokens.module_or_class = "" if self.is_method() else parent_cpp_module_var_name
        if self.is_vectorize_impl:
            replace_tokens.function_name_python = (
                self.options.fn_vectorize_prefix + self.function_name_python() + self.options.fn_vectorize_suffix
            )
        else:
            replace_tokens.function_name_python = self.function_name_python()
        replace_tokens.location = self.info_original_location_cpp()
        replace_tokens.def_maybe_static = "def_static" if self.cpp_element().is_static() else "def"

        r = code_utils.process_code_template(template_code, replace_tokens)
        return r

    def _pydef_without_lambda_str_impl(self) -> str:
        """Create the full code of the pydef, with a direct call to the function or method"""
        template_code = code_utils.unindent_code(
            """
            {pydef_method_creation_part}
            {_i_}{function_pointer}{maybe_comma}{pydef_end_arg_docstring_returnpolicy}"""
        )[1:]

        # Standard replacements dict (r) and replacement dict with possible line removal (l)
        replace_tokens = Munch()
        replace_lines = Munch()

        # fill _i_
        replace_tokens._i_ = self.options.indent_cpp_spaces()

        replace_tokens.pydef_method_creation_part = self._pydef_method_creation_part()

        # fill function_pointer
        function_name = self.cpp_element().function_name
        function_parent_scope = self.cpp_element().cpp_scope(False).str_cpp_prefix()

        if self.is_vectorize_impl:
            replace_tokens.function_pointer = f"py::vectorize({function_parent_scope}{function_name})"
        else:
            replace_tokens.function_pointer = f"{function_parent_scope}{function_name}"

        if self.is_method():
            replace_tokens.function_pointer = "&" + replace_tokens.function_pointer

        if self.is_overloaded:
            overload_types = self.cpp_element().parameter_list.str_types_only_for_overload()
            replace_tokens.function_pointer = f"py::overload_cast<{overload_types}>({replace_tokens.function_pointer})"

        # fill pydef_end_arg_docstring_returnpolicy
        replace_tokens.pydef_end_arg_docstring_returnpolicy = self._pydef_end_arg_docstring_returnpolicy()

        # If pydef_end_arg_docstring_returnpolicy is multiline, add \n
        if "\n" in replace_tokens.pydef_end_arg_docstring_returnpolicy:
            replace_tokens.pydef_end_arg_docstring_returnpolicy = (
                "\n" + replace_tokens.pydef_end_arg_docstring_returnpolicy
            )
        else:
            replace_tokens.pydef_end_arg_docstring_returnpolicy = (
                replace_tokens.pydef_end_arg_docstring_returnpolicy.lstrip()
            )

        # Process template
        code = code_utils.process_code_template(
            input_string=template_code,
            replacements=replace_tokens,
            replacements_with_line_removal_if_not_found=replace_lines,
            flag_replace_maybe_comma=True,
        )

        return code

    def _pydef_with_lambda_str_impl(self) -> str:
        """Create the full code of the pydef, with an inner lambda"""

        template_code = code_utils.unindent_code(
            """
            {pydef_method_creation_part}
            {_i_}[]({params_call_with_self_if_method}){lambda_return_arrow}
            {_i_}{
            {_i_}{_i_}{lambda_adapter_code}
            {maybe_empty_line}
            {_i_}{_i_}{return_code};
            {_i_}}{maybe_close_paren_if_ctor}{maybe_comma}{pydef_end_arg_docstring_returnpolicy}"""
        )[1:]

        function_infos = self.cpp_adapted_function

        # Standard replacement dict (r) and replacement dict with possible line removal (l)
        replace_tokens = Munch()
        replace_lines = Munch()

        # fill _i_
        replace_tokens._i_ = self.options.indent_cpp_spaces()

        if self.is_constructor():
            replace_tokens.pydef_method_creation_part = ".def(py::init("
            replace_tokens.maybe_close_paren_if_ctor = ")"
        else:
            replace_tokens.pydef_method_creation_part = self._pydef_method_creation_part()
            replace_tokens.maybe_close_paren_if_ctor = ""

        # fill params_call_with_self_if_method
        _params_list = function_infos.parameter_list.list_types_names_default_for_signature()
        if self.is_method() and not self.is_constructor():
            _self_param = f"{self.cpp_element().cpp_scope(True).str_cpp()} & self"
            if function_infos.is_const():
                _self_param = "const " + _self_param
            _params_list = [_self_param] + _params_list
        replace_tokens.params_call_with_self_if_method = ", ".join(_params_list)

        # Fill lambda_return_arrow
        if self.cpp_adapted_function.returns_void():
            replace_tokens.lambda_return_arrow = ""
        else:
            full_return_type = self.cpp_adapted_function.str_full_return_type()
            replace_tokens.lambda_return_arrow = f" -> {full_return_type}"

        # fill return_code
        replace_tokens.return_code = self._pydef_return_str()

        # fill lambda_adapter_code
        replace_lines.lambda_adapter_code = self.cpp_adapter_code

        if replace_lines.lambda_adapter_code is not None:
            replace_lines.lambda_adapter_code = code_utils.indent_code(
                replace_lines.lambda_adapter_code,
                indent_str=self.options.indent_cpp_spaces() * 2,
                skip_first_line=True,
            )
            if replace_lines.lambda_adapter_code[-1] == "\n":
                replace_lines.lambda_adapter_code = replace_lines.lambda_adapter_code[:-1]

        # fill maybe_empty_line
        replace_lines.maybe_empty_line = "" if replace_lines.lambda_adapter_code is not None else None

        # fill pydef_end_arg_docstring_returnpolicy
        replace_tokens.pydef_end_arg_docstring_returnpolicy = self._pydef_end_arg_docstring_returnpolicy()
        # If pydef_end_arg_docstring_returnpolicy is multiline, add \n
        if "\n" in replace_tokens.pydef_end_arg_docstring_returnpolicy:
            replace_tokens.pydef_end_arg_docstring_returnpolicy = (
                "\n" + replace_tokens.pydef_end_arg_docstring_returnpolicy
            )

        # Process template
        code = code_utils.process_code_template(
            input_string=template_code,
            replacements=replace_tokens,
            replacements_with_line_removal_if_not_found=replace_lines,
            flag_replace_maybe_comma=True,
        )

        return code

    def _pydef_constructor_str(self) -> str:
        """
        A constructor decl look like this
            .def(py::init<ARG_TYPES_LIST>(),
            PY_ARG_LIST
            DOC_STRING);
        """

        template_code = code_utils.unindent_code(
            """
            .def(py::init<{arg_types}>(){maybe_comma}{location}
            {_i_}{maybe_pyarg}{maybe_comma}
            {_i_}{maybe_docstring}"""
        )[1:]

        function_infos = self.cpp_element()

        if "delete" in function_infos.specifiers:
            return ""

        _i_ = self.options.indent_cpp_spaces()

        arg_types = function_infos.parameter_list.str_types_only_for_overload()
        location = self.info_original_location_cpp()

        if len(self._pydef_pyarg_list()) > 0:
            maybe_pyarg = ", ".join(self._pydef_pyarg_list())
        else:
            maybe_pyarg = None

        if len(self.comment_pydef_one_line()) > 0:
            maybe_docstring = f'"{self.comment_pydef_one_line()}"'
        else:
            maybe_docstring = None

        # Apply simple replacements
        code = template_code
        code = code_utils.replace_in_string(
            code,
            {
                "_i_": _i_,
                "location": location,
                "arg_types": arg_types,
            },
        )

        # Apply replacements with possible line removal
        code = code_utils.replace_in_string_remove_line_if_none(
            code,
            {
                "maybe_docstring": maybe_docstring,
                "maybe_pyarg": maybe_pyarg,
            },
        )

        # Process maybe_comma
        code = code_utils.replace_maybe_comma(code)

        code = code_utils.add_item_before_cpp_comment(code, ")")

        return code

    def _pydef_flag_needs_lambda(self) -> bool:
        r = self.cpp_adapter_code is not None or self.lambda_to_call is not None
        return r

    # override
    def _str_pydef_lines(self) -> List[str]:

        # Handle <=> (aka spaceship) operator, which is split in 5 operators!
        from litgen.internal.adapted_types import operators

        if operators.is_spaceship_operator(self):
            new_functions = operators.cpp_split_spaceship_operator(self)
            r = []
            for new_function in new_functions:
                r += new_function._str_pydef_lines()
            return r

        if self.is_constructor():
            if self._pydef_flag_needs_lambda():
                code = self._pydef_with_lambda_str_impl()
            else:
                code = self._pydef_constructor_str()
        else:
            if self._pydef_flag_needs_lambda():
                code = self._pydef_with_lambda_str_impl()
            else:
                code = self._pydef_without_lambda_str_impl()

        lines = code.split("\n")

        if self.shall_vectorize():
            new_vectorized_function = copy.copy(self)
            new_vectorized_function.is_vectorize_impl = True
            lines += new_vectorized_function._str_pydef_lines()

        return lines

    def __str__(self) -> str:
        r = str(self.cpp_element())
        return r
