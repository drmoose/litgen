# litgen

```{admonition} What is litgen
:class: note
`litgen`, also known as _Literate Generator_, is an automatic python bindings generator for humans who like nice code and APIs.

It can be used to bind C++ libraries into _documented_ and _discoverable_ python modules using [pybind11](https://pybind11.readthedocs.io/en/stable/index.html)
```

Although being relatively new (2022), litgen was battle tested on 20 different libraries totalling more than 100,000 lines of code, and it is the main driving force behind the python bindings for [Dear ImGui Bundle](https://github.com/pthom/imgui_bundle).

litgen puts a strong emphasis on emitting documented and discoverable code, thus providing a great experience for the final python user.

```{admonition} srcML
:class: tip
litgen is based on [srcML](https://www.srcml.org/) a multi-language parsing tool to convert source code into XML with a developer centric approach: preprocessor statements are kept unprocessed, and all original text is preserved (including white space, comments and special characters).
```

## litgen in action

As an appetizer, here is an example when using bindings generated by litgen inside a python Integrated Development Environment (IDE):

![IDE auto completion](images/ide_autocomplete.png)

_Example of auto-completion in an IDE: all bindings are discoverable_

![IDE params](images/ide_params.png)

_Parameters type are accurately reproduced, and the function documentation is accessible_

In the example above, the bindings were generated from the following C++ function signature:
```cpp
// Parameters stacks (current window)
IMGUI_API void          PushItemWidth(float item_width); // push width of items for common large "item+label" widgets. >0.0f: width in pixels, <0.0f align xx pixels to the right of window (so -FLT_MIN always align width to the right side).
```

And the generated code consists of two parts:

1. a python stub file, which contains the documentation and the function signatures, e.g.:
```python
# Parameters stacks (current window)
# IMGUI_API void          PushItemWidth(float item_width);        /* original C++ signature */
def push_item_width(item_width: float) -> None:
    """push width of items for common large "item+label" widgets. >0.0: width in pixels, <0.0 align xx pixels to the right of window (so -FLT_MIN always align width to the right side)."""
    pass
```

2. a C++ bindings file, which contains the actual bindings, e.g.:
```cpp
m.def("push_item_width",
    ImGui::PushItemWidth,
    py::arg("item_width"),
    "push width of items for common large \"item+label\" widgets. >0.0: width in pixels, <0.0 align xx pixels to the right of window (so -FLT_MIN always align width to the right side).");
```

## Examples

More complete examples can be found online inside the [Dear ImGui Bundle](https://github.com/pthom/imgui_bundle) repository, for example:

* [imgui.h](https://github.com/pthom/imgui/blob/imgui_bundle/imgui.h) header file that declares the API for [Dear ImGui](https://github.com/ocornut/imgui) in a documented way
* [imgui.piy](https://github.com/pthom/imgui_bundle/blob/main/bindings/imgui_bundle/imgui/__init__.pyi) the corresponding python stub file which exposes the bindings in a documented way

## Compatibility

Being based on srcML, litgen is compatible with C++14: your code can of course make use of more recent features (C++17, C++20 and C++23), but the API that you want to expose to python must be C++14 compatible.

## License

* Specific license to define: free for Open Source, paying for orgs.

* [srcML]() is  GNU GENERAL PUBLIC LICENSE Version 3


## Support

If you need help with bindings when working in an Open Source context, please open an issue on the [srcmlcpp repository](https://github.com/pthom/srcmlcpp/issues).

If you need help with bindings if a professional setting, please contact the author by email, for possible consulting work.

C++ is notorious for being hard to parse. As a consequence, the author makes no guaranty that the generator will work on all kinds of C++ constructs. Contributions and skilled contributors are welcome!

# Table of contents

```{tableofcontents}
```