from enum import Enum

from codemanip.code_replacements import RegexReplacementList
from codemanip.code_utils import join_string_by_pipe_char
from srcmlcpp.srcmlcpp_options import WarningType

from litgen.options import LitgenOptions


class ImguiOptionsType(Enum):
    imgui_h = 1
    imgui_stdlib_h = 2
    imgui_internal_h = 3


def _preprocess_imgui_code(code: str) -> str:
    # The imgui code uses two macros (IM_FMTARGS and IM_FMTLIST) which help the compiler
    #     #define IM_FMTARGS(FMT)             __attribute__((format(printf, FMT, FMT+1)))
    #     #define IM_FMTLIST(FMT)             __attribute__((format(printf, FMT, 0)))
    #
    # They are used like this:
    #     IMGUI_API bool          TreeNode(const char* str_id, const char* fmt, ...) IM_FMTARGS(2);
    #
    # They are removed before processing the header, because they would not be correctly interpreted by srcml.
    import re

    new_code = code
    new_code, _n = re.subn(r"IM_FMTARGS\(\d\)", "", new_code)
    new_code, _n = re.subn(r"IM_FMTLIST\(\d\)", "", new_code)
    # Also, imgui_internal.h contains lines like this (with no final ";"):
    #       IM_MSVC_RUNTIME_CHECKS_OFF
    # This confuses srcML, so we add a ";" at the end of those lines
    new_code, _n = re.subn(r"\nIM_MSVC_RUNTIME_CHECKS_OFF\n", "\nIM_MSVC_RUNTIME_CHECKS_OFF;\n", new_code)
    new_code, _n = re.subn(r"\nIM_MSVC_RUNTIME_CHECKS_RESTORE\n", "\nIM_MSVC_RUNTIME_CHECKS_RESTORE;\n", new_code)
    return new_code


