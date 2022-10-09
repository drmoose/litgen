"""
Types that will represent the AST parsed by srcML in an actionable way under python.

* `CppElement` is a wrapper around a srcLML xml node (it contains an exact copy of the original code)
* `CppElementAndComment` is a documented C++ element (with its comments on previous lines and at the end of line)

All elements are stored.

All declarations are stored in a corresponding object:
    * function -> CppFunction
     * struct -> CppStruct
    * enums -> CppEnum
    * etc.

Implementations (expressions, function calls, etc.) are stored as CppUnprocessed. It is still possible to retrieve their
original code.

See doc/srcml_cpp_doc.png
"""


from __future__ import annotations
import copy
import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Callable, Tuple, cast, Union
from xml.etree import ElementTree as ET  # noqa

from codemanip import code_utils

from srcmlcpp.cpp_scope import CppScope, CppScopePart, CppScopeType
from srcmlcpp.srcml_options import SrcmlOptions
from srcmlcpp.srcml_options import _int_from_str_or_named_number_macros
from srcmlcpp.srcml_xml_wrapper import SrcmlXmlWrapper

"""
"""
StringToIntDict = Dict[str, int]


class AccessTypes(Enum):
    public = "public"
    protected = "protected"
    private = "private"

    @staticmethod
    def from_name(name: str) -> AccessTypes:
        if name == "public" or name == "":
            return AccessTypes.public
        elif name == "protected":
            return AccessTypes.protected
        elif name == "private":
            return AccessTypes.private
        else:
            raise AssertionError()


@dataclass
class CppElementComments:
    """Gathers the C++ comments about functions, declarations, etc. : each CppElement can store
     comment on previous lines, and a single line comment next to its declaration.

    Lonely comments are stored as `CppComment`

     Example:
         `````cpp
         /*
         A multiline C comment
         about Foo1
         */
         void Foo1();

         // First line of comment on Foo2()
         // Second line of comment on Foo2()
         void Foo2();

         // A lonely comment

         //
         // Another lonely comment, on two lines
         // which ends on this second line, but has surrounding empty lines
         //

         // A comment on top of Foo3() & Foo4(), which should be kept as a standalone comment
         // since Foo3 and Foo4 have eol comments
         Void Foo3(); // Comment on end of line for Foo3()
         Void Foo4(); // Comment on end of line for Foo4()
         // A comment that shall not be grouped to the previous (which was an EOL comment for Foo4())
         ````
    """

    comment_on_previous_lines: str
    comment_end_of_line: str
    is_c_style_comment: bool  # Will be True if comment_on_previous_lines was a /* */ comment

    def __init__(self) -> None:
        self.comment_on_previous_lines = ""
        self.comment_end_of_line = ""
        self.is_c_style_comment = False

    def comment(self) -> str:
        if len(self.comment_on_previous_lines) > 0 and len(self.comment_end_of_line) > 0:
            return self.comment_on_previous_lines + "\n" + self.comment_end_of_line
        else:
            return self.comment_on_previous_lines + self.comment_end_of_line

    def top_comment_code(self, add_eol: bool = True, preserve_c_style_comment: bool = True) -> str:

        if preserve_c_style_comment and self.is_c_style_comment:
            r = "/*" + self.comment_on_previous_lines + "*/"
            return r

        top_comments = map(lambda comment: "//" + comment, self.comment_on_previous_lines.splitlines())
        top_comment = "\n".join(top_comments)
        if add_eol:
            if len(top_comment) > 0:
                if not top_comment.endswith("\n"):
                    top_comment += "\n"
        else:
            while top_comment.endswith("\n"):
                top_comment = top_comment[:-1]
        return top_comment

    def eol_comment_code(self) -> str:
        if len(self.comment_end_of_line) == 0:
            return ""
        else:
            if self.comment_end_of_line.startswith("//"):
                return self.comment_end_of_line
            else:
                return " //" + self.comment_end_of_line

    def add_eol_comment(self, comment: str) -> None:
        if len(self.comment_end_of_line) == 0:
            self.comment_end_of_line = comment
        else:
            self.comment_end_of_line += " - " + comment

    def full_comment(self) -> str:
        if len(self.comment_on_previous_lines) > 0 and len(self.comment_end_of_line) > 0:
            return self.comment_on_previous_lines + "\n\n" + self.comment_end_of_line
        else:
            return self.comment_on_previous_lines + self.comment_end_of_line


class CppElement(SrcmlXmlWrapper):
    """Base class of all the cpp types"""

    # the parent of this element (will be None for the root, which is a CppUnit)
    # at construction time, this field is absent (hasattr return False)!
    # It will be filled later by CppBlock.fill_parents() (with a tree traversal)
    parent: Optional[CppElement]

    # members that are always copied as shallow members (this is intentionally a static list)
    CppElement__deep_copy_force_shallow_ = ["parent"]

    def __init__(self, element: SrcmlXmlWrapper) -> None:
        super().__init__(element.options, element.srcml_xml, element.filename)
        # self.parent is intentionally not filled!

    def __deepcopy__(self, memo=None):
        """CppElement.__deepcopy__: force shallow copy of the parent
        This improves the performance a lot.
        Reason: when we deepcopy, we only intend to modify children.
        """

        # __deepcopy___ "manual":
        #   See https://stackoverflow.com/questions/1500718/how-to-override-the-copy-deepcopy-operations-for-a-python-object
        #   (Antony Hatchkins's answer here)

        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k not in CppElement.CppElement__deep_copy_force_shallow_:
                setattr(result, k, copy.deepcopy(v, memo))
            else:
                setattr(result, k, v)
        return result

    def str_code(self) -> str:
        """Returns a C++ textual representation of the contained code element.
        By default, it returns an exact copy of the original code.

        Derived classes override this implementation and str_code will return a string that differs
         a little from the original code, because it is based on information stored in these derived classes.
        """
        return self.str_code_verbatim()

    def depth(self) -> int:
        """The depth of this node, i.e how many parents it has"""
        depth = 0
        current = self
        if not hasattr(current, "parent"):
            return 0
        while current.parent is not None:
            depth += 1
            current = current.parent
        return depth

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        """Visits all the cpp children, and run the given function on them.
        Runs the visitor on this element first, then on its children

        This method is overriden in classes that have children!
        """
        # For an element without children, simply run the visitor
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)

    def short_cpp_element_info(self, include_scope: bool = True) -> str:
        r = type(self).__name__
        if self.has_name():
            r += f" name={self.name_code()}"
        if include_scope:
            scope_str = self.cpp_scope().str_cpp()
            if len(scope_str) > 0:
                r += f" scope={scope_str}"
        return r

    def cpp_scope(self, include_self: bool = False) -> CppScope:
        """Return this element cpp scope

        For example
        namespace Foo {
            struct S {
                void dummy();  // Will have a scope equal to ["Foo", "S"]
            }
        }
        """
        ancestors = self.ancestors_list(include_self)
        ancestors.reverse()

        scope = CppScope()
        for ancestor in ancestors:
            if isinstance(ancestor, CppStruct):  # this also tests for CppClass
                scope.scope_parts.append(CppScopePart(CppScopeType.ClassOrStruct, ancestor.class_name))
            elif isinstance(ancestor, CppNamespace):
                scope.scope_parts.append(CppScopePart(CppScopeType.Namespace, ancestor.ns_name))
            elif isinstance(ancestor, CppEnum):
                scope.scope_parts.append(CppScopePart(CppScopeType.Enum, ancestor.enum_name))

        return scope

    def ancestors_list(self, include_self: bool = False) -> List[CppElement]:
        """
        Returns the list of ancestors, up to the root unit

        This list does not include this element, and is in the order parent, grand-parent, grand-grand-parent, ...
        :return:
        """
        assert hasattr(self, "parent")  # parent should have been filled by parse_unit & CppBlock
        ancestors = []

        current_parent = self if include_self else self.parent
        while current_parent is not None:
            ancestors.append(current_parent)
            current_parent = current_parent.parent
        return ancestors

    def root_cpp_unit_parent(self) -> CppUnit:
        assert hasattr(self, "parent")  # parent should have been filled by parse_unit & CppBlock

        current = self
        while True:
            root = current
            if current.parent is None:
                break
            current = current.parent

        assert isinstance(root, CppUnit)
        return root

    def hierarchy_overview(self) -> str:
        log = ""

        def visitor_log_info(cpp_element: CppElement, event: CppElementsVisitorEvent, depth: int) -> None:
            nonlocal log
            if event == CppElementsVisitorEvent.OnElement:
                log += "  " * depth + cpp_element.short_cpp_element_info() + "\n"

        self.visit_cpp_breadth_first(visitor_log_info)
        return log

    def __str__(self) -> str:
        return self._str_simplified_yaml()


