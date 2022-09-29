import os
import sys

import srcmlcpp

import litgen
from litgen.litgen_generator import LitgenGeneratorTestsHelper
from litgen.litgen_options_imgui import litgen_options_imgui


_THIS_DIR = os.path.dirname(__file__)
sys.path.append(_THIS_DIR + "/../..")


def read_file_content(filename) -> str:
    with open(filename, "r") as f:
        content = f.read()
    return content


def play_parse(code) -> None:
    options = litgen_options_imgui()
    cpp_unit = srcmlcpp.code_to_cpp_unit(options.srcml_options, code)
    print(cpp_unit)


def play_stub(code, options) -> None:
    pyi_code = LitgenGeneratorTestsHelper.code_to_stub(options, code)
    print(f">>>\n{pyi_code}<<<")


def play_pydef(code, options) -> None:
    pyi_code = LitgenGeneratorTestsHelper.code_to_pydef(options, code)
    print(f">>>\n{pyi_code}<<<")


def litgensample_options() -> litgen.LitgenOptions:
    options = litgen.LitgenOptions()
    options.fn_params_replace_modifiable_c_array_by_boxed__regex = "array"
    options.fn_params_output_modifiable_immutable_to_return__regex = r".*"
    return options


def my_play() -> None:
    code = """
    enum Foo
    {
        Foo_A,
        Foo_B,
        Foo_Count
    };

    void PlayFoo(Foo f = Foo_A);
    """
    # options = litgen_options_imgui()
    options = litgen.options.LitgenOptions()
    play_stub(code, options)


if __name__ == "__main__":
    my_play()
