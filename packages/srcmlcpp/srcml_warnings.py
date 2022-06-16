import sys
from typing import List
from dataclasses import dataclass
import xml.etree.ElementTree as ET  # noqa
import logging
import traceback
import inspect

import srcmlcpp
from srcmlcpp import code_utils, srcml_main, srcml_types, srcml_utils
from srcmlcpp.srcml_options import SrcmlOptions
from srcmlcpp.srcml_exception import SrcMlException


###########################################
#
# Error and warning messages
#
###########################################


@dataclass
class CodePos:
    line: int = 0
    col: int = 0


@dataclass
class ErrorContext:
    concerned_lines: List[str]
    start: CodePos = CodePos()
    end: CodePos = CodePos()

    def __str__(self):
        msg = ""
        for i, line in enumerate(self.concerned_lines):
            msg += line + "\n"
            if self.start is not None:
                if i == self.start.line:
                    nb_spaces = self.start.col - 1
                    if nb_spaces < 0:
                        nb_spaces = 0
                    msg += " " * nb_spaces + "^" + "\n"

        return msg


def _extract_error_context(element: ET.Element) -> ErrorContext:
    cpp_element = srcml_types.CppElement(element)

    full_code = srcml_main.srcml_main_context().current_parsed_file_unit_code
    if len(full_code) > 0:
        full_code_lines = [""] + full_code.split("\n")

        if cpp_element.start() is not None and len(full_code) > 0:
            concerned_lines = full_code_lines[cpp_element.start().line : cpp_element.end().line + 1]
            start = CodePos(0, cpp_element.start().column)
            end = CodePos(
                cpp_element.end().line - cpp_element.start().line,
                cpp_element.end().column,
            )
            return ErrorContext(concerned_lines, start, end)
        else:
            return ErrorContext([], CodePos(), CodePos())
    else:
        original_code = srcmlcpp.srcml_to_code(element)
        return ErrorContext(original_code.split("\n"), cpp_element.start(), cpp_element.end())


def _highlight_responsible_code(element: ET.Element) -> str:
    error_context = _extract_error_context(element)
    return str(error_context)


def _show_element_info(element: ET.Element, encoding):
    def file_location(element: ET.Element):
        header_filename = srcml_main.srcml_main_context().current_parsed_file
        if len(header_filename) == 0:
            header_filename = "Position"
        start = srcml_utils.element_start_position(element)
        if start is not None:
            return f"{header_filename}:{start.line}:{start.column}"
        else:
            return f"{header_filename}"

    element_tag = srcml_utils.clean_tag_or_attrib(element.tag)
    concerned_code = _highlight_responsible_code(element)
    message = f"""        
    While parsing a "{element_tag}", corresponding to this C++ code:
    {file_location(element)}
{code_utils.indent_code(concerned_code, 12)}
    """
    return message


def _warning_detailed_info(
    current_element: ET.Element = None,
    additional_message: str = "",
    options: SrcmlOptions = SrcmlOptions(),
):
    def _get_python_call_info():
        stack_lines = traceback.format_stack()
        error_line = stack_lines[-4]
        frame = inspect.currentframe()
        caller_function_name = inspect.getframeinfo(frame.f_back.f_back.f_back).function
        return caller_function_name, error_line

    python_caller_function_name, python_error_line = _get_python_call_info()

    def show_python_callstack():
        return f"""
                Python call stack info:
        {code_utils.indent_code(python_error_line, 4)}
        """

    message = ""

    if current_element is not None:
        message += _show_element_info(current_element, options.encoding)

    if options.flag_show_python_callstack:
        message += show_python_callstack()

    if len(additional_message) > 0:
        message = (
            code_utils.unindent_code(additional_message, flag_strip_empty_lines=True)
            + "\n"
            + code_utils.unindent_code(message, flag_strip_empty_lines=True)
        )

    return message


class SrcMlExceptionDetailed(SrcMlException):
    def __init__(
        self,
        current_element: ET.Element = None,
        additional_message="",
        options: SrcmlOptions = SrcmlOptions(),
    ):
        message = _warning_detailed_info(current_element, additional_message, options=options)
        super().__init__(message)


def emit_srcml_warning(
    current_element: ET.Element = None,
    additional_message="",
    options: SrcmlOptions = SrcmlOptions(),
):
    if options.flag_quiet:
        return
    message = _warning_detailed_info(current_element, additional_message, options)

    in_pytest = "pytest" in sys.modules
    if in_pytest:
        logging.warning(message)
    else:
        print("Warning: " + message, file=sys.stderr)


def emit_warning(message: str, options: SrcmlOptions):
    if options.flag_quiet:
        return
    in_pytest = "pytest" in sys.modules
    if in_pytest:
        logging.warning(message)
    else:
        print("Warning: " + message, file=sys.stderr)