class CppElementsVisitorEvent(Enum):
    OnElement = 1  # We are visiting this element (will be raised for all elements, incl Blocks)
    OnBeforeChildren = 2  # We are about to visit a block's children
    OnAfterChildren = 3  # We finished visiting a block's children


# This defines the type of function that will visit all the Cpp Elements
# - First param: element being visited. A same element can be visited up to three times with different events
# - Second param: event (see CppElementsVisitorEvent doc)
# - Third param: depth in the source tree
CppElementsVisitorFunction = Callable[[CppElement, CppElementsVisitorEvent, int], None]


@dataclass
class CppElementAndComment(CppElement):
    """A CppElement to which we add comments"""

    cpp_element_comments: CppElementComments

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element)
        self.cpp_element_comments = cpp_element_comments

    def str_commented(self, is_enum: bool = False, is_decl_stmt: bool = False) -> str:
        result = self.cpp_element_comments.top_comment_code()
        result += self.str_code()
        if is_enum:
            result += ","
        if is_decl_stmt:
            result += ";"
        result += self.cpp_element_comments.eol_comment_code()
        return result

    def __str__(self) -> str:
        return self.str_commented()


@dataclass
class CppEmptyLine(CppElementAndComment):
    def __init__(self, element: SrcmlXmlWrapper) -> None:
        dummy_comments = CppElementComments()
        super().__init__(element, dummy_comments)

    def str_code(self) -> str:
        return ""

    def str_commented(self, is_enum: bool = False, is_decl_stmt: bool = False) -> str:
        return ""

    def __str__(self) -> str:
        return ""


class CppUnprocessed(CppElementAndComment):
    """Any Cpp Element that is not yet processed by srcmlcpp
    We keep its original source under the form of a string
    """

    code: str

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)
        self.code = ""

    def str_code(self) -> str:
        return f"<unprocessed_{self.tag()}/>"

    def __str__(self) -> str:
        return self.str_commented()


@dataclass
class CppBlock(CppElementAndComment):
    """The class CppBlock is a container that represents any set of code  detected by srcML.
    It has several derived classes.

     - For namespaces:
             Inside srcML we have this: <block>CODE</block>
             Inside python, the block is handled by `CppBlock`
     - For files (i.e "units"):
             Inside srcML we have this: <unit>CODE</unit>
             Inside python, the block is handled by `CppUnit` (which derives from `CppBlock`)
     - For functions and anonymous block:
             Inside srcML we have this:  <block><block_content>CODE</block_content></block>
             Inside python, the block is handled by `CppBlockContent` (which derives from `CppBlock`)
     - For classes and structs:
             Inside srcML we have this: <block><private or public>CODE</private or public></block>
             Inside python, the block is handled by `CppPublicProtectedPrivate` (which derives from `CppBlock`)

     https://www.srcml.org/doc/cpp_srcML.html#block
    """

    block_children: List[CppElementAndComment]

    def __init__(self, element: SrcmlXmlWrapper) -> None:
        dummy_cpp_comments = CppElementComments()
        super().__init__(element, dummy_cpp_comments)
        self.block_children: List[CppElementAndComment] = []

    def str_block(self, is_enum: bool = False) -> str:
        result = ""
        for i, child in enumerate(self.block_children):
            if i < len(self.block_children) - 1:
                child_str = child.str_commented(is_enum=is_enum)
            else:
                child_str = child.str_commented(is_enum=False)
            result += child_str
            if not child_str.endswith("\n"):
                result += "\n"
        return result

    def all_functions(self) -> List[CppFunctionDecl]:
        """Gathers all CppFunctionDecl and CppFunction in the children (non recursive)"""
        r: List[CppFunctionDecl] = []
        for child in self.block_children:
            if isinstance(child, CppFunctionDecl):
                r.append(child)
        return r

    def all_functions_with_name(self, name: str) -> List[CppFunctionDecl]:
        """Gathers all CppFunctionDecl and CppFunction matching a given name"""
        all_functions = self.all_functions()
        r: List[CppFunctionDecl] = []
        for fn in all_functions:
            if fn.function_name == name:
                r.append(fn)
        return r

    def all_structs_recursive(self) -> List[CppStruct]:
        """Gathers all CppStruct and CppClass in the children (*recursively*)"""
        r_ = self.all_cpp_elements_recursive(wanted_type=CppStruct)
        r = [cast(CppStruct, v) for v in r_]
        return r

    def find_struct_or_class(self, class_name_with_scope: str, current_scope: CppScope) -> Optional[CppStruct]:
        """Given a current scope, look for an existing matching class
        class_name_with_scope is a name that could include additional scopes
        """
        if "::" in class_name_with_scope:
            items = class_name_with_scope.split("::")
            class_name = items[-1]
            class_scope_str = "::".join(items[:-1])
        else:
            class_name = class_name_with_scope
            class_scope_str = ""

        all_structs = self.all_structs_recursive()
        for struct in all_structs:

            current_scope_str = current_scope.str_cpp()

            searched_scopes_strs = []
            searched_scopes_strs.append(class_scope_str)
            if len(current_scope_str) > 0:
                searched_scopes_strs.append(current_scope_str + "::" + class_scope_str)

            struct_scope_str = struct.cpp_scope(include_self=False).str_cpp()

            is_struct_visible_from_scope = False
            for searched_scope_str in searched_scopes_strs:
                if searched_scope_str.startswith(struct_scope_str):
                    is_struct_visible_from_scope = True

            is_name_equal = struct.class_name == class_name

            if is_name_equal and is_struct_visible_from_scope:
                return struct

        return None

    def all_functions_recursive(self) -> List[CppFunctionDecl]:
        """Gathers all CppFunctionDecl and CppFunction in the children (*recursive*)"""
        r_ = self.all_elements_of_type(wanted_type=CppFunctionDecl)
        r = [cast(CppFunctionDecl, v) for v in r_]
        return r

    def is_function_overloaded(self, function: CppFunctionDecl) -> bool:
        functions_same_name = self.all_functions_with_name(function.function_name)
        assert len(functions_same_name) >= 1
        is_overloaded = len(functions_same_name) >= 2
        return is_overloaded

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        """Visits all the cpp children, and run the given function on them.
        Runs the visitor on this block first, then on its children
        """
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        for child in self.block_children:
            child.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)

    def all_cpp_elements_recursive(self, wanted_type: Optional[type] = None) -> List[CppElement]:
        _all_cpp_elements = []

        def visitor_add_cpp_element(cpp_element: CppElement, event: CppElementsVisitorEvent, _depth: int) -> None:
            if event == CppElementsVisitorEvent.OnElement:
                if wanted_type is None or isinstance(cpp_element, wanted_type):
                    _all_cpp_elements.append(cpp_element)

        self.visit_cpp_breadth_first(visitor_add_cpp_element)
        return _all_cpp_elements

    def all_elements_of_type(self, wanted_type: type) -> List[CppElement]:
        return self.all_cpp_elements_recursive(wanted_type)

    def fill_children_parents(self) -> None:
        parents_stack: List[Optional[CppElement]] = [None]

        def visitor_fill_parent(cpp_element: CppElement, event: CppElementsVisitorEvent, _depth: int) -> None:
            nonlocal parents_stack
            if event == CppElementsVisitorEvent.OnElement:
                assert len(parents_stack) > 0

                last_parent = parents_stack[-1]
                if len(parents_stack) > 1:
                    assert last_parent is not None

                cpp_element.parent = last_parent
            elif event == CppElementsVisitorEvent.OnBeforeChildren:
                parents_stack.append(cpp_element)
            elif event == CppElementsVisitorEvent.OnAfterChildren:
                parents_stack.pop()

        self.visit_cpp_breadth_first(visitor_fill_parent)

    def __str__(self) -> str:
        return self.str_block()


