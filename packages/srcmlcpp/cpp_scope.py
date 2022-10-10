from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class CppScopeType(Enum):
    Namespace = "Namespace"
    ClassOrStruct = "ClassOrStruct"
    Enum = "Enum"


@dataclass
class CppScopePart:
    scope_type: CppScopeType
    scope_name: str


class CppScope:
    scope_parts: List[CppScopePart]

    def __init__(self, scopes: Optional[List[CppScopePart]] = None) -> None:
        if scopes is None:
            self.scope_parts = []
        else:
            self.scope_parts = scopes

    def str_cpp(self) -> str:
        """Returns this scope as a cpp, e.g Foo::Blah"""
        if len(self.scope_parts) == 0:
            return ""
        scope_names = map(lambda s: s.scope_name, self.scope_parts)
        r = "::".join(scope_names)
        return r

    def str_cpp_prefix(self) -> str:
        """Returns this scope as a cpp, e.g Foo::Blah::"""
        s = self.str_cpp()
        if len(s) == 0:
            return ""
        else:
            return s + "::"

    def __str__(self):
        return self.str_cpp()