def litgen_options_imgui(options_type: ImguiOptionsType, docking_branch: bool) -> LitgenOptions:
    from litgen.internal import cpp_to_python

    options = LitgenOptions()

    options.srcmlcpp_options.ignored_warnings = [
        WarningType.LitgenClassMemberSkipBitfield,
        WarningType.LitgenClassMemberUnparsableSize,
        WarningType.LitgenClassMemberNonNumericCStyleArray,
    ]

    options.srcmlcpp_options.ignored_warning_parts = [
        "C style function pointers",
        "function_decl as a param",
        'Unsupported zero param "operator bool"',
        "ImGuiDataType_Pointer",
        "ImGuiDataType_ID",
    ]

    options.cpp_indent_size = 4

    options.namespace_root__regex = "^ImGui$"

    options.type_replacements = cpp_to_python.standard_type_replacements()
    options.type_replacements.merge_replacements(
        RegexReplacementList.from_string(
            r"""
            \bImVector\s*<\s*([\w:]*)\s*> -> List[\1]
            ^signed char$ -> int
            ^char$ -> int
            """
        )
    )

    options.function_names_replacements.merge_replacements(
        RegexReplacementList.from_string(
            r"""
            RGBtoHSV -> RgbToHsv
            HSVtoRGB -> HsvToRgb
            """
        )
    )

    options.type_replacements.add_last_replacement(r"ImGui([A-Z][a-zA-Z0-9]*)", r"\1")
    options.var_names_replacements.add_last_replacement(r"^id$", "id_")  # id() is a built-in function in python

    # options.names_replacements.add_last_replacement(r"(^ImGui)([A-Z])", r"\2")

    options.python_max_line_length = -1  # in ImGui, the function decls are on *one* line
    options.python_convert_to_snake_case = True
    options.original_location_flag_show = True
    options.original_signature_flag_show = True

    options.python_run_black_formatter = True

    options.srcmlcpp_options.functions_api_prefixes = "IMGUI_API"

    options.srcmlcpp_options.header_filter_acceptable__regex += "|^IMGUI_DISABLE$"
    if docking_branch:
        options.srcmlcpp_options.header_filter_acceptable__regex += "|^IMGUI_HAS_DOCK$"

    options.srcmlcpp_options.code_preprocess_function = _preprocess_imgui_code

    options.fn_exclude_by_name__regex = join_string_by_pipe_char(
        [
            # IMGUI_API void          SetAllocatorFunctions(ImGuiMemAllocFunc alloc_func, ImGuiMemFreeFunc free_func, void* user_data = NULL);
            #                                               ^
            # IMGUI_API void          GetAllocatorFunctions(ImGuiMemAllocFunc* p_alloc_func, ImGuiMemFreeFunc* p_free_func, void** p_user_data);
            #                                               ^
            # IMGUI_API void*         MemAlloc(size_t size);
            #           ^
            # IMGUI_API void          MemFree(void* ptr);
            #                                 ^
            r"\bGetAllocatorFunctions\b",
            r"\bSetAllocatorFunctions\b",
            r"\bMemAlloc\b",
            r"\bMemFree\b",
            # IMGUI_API void              GetTexDataAsAlpha8(unsigned char** out_pixels, int* out_width, int* out_height, int* out_bytes_per_pixel = NULL);  // 1 byte per-pixel
            #                                                             ^
            # IMGUI_API void              GetTexDataAsRGBA32(unsigned char** out_pixels, int* out_width, int* out_height, int* out_bytes_per_pixel = NULL);  // 4 bytes-per-pixel
            #                                                             ^
            r"\bGetTexDataAsAlpha8\b",
            r"\bGetTexDataAsRGBA32\b",
            # IMGUI_API ImVec2            CalcTextSizeA(float size, float max_width, float wrap_width, const char* text_begin, const char* text_end = NULL, const char** remaining = NULL) const; // utf8
            #                                                                                                                                                         ^
            r"\bCalcTextSizeA\b",
            r"ImFormatStringToTempBuffer",
            r"ImTextStrFromUtf8",
            "appendfv",
            # Exclude function whose name ends with V, like for example
            #       IMGUI_API void          TextV(const char* fmt, va_list args)                            IM_FMTLIST(1);
            # which are utilities for variadic print format
            r"[a-z0-9]V$",
            # Low level utility functions from imgui_internal.h
            r"^ImStr",
            r"^ImFormat",
            r"^ImParseFormat",
            r"^ImFontAtlasBuild",
            r"^ImText\w*To",
            r"^ImText\w*From",
            r"^DataType",
            r"^InputTextEx$",
            r"^TempInput",
            r"^ErrorCheckEnd",
            r"ImFileLoadToMemory",
            r"AddFontFromFileTTF",
        ]
    )

    options.member_exclude_by_name__regex = join_string_by_pipe_char(
        [
            #     typedef void (*ImDrawCallback)(const ImDrawList* parent_list, const ImDrawCmd* cmd);
            #     ImDrawCallback  UserCallback;       // 4-8  // If != NULL, call the function instead of rendering the vertices. clip_rect and texture_id will be set normally.
            #     ^
            r"Callback$",
            # struct ImDrawData
            # { ...
            #     ImDrawList**    CmdLists;               // Array of ImDrawList* to render. The ImDrawList are owned by ImGuiContext and only pointed to from here.
            #               ^
            # }
            r"\bCmdLists\b",
        ]
    )

    options.member_exclude_by_type__regex = join_string_by_pipe_char(
        [
            r"^char\s*\*",
            r"const ImWchar\s*\*",
            r"unsigned char\s*\*",
            r"unsigned int\s*\*",
            r"^ImVector",
            r"^ImPool",
            r"^ImChunkStream",
            r"^ImSpan",
            r"^ImBitArray",
            r"::STB_",
            # r"^ImGuiStorage$"
        ]
    )

    options.class_exclude_by_name__regex = join_string_by_pipe_char(
        [
            r"^ImVector\b",
            # "ImGuiTextBuffer",
            # "^ImGuiStorage$"
        ]
    )

    options.member_numeric_c_array_types += "|" + join_string_by_pipe_char(
        [
            "ImGuiID",
            "ImS8",
            "ImU8",
            "ImS16",
            "ImU16",
            "ImS32",
            "ImU32",
            "ImS64",
            "ImU64",
        ]
    )

    # options.fn_force_overload__regex = r".*"
    options.fn_force_overload__regex = join_string_by_pipe_char(
        [
            r"^SetScroll",
            r"^Drag",
            r"^Slider",
            r"^InputText",
            r"Popup",
            r"DrawList",
            r"^Table",
            r"^SetWindowPos",
            r"^SetWindowSize",
            r"^SetWindowCollapsed",
        ]
    )

    options.fn_return_force_policy_reference_for_pointers__regex = r".*"
    options.fn_return_force_policy_reference_for_references__regex = r".*"

    options.fn_params_replace_buffer_by_array__regex = r".*"

    # Exclude callbacks from the params when they have a default value
    # (since imgui use bare C function pointers, not easily portable)
    options.fn_params_exclude_types__regex = r"Callback$"
    options.fn_exclude_by_param_type__regex = "^char$"

    # Version where we use Boxed types everywhere
    # options.fn_params_replace_modifiable_immutable_by_boxed__regex = r".*"
    # Version where we return tuples
    options.fn_params_output_modifiable_immutable_to_return__regex = r".*"

    options.fn_params_replace_c_array_modifiable_by_boxed__regex = ""

    options.srcmlcpp_options.flag_show_progress = True

    if options_type == ImguiOptionsType.imgui_h:
        options.fn_exclude_by_name__regex += "|^InputText"
    elif options_type == ImguiOptionsType.imgui_internal_h:
        options.fn_template_options.add_ignore(".*")
        options.class_template_options.add_ignore(".*")
    elif options_type == ImguiOptionsType.imgui_stdlib_h:
        pass

    return options