@dataclass
class CppUnit(CppBlock):
    """A kind of block representing a full file."""

    def __init__(self, element: SrcmlXmlWrapper) -> None:
        super().__init__(element)

    def __str__(self) -> str:
        return self.str_block()


@dataclass
class CppBlockContent(CppBlock):
    """A kind of block used by function and anonymous blocks, where the code is inside <block><block_content>
    This can be viewed as a sub-block with a different name
    """

    def __init__(self, element: SrcmlXmlWrapper):
        super().__init__(element)

    def __str__(self) -> str:
        return self.str_block()


@dataclass
class CppPublicProtectedPrivate(CppBlock):  # Also a CppElementAndComment
    """A kind of block defined by a public/protected/private zone in a struct or in a class

    See https://www.srcml.org/doc/cpp_srcML.html#public-access-specifier
    Note: this is not a direct adaptation. Here we merge the different access types, and we derive from CppBlockContent
    """

    access_type: str = ""  # "public", "private", or "protected"
    default_or_explicit: str = ""  # "default" or "" ("default" means it was added automatically)

    def __init__(self, element: SrcmlXmlWrapper, access_type: str, default_or_explicit: Optional[str]) -> None:
        super().__init__(element)
        assert default_or_explicit in [None, "", "default"]
        assert access_type in ["public", "protected", "private"]
        self.access_type = access_type
        self.default_or_explicit = default_or_explicit if default_or_explicit is not None else ""

    def str_public_protected_private(self) -> str:
        r = ""

        r += f"{self.access_type}" + ":"
        if self.default_or_explicit == "default":
            r += "// <default_access_type/>"
        r += "\n"

        r += code_utils.indent_code(self.str_block(), 4)
        return r

    def str_code(self) -> str:
        return self.str_public_protected_private()

    def str_commented(self, is_enum: bool = False, is_decl_stmt: bool = False) -> str:  # noqa
        return self.str_code()

    def __str__(self) -> str:
        return self.str_public_protected_private()


@dataclass
class CppType(CppElement):
    """
    Describes a full C++ type, as seen by srcML
    See https://www.srcml.org/doc/cpp_srcML.html#type

    A type name can be composed of several names, for example:

        "unsigned int" -> ["unsigned", "int"]

        MY_API void Process() declares a function whose return type will be ["MY_API", "void"]
                             (where "MY_API" could for example be a dll export/import macro)

    Note about composed types:
        For composed types, like `std::map<int, std::string>` srcML returns a full tree.
        In order to simplify the process, we recompose this kind of type names into a simple string
    """

    # The field typenames can be:
    #   - simple: ["int"]
    #   - composed of several names, for example: ["unsigned", "long", "long"]
    #   - ["auto"] for inferred types
    #   - ["std::vector<int>"] for complex types (for example)
    typenames: List[str]

    # specifiers: a list of possible specifiers
    # Acceptable specifiers: const, inline, virtual, extern, constexpr, etc.
    #
    # Important:
    # if you filled SrcmlOptions.functions_api_prefixes, then those prefixes will be mentioned
    #  as specifiers for the return type of the functions.
    specifiers: List[str]

    # modifiers: could be ["*"], ["&&"], ["&"], ["*", "*"], ["..."]
    modifiers: List[str]

    # template arguments types i.e ["int"] for vector<int>
    # (this will not be filled: see note about composed types)
    # argument_list: List[str]

    def __init__(self, element: SrcmlXmlWrapper) -> None:
        super().__init__(element)
        self.typenames: List[str] = []
        self.specifiers: List[str] = []
        self.modifiers: List[str] = []

    @staticmethod
    def authorized_modifiers() -> List[str]:
        return ["*", "&", "&&", "..."]

    def str_return_type(self, remove_api_prefix: bool = True) -> str:
        # Remove unwanted specifiers
        # Possible specifiers : "const" "inline" "static" "virtual" "extern" "constexpr"
        # "inline", "virtual", "extern" and "static" do not change the return type
        specifiers = copy.copy(self.specifiers)
        unwanted_specifiers = ["inline", "virtual", "extern", "static"]
        for unwanted_specifier in unwanted_specifiers:
            if unwanted_specifier in self.specifiers:
                specifiers.remove(unwanted_specifier)
        specifiers_str = code_utils.join_remove_empty(" ", specifiers)

        # Handle const
        nb_const = self.specifiers.count("const")
        assert nb_const <= 1

        # Handle typenames with possible auto
        if len(self.typenames) > 1 and self.typenames[0] == "auto":
            name = " ".join(self.typenames[1:])
        else:
            name = " ".join(self.typenames)

        modifiers_str = code_utils.join_remove_empty(" ", self.modifiers)
        strs = [specifiers_str, name, modifiers_str]
        return_type_str = code_utils.join_remove_empty(" ", strs)

        if remove_api_prefix:
            for api_prefix in self.options.functions_api_prefixes_list():
                if return_type_str.startswith(api_prefix):
                    return_type_str = return_type_str[len(api_prefix) :].lstrip()

        return return_type_str

    def str_code(self) -> str:
        nb_const = self.specifiers.count("const")

        if nb_const > 2:
            raise ValueError("I cannot handle more than two `const` occurrences in a type!")

        specifiers = copy.copy(self.specifiers)
        if nb_const == 2:
            # remove the last const and handle it later
            specifier_r: List[str] = list(reversed(specifiers))
            specifier_r.remove("const")
            specifiers = list(reversed(specifier_r))

        specifiers_str = code_utils.join_remove_empty(" ", specifiers)
        modifiers_str = code_utils.join_remove_empty(" ", self.modifiers)

        name = " ".join(self.typenames)

        name_and_arg = name
        strs = [specifiers_str, name_and_arg, modifiers_str]
        r = code_utils.join_remove_empty(" ", strs)

        if nb_const == 2:
            r += " const"

        return r

    def name_without_modifier_specifier(self) -> str:
        name = " ".join(self.typenames)
        return name

    def is_const(self) -> bool:
        return "const" in self.specifiers

    def is_static(self) -> bool:
        return "static" in self.specifiers

    def is_raw_pointer(self) -> bool:
        return "*" in self.modifiers

    def is_void(self) -> bool:
        return self.typenames == ["void"] and len(self.specifiers) == 0

    def is_inferred_type(self) -> bool:
        return self.typenames == ["auto"]

    def with_instantiated_template(self, template_specs: TemplateInstantiation) -> Optional[CppType]:
        """Returns a new type where "template_name" is replaced by "cpp_type"
        Returns None if this type does not use "template_name"
        """
        was_changed = False
        new_type = copy.deepcopy(self)
        for i in range(len(new_type.typenames)):
            for template_spec in template_specs.instantiations:
                assert len(template_spec.cpp_type.typenames) == 1
                template_spec_type = template_spec.cpp_type.typenames[0]
                if new_type.typenames[i] == template_spec.template_name:
                    was_changed = True
                    new_type.typenames[i] = template_spec_type
                    new_type.specifiers += template_spec.cpp_type.specifiers
                    new_type.modifiers += template_spec.cpp_type.modifiers
                else:
                    new_typename, nb_sub = re.subn(
                        rf"\b{template_spec.template_name}\b", template_spec_type, new_type.typenames[i]
                    )
                    if nb_sub > 0:
                        was_changed = True
                        new_type.typenames[i] = new_typename
                        new_type.specifiers += template_spec.cpp_type.specifiers
                        new_type.modifiers += template_spec.cpp_type.modifiers

        if was_changed:
            return new_type
        else:
            return None

    def __str__(self) -> str:
        return self.str_code()


