from codemanip import code_replacements

from litgen.options import LitgenOptions


def _preprocess_imgui_code(code: str) -> str:
    """
    The imgui code uses two macros (IM_FMTARGS and IM_FMTLIST) which help the compiler
        #define IM_FMTARGS(FMT)             __attribute__((format(printf, FMT, FMT+1)))
        #define IM_FMTLIST(FMT)             __attribute__((format(printf, FMT, 0)))

    They are used like this:
        IMGUI_API bool          TreeNode(const char* str_id, const char* fmt, ...) IM_FMTARGS(2);

    They are removed before processing the header, because they would not be correctly interpreted by srcml.
    """
    import re

    new_code = code
    new_code = re.sub(r"IM_FMTARGS\(\d\)", "", new_code)
    new_code = re.sub(r"IM_FMTLIST\(\d\)", "", new_code)
    return new_code


def litgen_options_imgui() -> LitgenOptions:
    from litgen.internal import cpp_to_python

    options = LitgenOptions()

    options.generate_to_string = False
    options.cpp_indent_size = 4

    options.code_replacements = cpp_to_python.standard_code_replacements()
    options.code_replacements += code_replacements.parse_string_replacements(
        r"\bImVector\s*<\s*([\w:]*)\s*> -> List[\1]"
    )

    options.python_max_line_length = -1  # in ImGui, the function decls are on *one* line
    options.python_convert_to_snake_case = False
    options.original_location_flag_show = True
    options.original_signature_flag_show = False

    options.buffer_flag_replace_by_array = True

    options.srcml_options.functions_api_prefixes = ["IMGUI_API"]
    options.srcml_options.header_guard_suffixes.append("IMGUI_DISABLE")

    options.buffer_types += ["float"]
    options.c_array_numeric_member_types += [
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

    options.srcml_options.code_preprocess_function = _preprocess_imgui_code

    options.srcml_options.function_name_exclude_regexes = [
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
        "appendfv",
        # Exclude function whose name ends with V, like for example
        #       IMGUI_API void          TextV(const char* fmt, va_list args)                            IM_FMTLIST(1);
        # which are utilities for variadic print format
        r"\w*V\Z",
    ]

    options.srcml_options.decl_name_exclude_regexes = [
        #     typedef void (*ImDrawCallback)(const ImDrawList* parent_list, const ImDrawCmd* cmd);
        #     ImDrawCallback  UserCallback;       // 4-8  // If != NULL, call the function instead of rendering the vertices. clip_rect and texture_id will be set normally.
        #     ^
        r"\bUserCallback\b",
        # struct ImDrawData
        # { ...
        #     ImDrawList**    CmdLists;               // Array of ImDrawList* to render. The ImDrawList are owned by ImGuiContext and only pointed to from here.
        #               ^
        # }
        r"\bCmdLists\b",
    ]

    options.srcml_options.decl_types_exclude_regexes = [
        r"^char\s*\*",
        r"const ImWchar\s*\*",
        r"unsigned char\s*\*",
        r"unsigned int\s*\*",
    ]

    options.srcml_options.class_name_exclude_regexes = [r"^ImVector\b", "ImGuiTextBuffer"]

    options.fn_force_overload_regexes = [
        r"^SetScroll",
        r"^Drag",
        r"^Slider",
        r"^InputText",
        r"Popup",
        r"DrawList",
        r"^Table",
    ]

    options.fn_force_return_policy_reference_for_pointers = True
    options.fn_force_return_policy_reference_for_references = True

    return options