@dataclass
class CppDecl(CppElementAndComment):
    """
    https://www.srcml.org/doc/cpp_srcML.html#variable-declaration
    """

    cpp_type: CppType

    # decl_name, i.e. the variable name
    decl_name: str = ""

    # c_array_code will only be filled if this decl looks like:
    #   *  `int a[]:`      <-- in this case, c_array_code="[]"
    #   or
    #   *  `int a[10]:`      <-- in this case, c_array_code="[10]"
    #
    # In other cases, it will be an empty string
    c_array_code: str = ""

    # * init represent the initial aka default value.
    # With srcML, it is inside an <init><expr> node in srcML.
    # Here we retransform it to C++ code for simplicity
    #
    #     For example:
    #     int a = 5;
    #
    #     leads to:
    #         <decl_stmt>
    #             <decl>
    #                 <type> <name>int</name> </type>
    #                 <name>a</name>
    #                 <init>= <expr> <literal type="number">5</literal> </expr> </init>
    #             </decl>;
    #         </decl_stmt>
    #
    # And `<init>= <expr> <literal type="number">5</literal> </expr> </init>` is transcribed as "5"
    initial_value_code: str = ""  # initial or default value

    bitfield_range: str = ""  # Will be filled for bitfield members

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)

    def str_code(self) -> str:
        r = ""
        if hasattr(self, "cpp_type"):
            r += str(self.cpp_type) + " "
        r += self.decl_name + self.c_array_code
        if len(self.initial_value_code) > 0:
            r += " = " + self.initial_value_code
        return r

    def type_name_default_for_signature(self) -> str:
        r = ""
        if hasattr(self, "cpp_type"):
            r += str(self.cpp_type) + " "
        r += self.decl_name + self.c_array_code
        if len(self.initial_value_code) > 0:
            r += " = " + self.initial_value_code
        return r

    def has_name_or_ellipsis(self) -> bool:
        assert self.decl_name is not None
        if len(self.decl_name) > 0:
            return True
        elif "..." in self.cpp_type.modifiers:
            return True
        return False

    def __str__(self) -> str:
        r = self.str_commented()
        return r

    def is_c_string_list_ptr(self) -> bool:
        """
        Returns true if this decl looks like a const C string double pointer.
        Examples:
            const char * const items[]
            const char ** const items
            const char ** items
        :return:
        """
        is_const = "const" in self.cpp_type.specifiers
        is_char = self.cpp_type.typenames == ["char"]
        is_default_init = (
            self.initial_value_code == "" or self.initial_value_code == "NULL" or self.initial_value_code == "nullptr"
        )

        nb_indirections = 0
        nb_indirections += self.cpp_type.modifiers.count("*")
        if len(self.c_array_code) > 0:
            nb_indirections += 1

        r = is_const and is_char and nb_indirections == 2 and is_default_init
        return r

    def is_bitfield(self) -> bool:
        return len(self.bitfield_range) > 0

    def is_c_array(self) -> bool:
        """
        Returns true if this decl is a C style array, e.g.
            int v[4]
        or
            int v[]
        """
        return len(self.c_array_code) > 0

    def c_array_size_as_str(self) -> Optional[str]:
        """
        If this decl is a c array, return its size, e.g.
            * for `int v[COUNT]` it will return "COUNT"
            * for `int v[]` it will return ""
        """
        if not self.is_c_array():
            return None
        pos = self.c_array_code.index("[")
        size_str = self.c_array_code[pos + 1 : -1]
        return size_str

    def c_array_size_as_int(self) -> Optional[int]:
        """
        If this decl is a c array, return its size, e.g. for
            int v[4]
        It will return 4

        However, it might return None for
            int v[COUNT];
        where COUNT is a macro or constexpr value

        (but you can fill SrcmlOptions.named_number_macros to circumvent this)
        """
        size_as_str = self.c_array_size_as_str()
        maybe_size = _int_from_str_or_named_number_macros(self.options, size_as_str)
        return maybe_size

    def is_c_array_known_fixed_size(self) -> bool:
        """Returns true if this decl is a c array, and has a fixed size which we can interpret
        either via the code, or through size_dict
        """
        return self.c_array_size_as_int() is not None

    def is_c_array_no_size(self, options: SrcmlOptions) -> bool:
        """Returns true if this decl is a c array, and has a no fixed size, e.g.
        int a[];
        """
        is_array = self.is_c_array()
        if not is_array:
            return False
        size_str = self.c_array_size_as_str()
        assert size_str is not None
        has_size = len(size_str.strip()) > 0
        return is_array and not has_size

    def is_c_array_fixed_size_unparsable(self) -> bool:
        is_array = self.is_c_array()
        if not is_array:
            return False

        size_str = self.c_array_size_as_str()
        assert size_str is not None
        has_size = len(size_str.strip()) > 0
        array_size_as_int = self.c_array_size_as_int()
        r = is_array and has_size and (array_size_as_int is None)
        return r

    def is_const(self) -> bool:
        """
        Returns true if this decl is const"""
        return "const" in self.cpp_type.specifiers  # or "const" in self.cpp_type.names

    def with_instantiated_template(self, template_specs: TemplateInstantiation) -> Optional[CppDecl]:
        """Returns a new decl where "template_name" is replaced by "cpp_type"
        Returns None if this decl does not use "template_name"
        """
        new_type = self.cpp_type.with_instantiated_template(template_specs)
        if new_type is None:
            return None
        else:
            new_decl = copy.deepcopy(self)
            new_decl.cpp_type = new_type
            return new_decl

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        if hasattr(self, "cpp_type"):
            self.cpp_type.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)


@dataclass
class CppDeclStatement(CppElementAndComment):
    """
    https://www.srcml.org/doc/cpp_srcML.html#variable-declaration-statement
    """

    cpp_decls: List[CppDecl]  # A CppDeclStatement can initialize several variables

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)
        self.cpp_decls: List[CppDecl] = []

    def str_code(self) -> str:
        str_decls = list(
            map(
                lambda cpp_decl: cpp_decl.str_commented(is_decl_stmt=True),
                self.cpp_decls,
            )
        )
        str_decl = code_utils.join_remove_empty("\n", str_decls)
        return str_decl

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        for child in self.cpp_decls:
            child.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)

    def with_instantiated_template(self, template_specs: TemplateInstantiation) -> Optional[CppDeclStatement]:
        """Returns a new CppDeclStatement where "template_name" is replaced by "cpp_type"
        Returns None if this CppDeclStatement does not use "template_name"
        """
        was_changed = False

        new_decl_statement = copy.deepcopy(self)
        new_cpp_decls: List[CppDecl] = []
        for cpp_decl in new_decl_statement.cpp_decls:
            new_cpp_decl = cpp_decl.with_instantiated_template(template_specs)
            if new_cpp_decl is not None:
                was_changed = True
                new_cpp_decls.append(new_cpp_decl)
            else:
                new_cpp_decls.append(cpp_decl)

        if not was_changed:
            return None
        else:
            new_decl_statement.cpp_decls = new_cpp_decls
            return new_decl_statement

    def __str__(self) -> str:
        return self.str_commented()


@dataclass
class CppParameter(CppElementAndComment):
    """
    https://www.srcml.org/doc/cpp_srcML.html#function-declaration
    """

    decl: CppDecl
    template_type: str  # This is only for template's CppParameterList (will be "typename" or "class")
    template_name: str = ""  # This is only for template's CppParameterList (name of the template type, e.g. "T")

    def __init__(self, element: SrcmlXmlWrapper) -> None:
        dummy_cpp_element_comments = CppElementComments()
        super().__init__(element, dummy_cpp_element_comments)

    def type_name_default_for_signature(self) -> str:
        assert hasattr(self, "decl")
        r = self.decl.type_name_default_for_signature()
        return r

    def str_code(self) -> str:
        if hasattr(self, "decl"):
            assert not hasattr(self, "template_type")
            return str(self.decl)
        else:
            if not hasattr(self, "template_type"):
                logging.warning("CppParameter.__str__() with no decl and no template_type")
            return str(self.template_type) + " " + self.template_name

    def str_template_type(self) -> str:
        assert hasattr(self, "template_type")
        r = str(self.template_type) + " " + self.template_name
        return r

    def is_template_param(self) -> bool:
        r = hasattr(self, "template_type")
        return r

    def __str__(self) -> str:
        return self.str_code()

    def full_type(self) -> str:
        r = self.decl.cpp_type.str_code()
        return r

    def has_default_value(self) -> bool:
        return len(self.decl.initial_value_code) > 0

    def default_value(self) -> str:
        return self.decl.initial_value_code

    def variable_name(self) -> str:
        return self.decl.decl_name

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)

        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        if hasattr(self, "decl"):
            self.decl.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)


@dataclass
class CppParameterList(CppElement):
    """
    List of parameters of a function
    https://www.srcml.org/doc/cpp_srcML.html#function-declaration
    """

    parameters: List[CppParameter]

    def __init__(self, element: SrcmlXmlWrapper) -> None:
        super().__init__(element)
        self.parameters = []

    def list_types_names_only(self) -> List[str]:
        """Returns a list like ["int", "bool"]"""
        r = []
        for parameter in self.parameters:
            r.append(parameter.decl.cpp_type.str_code())
        return r

    def str_types_names_only(self) -> str:
        return ", ".join(self.list_types_names_only())

    def list_types_names_default_for_signature(self) -> List[str]:
        """Returns a list like ["int a", "bool flag = true"]"""
        params_strs = list(map(lambda param: param.type_name_default_for_signature(), self.parameters))
        return params_strs

    def str_types_names_default_for_signature(self) -> str:
        """Returns a string like "int a, bool flag = true" """
        params_strs = self.list_types_names_default_for_signature()
        params_str = ", ".join(params_strs)
        return params_str

    def str_code(self) -> str:
        return self.str_types_names_default_for_signature()

    def str_names_only_for_call(self) -> str:
        names = [param.variable_name() for param in self.parameters]
        r = ", ".join(names)
        return r

    def str_types_only_for_overload(self) -> str:
        def type_with_star_for_array(param: CppParameter) -> str:
            type_str = param.decl.cpp_type.str_code()
            if param.decl.c_array_code.startswith("["):
                type_str += " *"
            return type_str

        types = [type_with_star_for_array(param) for param in self.parameters]
        r = ", ".join(types)
        return r

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        for child in self.parameters:
            child.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)

    def __str__(self) -> str:
        return self.str_code()


@dataclass
class CppTemplate(CppElement):
    """
    Template parameters of a function, struct or class
    https://www.srcml.org/doc/cpp_srcML.html#template
    """

    parameter_list: CppParameterList

    def __init__(self, element: SrcmlXmlWrapper) -> None:
        super().__init__(element)
        self.parameter_list = CppParameterList(element)

    def str_code(self) -> str:
        typelist = [param.str_template_type() for param in self.parameter_list.parameters]
        typelist_str = ", ".join(typelist)
        params_str = f"template<{typelist_str}> "
        return params_str

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        if hasattr(self, "parameter_list"):
            self.parameter_list.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)

    def __str__(self) -> str:
        return self.str_code()


class TemplateInstantiationPart:
    cpp_type: CppType
    template_name: str = ""  # If empty, will be applied to the first available template param

    def __init__(self, cpp_type: Union[CppType, str], template_name: str = ""):
        if isinstance(cpp_type, CppType):
            self.cpp_type = cpp_type
        elif isinstance(cpp_type, str):
            from srcmlcpp import srcmlcpp_main
            from srcmlcpp.srcml_options import SrcmlOptions

            dummy_options = SrcmlOptions()
            self.cpp_type = srcmlcpp_main.code_to_cpp_type(dummy_options, cpp_type)
            self.template_name = template_name

        # We do not support type composed of multiple word here, such as "unsigned int".
        # Please use "uint" or other typedefs.
        assert len(self.cpp_type.typenames) == 1

    def __str__(self):
        if len(self.template_name) > 0:
            return f"{self.template_name} -> {str(self.cpp_type)}"
        else:
            return str(self.cpp_type)


class TemplateInstantiation:
    instantiations: List[TemplateInstantiationPart]

    def __init__(self, check_private_constructor: str):
        if check_private_constructor != "from_within":
            raise Exception("Please use named constructors, this constructor is private!")

    @staticmethod
    def from_type_str(cpp_type_str: str, template_name: str = "") -> TemplateInstantiation:
        r = TemplateInstantiation("from_within")
        r.instantiations = [TemplateInstantiationPart(cpp_type_str, template_name)]
        return r

    @staticmethod
    def from_type(cpp_type: CppType, template_name: str = "") -> TemplateInstantiation:
        r = TemplateInstantiation("from_within")
        r.instantiations = [TemplateInstantiationPart(cpp_type, template_name)]
        return r

    @staticmethod
    def from_instantiations(instantiations: List[TemplateInstantiationPart]) -> TemplateInstantiation:
        r = TemplateInstantiation("from_within")
        r.instantiations = instantiations
        return r


class ICppTemplateHost:
    """
    Interface added to templatable classes: CppStruct (+CppClass) and CppFunctionDecl (+CppFunction)
    """

    template: CppTemplate
    instantiated_template_params: List[CppType]  # Will only be filled after calling with_instantiated_template

    def __init__(self, _element: SrcmlXmlWrapper, _cpp_element_comments: CppElementComments) -> None:
        self._init_template_host()

    def _init_template_host(self) -> None:
        # self.template is not set by default
        self.instantiated_template_params = []

    def is_template(self) -> bool:
        return hasattr(self, "template")

    def is_template_non_specialized(self) -> bool:
        return hasattr(self, "template") and not self.is_fully_specialized_template()

    def is_fully_specialized_template(self) -> bool:
        if not self.is_template():
            return False
        nb_params = len(self.template.parameter_list.parameters)
        nb_inst = len(self.instantiated_template_params)
        return nb_inst == nb_params

    def str_instantiated_params(self) -> str:
        return ", ".join([str(param) for param in self.instantiated_template_params])

    def _instantiation_str(self) -> str:
        if len(self.instantiated_template_params) > 0:
            return f"<{self.str_instantiated_params()}>"
        else:
            return ""

    def _store_template_specs(self, template_specs: TemplateInstantiation) -> None:
        for template_spec in template_specs.instantiations:
            if len(template_spec.template_name) == 0:
                assert self.is_template()
                nb_remaining_template_to_instantiate = len(self.template.parameter_list.parameters) - len(
                    self.instantiated_template_params
                )
                assert nb_remaining_template_to_instantiate > 0
                idx_template = len(self.instantiated_template_params)
                template_spec.template_name = self.template.parameter_list.parameters[idx_template].template_name
                self.instantiated_template_params.append(template_spec.cpp_type)

    def str_template(self) -> str:
        if not hasattr(self, "template"):
            return ""
        if len(self.template.parameter_list.parameters) == 0:
            return ""

        template_params_strs = []
        for i in range(len(self.template.parameter_list.parameters)):
            template_parameter = self.template.parameter_list.parameters[i]
            template_type_and_name = template_parameter.template_type + " " + template_parameter.template_name
            if i < len(self.instantiated_template_params):
                template_instantiation = self.instantiated_template_params[i]
                template_params_strs.append(f"{template_type_and_name}={template_instantiation}")
            else:
                template_params_strs.append(template_type_and_name)

        template_params_str = ", ".join(template_params_strs)

        if len(self.instantiated_template_params) == 0:
            r = f"template<{template_params_str}> "
        else:
            if isinstance(self, CppFunctionDecl):
                r = f"template</*{template_params_str}*/> "
            elif isinstance(self, CppStruct):
                r = f"/*template<{template_params_str}>*/ "

        return r


@dataclass
class CppFunctionDecl(CppElementAndComment, ICppTemplateHost):
    """
    https://www.srcml.org/doc/cpp_srcML.html#function-declaration
    """

    specifiers: List[str]  # "const" or ""

    # warning: return_type may include API and inline markers i.e for
    #       MY_API inline int foo()
    # then return_type = "MY_API inline int"
    #
    # Use full_return_type() to get a return type without those.
    return_type: CppType

    parameter_list: CppParameterList
    function_name: str
    is_pure_virtual: bool

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)
        self._init_template_host()
        self.specifiers: List[str] = []
        self.is_pure_virtual = False
        self.function_name = ""

    def qualified_function_name(self) -> str:
        parent_scope = self.cpp_scope(False).str_cpp()
        if len(parent_scope) == 0:
            return self.function_name
        else:
            return parent_scope + "::" + self.function_name

    def qualified_function_name_with_instantiation(self) -> str:
        return self.qualified_function_name() + self._instantiation_str()

    def function_name_with_instantiation(self) -> str:
        return self.function_name + self._instantiation_str()

    def with_instantiated_template(self, template_specs: TemplateInstantiation) -> Optional[CppFunctionDecl]:
        """Returns a new non-templated function, implemented for the given type
        Only works on templated function with *one* template parameter
        """
        new_function = copy.deepcopy(self)
        new_function._store_template_specs(template_specs)

        was_changed = False

        new_return_type = new_function.return_type.with_instantiated_template(template_specs)
        if new_return_type is not None:
            was_changed = True
            new_function.return_type = new_return_type

        new_parameters: List[CppParameter] = []
        for parameter in new_function.parameter_list.parameters:
            new_decl = parameter.decl.with_instantiated_template(template_specs)
            if new_decl is not None:
                new_parameter = copy.deepcopy(parameter)
                new_parameter.decl = new_decl
                new_parameters.append(new_parameter)
                was_changed = True
            else:
                new_parameters.append(parameter)

        new_function.parameter_list.parameters = new_parameters

        if was_changed:
            return new_function
        else:
            return None

    def is_inferred_return_type(self) -> bool:
        if not hasattr(self, "return_type"):
            return False
        return "auto" in self.return_type.specifiers and len(self.return_type.typenames) == 0

    def is_arrow_notation_return_type(self) -> bool:
        if self.is_inferred_return_type():
            return False
        elif len(self.return_type.typenames) == 0:
            return False
        else:
            first_typename = self.return_type.typenames[0]
            return first_typename == "auto"

    def _str_signature(self) -> str:
        r = ""

        r += self.str_template()

        if self.is_arrow_notation_return_type():
            if self.return_type.str_return_type() == "auto":
                r += f"auto {self.function_name}{self._instantiation_str()}({self.parameter_list})"
            else:
                r += f"auto {self.function_name}{self._instantiation_str()}({self.parameter_list}) -> {self.return_type.str_return_type()}"
        else:
            r += f"{self.return_type.str_return_type()} {self.function_name}{self._instantiation_str()}({self.parameter_list})"

        if len(self.specifiers) > 0:
            specifiers_strs = map(str, self.specifiers)
            r = r + " ".join(specifiers_strs)

        return r

    # def is_auto_decl(self):
    #     self.return_type.typenames[0]

    def str_code(self) -> str:
        r = self._str_signature() + ";"
        return r

    def str_full_return_type(self) -> str:
        """The C++ return type of the function, without API, virtual or inline specifiers"""
        r = self.return_type.str_return_type()
        for prefix in self.options.functions_api_prefixes_list():
            r = r.replace(prefix + " ", "")
        return r

    def is_const(self) -> bool:
        return "const" in self.specifiers

    def is_method(self) -> bool:
        assert hasattr(self, "parent")
        is_method = isinstance(self.parent, CppPublicProtectedPrivate)
        return is_method

    def method_access_type(self) -> str:
        """
        Returns "public", "private", or "protected"
        Will throw if this is not a method!
        """
        assert self.is_method()
        assert hasattr(self, "parent")
        assert isinstance(self.parent, CppPublicProtectedPrivate)
        access_type = self.parent.access_type
        return access_type

    def is_virtual_method(self) -> bool:
        if not self.is_method():
            return False
        if not hasattr(self, "return_type"):
            return False
        is_virtual = "virtual" in self.return_type.specifiers
        return is_virtual

    def is_overloaded_method(self) -> bool:
        if not self.is_method():
            return False
        parent_struct = self.parent_struct_if_method()
        assert parent_struct is not None
        methods_same_name = parent_struct.all_methods_with_name(self.function_name)
        assert len(methods_same_name) >= 1
        is_overloaded = len(methods_same_name) >= 2
        return is_overloaded

    def parent_struct_if_method(self) -> Optional[CppStruct]:
        assert hasattr(self, "parent")
        if not self.is_method():
            return None
        """
        The inner hierarchy of a struct resembles this:
              CppStruct name=MyStruct
                CppBlock scope=MyStruct
                  CppPublicProtectedPrivate scope=MyStruct
                    CppFunctionDecl name=foo scope=MyStruct
                      CppType name=void scope=MyStruct
                      CppParameterList scope=MyStruct
                        ...
        """
        assert self.parent is not None
        assert self.parent.parent is not None
        parent_block = self.parent.parent
        assert isinstance(parent_block, CppBlock)
        parent_struct_ = parent_block.parent
        assert isinstance(parent_struct_, CppStruct)
        return parent_struct_

    def parent_struct_name_if_method(self) -> Optional[str]:
        parent_struct = self.parent_struct_if_method()
        if parent_struct is None:
            return None
        else:
            return parent_struct.class_name

    def is_constructor(self) -> bool:
        parent_struct_name = self.parent_struct_name_if_method()
        if parent_struct_name is None:
            return False
        r = self.function_name == parent_struct_name
        return r

    def is_operator(self) -> bool:
        return self.function_name.startswith("operator")

    def operator_name(self) -> str:
        assert self.is_operator()
        r = self.function_name[len("operator") :]
        return r

    def returns_pointer(self) -> bool:
        r = hasattr(self, "return_type") and self.return_type.modifiers == ["*"]
        return r

    def returns_reference(self) -> bool:
        r = hasattr(self, "return_type") and self.return_type.modifiers == ["&"]
        return r

    def returns_void(self) -> bool:
        return self.str_full_return_type() == "void"

    def is_static(self) -> bool:
        if not hasattr(self, "return_type"):
            return False
        return "static" in self.return_type.specifiers

    def is_static_method(self) -> bool:
        return self.is_method() and self.is_static()

    def __str__(self) -> str:
        return self.str_commented()

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        if hasattr(self, "return_type"):
            self.return_type.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        if hasattr(self, "parameter_list"):
            self.parameter_list.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        if hasattr(self, "template"):
            self.template.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)


@dataclass
class CppFunction(CppFunctionDecl):
    """
    https://www.srcml.org/doc/cpp_srcML.html#function-definition
    """

    block: CppUnprocessed

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)

    def str_code(self) -> str:
        r = self._str_signature()
        if hasattr(self, "block"):
            r += str(self.block)
        return r

    def __str__(self) -> str:
        r = ""
        if len(self.cpp_element_comments.top_comment_code()) > 0:
            r += self.cpp_element_comments.top_comment_code()
        r += self._str_signature() + self.cpp_element_comments.eol_comment_code()
        r += "\n" + str(self.block) + "\n"
        return r

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        if hasattr(self, "block"):
            cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
            self.block.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
            cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)


@dataclass
class CppConstructorDecl(CppFunctionDecl):
    """
    https://www.srcml.org/doc/cpp_srcML.html#constructor-declaration
    """

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)
        self.specifiers: List[str] = []
        self.function_name = ""

    def _str_signature(self) -> str:
        r = f"{self.function_name}({self.parameter_list})"
        if len(self.specifiers) > 0:
            specifiers_strs = map(str, self.specifiers)
            r = r + " " + " ".join(specifiers_strs)
        return r

    def str_full_return_type(self) -> str:
        return ""

    def str_code(self) -> str:
        return self._str_signature()

    def __str__(self) -> str:
        return self.str_commented()


@dataclass
class CppConstructor(CppConstructorDecl):
    """
    https://www.srcml.org/doc/cpp_srcML.html#constructor
    """

    block: CppUnprocessed
    member_init_list: CppUnprocessed

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)

    def str_code(self) -> str:
        r = self._str_signature()
        if hasattr(self, "block"):
            r += str(self.block)
        return r

    def __str__(self) -> str:
        r = ""
        if len(self.cpp_element_comments.top_comment_code()) > 0:
            r += self.cpp_element_comments.top_comment_code()
        r += self._str_signature() + self.cpp_element_comments.eol_comment_code()
        r += "\n" + str(self.block) + "\n"
        return r

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        if hasattr(self, "block"):
            self.block.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        if hasattr(self, "member_init_list"):
            self.member_init_list.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)


@dataclass
class CppSuper(CppElement):
    """
    Define a super classes of a struct or class
    https://www.srcml.org/doc/cpp_srcML.html#struct-definition
    """

    specifier: str = ""  # public, private or protected inheritance
    superclass_name: str = ""  # name of the super class

    def __init__(self, element: SrcmlXmlWrapper):
        super().__init__(element)

    def str_code(self) -> str:
        if len(self.specifier) > 0:
            return f"{self.specifier} {self.superclass_name}"
        else:
            return self.superclass_name

    def __str__(self) -> str:
        return self.str_code()


@dataclass
class CppSuperList(CppElement):
    """
    Define a list of super classes of a struct or class
    https://www.srcml.org/doc/cpp_srcML.html#struct-definition
    """

    super_list: List[CppSuper]

    def __init__(self, element: SrcmlXmlWrapper):
        super().__init__(element)
        self.super_list: List[CppSuper] = []

    def str_code(self) -> str:
        strs = list(map(str, self.super_list))
        return " : " + code_utils.join_remove_empty(", ", strs)

    def __str__(self) -> str:
        return self.str_code()

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        for super_class in self.super_list:
            super_class.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)


@dataclass
class CppStruct(CppElementAndComment, ICppTemplateHost):
    """
    https://www.srcml.org/doc/cpp_srcML.html#struct-definition
    """

    class_name: str  # either the class or the struct name
    super_list: CppSuperList
    block: CppBlock
    specifier: str  # "final" for final classes, empty otherwise

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)
        self._init_template_host()
        self.class_name = ""
        self.specifier = ""

    def str_code(self) -> str:
        r = ""
        r += self.str_template()

        if isinstance(self, CppClass):
            r += "class "
        elif isinstance(self, CppStruct):
            r += "struct "
        r += f"{self.class_name}"

        if hasattr(self, "super_list") and len(str(self.super_list)) > 0:
            r += str(self.super_list)

        r += "\n"

        r += "{\n"
        r += code_utils.indent_code(str(self.block), 4)
        r += "};\n"

        return r

    def __str__(self) -> str:
        return self.str_commented()

    def is_final(self) -> bool:
        return self.specifier == "final"

    def has_base_classes(self) -> bool:
        if not hasattr(self, "super_list"):
            return False
        return len(self.super_list.super_list) > 0

    def base_classes(self) -> List[Tuple[AccessTypes, CppStruct]]:
        if not self.has_base_classes():
            return []

        r = []
        for cpp_super in self.super_list.super_list:
            access_type = AccessTypes.from_name(cpp_super.specifier)

            root_cpp_unit = self.root_cpp_unit_parent()
            base_struct = root_cpp_unit.find_struct_or_class(
                cpp_super.superclass_name, self.cpp_scope(include_self=False)
            )
            if base_struct is not None:
                r.append((access_type, base_struct))
        return r

    def has_non_default_ctor(self) -> bool:
        found_non_default_ctor = False
        for access_zone in self.block.block_children:
            if isinstance(access_zone, CppPublicProtectedPrivate):
                for child in access_zone.block_children:
                    if isinstance(child, CppConstructorDecl):
                        found_non_default_ctor = True
                        break
                    if isinstance(child, CppFunctionDecl) and child.function_name == self.class_name:
                        found_non_default_ctor = True
                        break

        return found_non_default_ctor

    def has_deleted_default_ctor(self) -> bool:
        found_deleted_default_ctor = False
        for access_zone in self.block.block_children:
            if isinstance(access_zone, CppPublicProtectedPrivate):
                for child in access_zone.block_children:
                    if isinstance(child, CppConstructorDecl):
                        if "delete" in child.specifiers:
                            found_deleted_default_ctor = True
                            break
        return found_deleted_default_ctor

    def has_private_dtor(self) -> bool:
        found_private_dtor = False
        for access_zone in self.block.block_children:
            if isinstance(access_zone, CppPublicProtectedPrivate):
                if access_zone.access_type == "private":
                    for child in access_zone.block_children:
                        if child.tag() == "destructor_decl" or child.tag() == "destructor":
                            found_private_dtor = True
                            break
        return found_private_dtor

    def get_public_blocks(self) -> List[CppPublicProtectedPrivate]:
        """
        Returns the public blocks of the class
        """
        r: List[CppPublicProtectedPrivate] = []
        for access_zone in self.block.block_children:
            if isinstance(access_zone, CppPublicProtectedPrivate):
                if access_zone.access_type == "public":
                    r.append(access_zone)
        return r

    def get_members(self) -> List[Tuple[AccessTypes, CppDecl]]:
        r: List[Tuple[AccessTypes, CppDecl]] = []
        for access_zone in self.block.block_children:
            if isinstance(access_zone, CppPublicProtectedPrivate):
                access_type = AccessTypes.from_name(access_zone.access_type)
                for child in access_zone.block_children:
                    if isinstance(child, CppDeclStatement):
                        for cpp_decl in child.cpp_decls:
                            r.append((access_type, cpp_decl))
        return r

    def get_public_elements(self) -> List[CppElementAndComment]:
        """
        Returns the public members, constructors, and methods
        """
        r: List[CppElementAndComment] = []
        for access_zone in self.block.block_children:
            if isinstance(access_zone, CppPublicProtectedPrivate):
                if access_zone.access_type == "public":
                    for child in access_zone.block_children:
                        r.append(child)
        return r

    def get_protected_elements(self) -> List[CppElementAndComment]:
        """
        Returns the protected members, constructors, and methods
        """
        r: List[CppElementAndComment] = []
        for access_zone in self.block.block_children:
            if isinstance(access_zone, CppPublicProtectedPrivate):
                if access_zone.access_type == "protected":
                    for child in access_zone.block_children:
                        r.append(child)
        return r

    def all_methods(self) -> List[CppFunctionDecl]:
        r: List[CppFunctionDecl] = []
        for access_zone in self.block.block_children:
            if isinstance(access_zone, CppPublicProtectedPrivate):
                for child in access_zone.block_children:
                    if isinstance(child, CppFunctionDecl):
                        r.append(child)
        return r

    def all_methods_with_name(self, name: str) -> List[CppFunctionDecl]:
        all_methods = self.all_methods()
        r: List[CppFunctionDecl] = []
        for fn in all_methods:
            if fn.function_name == name:
                r.append(fn)
        return r

    def is_virtual(self) -> bool:
        """Returns True if there is at least one virtual method"""
        for method in self.all_methods():
            if method.is_virtual_method():
                return True
        return False

    def virtual_methods(self, include_inherited_virtual_methods: bool) -> List[CppFunctionDecl]:
        virtual_methods = []
        for base_method in self.all_methods():
            if base_method.is_virtual_method():
                virtual_methods.append(base_method)

        def is_method_already_present(method: CppFunctionDecl) -> bool:
            for present_method in virtual_methods:
                same_name = present_method.function_name == method.function_name
                same_parameters_types = (
                    present_method.parameter_list.str_types_names_only() == method.parameter_list.str_types_names_only()
                )
                if same_name and same_parameters_types:
                    return True
            return False

        for _access_type, base_class in self.base_classes():
            for base_method in base_class.virtual_methods(include_inherited_virtual_methods):
                if not is_method_already_present(base_method):
                    virtual_methods.append(base_method)

        return virtual_methods

    def class_name_with_instantiation(self) -> str:
        return self.class_name + self._instantiation_str()

    def with_instantiated_template(self, template_specs: TemplateInstantiation) -> Optional[CppStruct]:
        """Returns a new non-templated class, implemented for the given type
        Only works on templated class with *one* template parameter
        Will return None if the application of the template changes nothing
        """
        new_class = copy.deepcopy(self)
        new_class._store_template_specs(template_specs)

        was_changed = False

        for ppp_block in new_class.block.block_children:
            if isinstance(ppp_block, CppPublicProtectedPrivate):
                ppp_new_block_children: List[CppElementAndComment] = []
                for ppp_child in ppp_block.block_children:
                    new_ppp_child: Optional[CppElementAndComment] = None
                    if isinstance(ppp_child, (CppFunctionDecl, CppStruct, CppDeclStatement)):
                        new_ppp_child = ppp_child.with_instantiated_template(template_specs)
                    if new_ppp_child is not None:
                        ppp_new_block_children.append(new_ppp_child)
                        was_changed = True
                    else:
                        ppp_new_block_children.append(ppp_child)
                ppp_block.block_children = ppp_new_block_children

        if was_changed:
            return new_class
        else:
            return None

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        if hasattr(self, "super_list"):
            self.super_list.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        if hasattr(self, "block"):
            self.block.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        if hasattr(self, "template"):
            self.template.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)

    def qualified_struct_name(self) -> str:
        parent_cpp_scope_str = self.cpp_scope().str_cpp()
        if len(parent_cpp_scope_str) > 0:
            r = parent_cpp_scope_str + "::" + self.class_name
        else:
            r = self.class_name
        return r


@dataclass
class CppClass(CppStruct):
    """
    https://www.srcml.org/doc/cpp_srcML.html#class-definition
    """

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments):
        super().__init__(element, cpp_element_comments)

    def __str__(self) -> str:
        return self.str_commented()


@dataclass
class CppComment(CppElementAndComment):
    """
    https://www.srcml.org/doc/cpp_srcML.html#comment
    Warning, the text contains "//" or "/* ... */" and "\n"
    """

    comment: str

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)

    def str_code(self) -> str:
        lines = self.comment.split("\n")  # split("\n") keeps empty lines (splitlines() does not!)
        lines = list(map(lambda s: "// " + s, lines))
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.str_code()


@dataclass
class CppNamespace(CppElementAndComment):
    """
    https://www.srcml.org/doc/cpp_srcML.html#namespace
    """

    ns_name: str
    block: CppBlock

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)
        self.ns_name = ""

    def str_code(self) -> str:
        r = f"namespace {self.ns_name}\n"
        r += "{\n"
        r += code_utils.indent_code(str(self.block), 4)
        r += "}"
        return r

    def __str__(self) -> str:
        return self.str_code()

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        if hasattr(self, "block"):
            self.block.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)


@dataclass
class CppEnum(CppElementAndComment):
    """
    https://www.srcml.org/doc/cpp_srcML.html#enum-definition
    https://www.srcml.org/doc/cpp_srcML.html#enum-class
    """

    block: CppBlock
    enum_type: str = ""  # "class" or ""
    enum_name: str = ""

    def __init__(self, element: SrcmlXmlWrapper, cpp_element_comments: CppElementComments) -> None:
        super().__init__(element, cpp_element_comments)

    def is_enum_class(self) -> bool:
        return self.enum_type == "class"

    def str_code(self) -> str:
        r = ""
        if self.enum_type == "class":
            r += f"enum class {self.enum_name}\n"
        else:
            r += f"enum {self.enum_name}\n"
        r += "{\n"
        block_code = self.block.str_block(is_enum=True)
        r += code_utils.indent_code(block_code, 4)
        r += "};\n"
        return r

    def __str__(self) -> str:
        return self.str_code()

    def get_enum_decls_poub(self) -> List[CppDecl]:
        r: List[CppDecl] = []
        for child in self.block.block_children:
            if isinstance(child, CppDecl):
                r.append(child)
        return r

    def get_children_with_filled_decl_values(self) -> List[CppElementAndComment]:
        children: List[CppElementAndComment] = []

        last_decl: Optional[CppDecl] = None

        for child in self.block.block_children:
            if not isinstance(child, CppDecl):
                children.append(child)
            else:
                decl = child
                decl_with_value = copy.copy(decl)

                if len(decl_with_value.initial_value_code) > 0:
                    """
                    we do not try to parse it as an integer, because sometimes an enum value
                    is a composition of other values.
                    For example: `enum Foo { A = 0, B = A << 1, C = A | B };`
                    """
                    if decl_with_value.initial_value_code in self.options.named_number_macros:
                        decl_with_value.initial_value_code = str(
                            self.options.named_number_macros[decl_with_value.initial_value_code]
                        )

                else:
                    if last_decl is None:
                        decl_with_value.initial_value_code = "0"  # in C/C++ the first value is 0 by default
                    else:
                        last_decl_value_str = last_decl.initial_value_code
                        try:
                            last_decl_value_int = int(last_decl_value_str)
                            decl_with_value.initial_value_code = str(last_decl_value_int + 1)
                        except ValueError:
                            decl.emit_warning(
                                """
                                Cannot parse the value of this enum element.
                                Hint: maybe add an entry to SrcmlOptions.named_number_macros""",
                            )

                last_decl = decl_with_value
                children.append(decl_with_value)

        return children

    def visit_cpp_breadth_first(self, cpp_visitor_function: CppElementsVisitorFunction, depth: int = 0) -> None:
        cpp_visitor_function(self, CppElementsVisitorEvent.OnElement, depth)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnBeforeChildren, depth)
        if hasattr(self, "block"):
            self.block.visit_cpp_breadth_first(cpp_visitor_function, depth + 1)
        cpp_visitor_function(self, CppElementsVisitorEvent.OnAfterChildren, depth)
