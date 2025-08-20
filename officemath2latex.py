from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional, List
from lxml import etree

# Namespaces
NS = {
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "xml": "http://www.w3.org/XML/1998/namespace",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
}


def qname(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def get_localname(el: etree._Element) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


# Public API

def process_math_string(math_string: str) -> str:
    """Parse an OfficeMath XML string and return LaTeX string.
    The input element should be an m:oMath or container with OfficeMath child nodes.
    """
    ns_str = " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in NS.items())
    wrapped = f'<root {ns_str}>{math_string}</root>'
    root = etree.fromstring(wrapped.encode("utf-8"))
    omath_node = root.find(qname("m", "oMath"))
    if omath_node is None:
        raise ValueError("No OfficeMath node found in the input string.")
    return process_math_node(omath_node)


def process_math_node(math_xml: etree._Element, chr_: str = "") -> str:
    return OfficeMathNode(math_xml).process(chr_)


# Core node wrappers

@dataclass
class OfficeMathNode:
    node: etree._Element

    def iter_element_children(self) -> List[etree._Element]:
        return [c for c in self.node if isinstance(c.tag, str)]

    def process(self, chr_: str = "") -> str:
        math_string = ""
        for element in self.iter_element_children():
            child = OfficeMathElement(element)
            math_string += child.process(chr_)
        return math_string


@dataclass
class OfficeMathElement:
    node: etree._Element

    def process(self, chr_: str = "") -> str:
        name = get_localname(self.node)
        # All Office Math tags are in the m namespace
        if self.node.tag == qname("m", "e"):
            return OfficeMathNode(self.node).process(chr_) + chr_
        if self.node.tag == qname("m", "r"):
            return OfficeMathRun(self.node).process(chr_)
        if self.node.tag in {qname("m", "sSup"), qname("m", "sSub"), qname("m", "sSubSup")}:
            return OfficeMathSuperscriptSubscript(self.node).process(chr_)
        if self.node.tag == qname("m", "d"):
            return OfficeMathDelimiter(self.node).process(chr_)
        if self.node.tag == qname("m", "f"):
            return OfficeMathFraction(self.node).process(chr_)
        if self.node.tag == qname("m", "nary"):
            return OfficeMathNary(self.node).process(chr_)
        if self.node.tag == qname("m", "func"):
            return OfficeMathFunction(self.node).process(chr_)
        if self.node.tag == qname("m", "limLow"):
            return OfficeMathLimLowerUpper(self.node).process(chr_, "_")
        if self.node.tag == qname("m", "limUpp"):
            return OfficeMathLimLowerUpper(self.node).process(chr_, "^")
        if self.node.tag == qname("m", "m"):
            return OfficeMathMatrix(self.node).process()
        if self.node.tag == qname("m", "acc"):
            return OfficeMathAccent(self.node).process(chr_)
        if self.node.tag == qname("m", "groupChr"):
            return OfficeMathGroupCharacter(self.node).process(chr_)
        if self.node.tag == qname("m", "bar"):
            return OfficeMathBar(self.node).process(chr_)
        if self.node.tag == qname("m", "rad"):
            return OfficeMathRadical(self.node).process(chr_)
        if self.node.tag == qname("m", "eqArr"):
            return OfficeMathEquationArray(self.node).process(chr_)
        if self.node.tag == qname("m", "box"):
            return "{" + OfficeMathNode(self.node).process(chr_) + "}"
        if self.node.tag == qname("m", "borderBox"):
            return "\\boxed{" + OfficeMathNode(self.node).process(chr_) + "}"
        if self.node.tag == qname("m", "sPre"):
            return OfficeMathSPre(self.node).process(chr_)
        if self.node.tag == qname("m", "t"):
            return OfficeMathText(self.node).process(chr_)
        # Unknown or unsupported node
        return ""


@dataclass
class OfficeMathSuperscriptSubscript(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        math_string = ""
        for el in self.node:
            if el.tag == qname("m", "e"):
                math_string += OfficeMathNode(el).process(chr_)
            elif el.tag == qname("m", "sup"):
                math_string += "^{" + OfficeMathNode(el).process(chr_) + "}"
            elif el.tag == qname("m", "sub"):
                math_string += "_{" + OfficeMathNode(el).process(chr_) + "}"
        return math_string


@dataclass
class OfficeMathDelimiter(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        math_string = ""
        open_par = "\\left( "
        close_par = "\\right)"

        for el in self.node:
            if el.tag == qname("m", "dPr"):
                open_par, close_par = self.get_delimiters(el)
            elif el.tag == qname("m", "e"):
                math_string += OfficeMathNode(el).process(chr_)

        if math_string.startswith("\\genfrac{}{}{0pt}{}"):
            return math_string.replace("\\genfrac{}{}{0pt}{}", "\\binom")

        return f"{open_par}{math_string}{close_par}"

    def get_delimiters(self, dpr_node: etree._Element) -> tuple[str, str]:
        open_par = "\\left( "
        close_par = "\\right)"
        for dpr in dpr_node:
            if dpr.tag == qname("m", "begChr"):
                val = dpr.get(qname("m", "val"))
                open_par = self.get_open_bracket(val)
            elif dpr.tag == qname("m", "endChr"):
                val = dpr.get(qname("m", "val"))
                close_par = self.get_close_bracket(val)
        return open_par, close_par

    def get_open_bracket(self, val: Optional[str]) -> str:
        match val:
            case "|":
                return "\\left| "
            case "{":
                return "\\left\\{ "
            case "[":
                return "\\left\\lbrack "
            case "]":
                return "\\left\\rbrack "
            case "〈":
                return "\\left\\langle "
            case "⌊":
                return "\\left\\lfloor "
            case "⌈":
                return "\\left\\lceil "
            case "‖":
                return "\\left\\| "
            case "⟦":
                return "\\left. ⟦ "
            case _:
                return "\\left. "

    def get_close_bracket(self, val: Optional[str]) -> str:
        match val:
            case "|":
                return "\\right| "
            case "}":
                return "\\right\\} "
            case "[":
                return "\\right\\lbrack "
            case "]":
                return "\\right\\rbrack "
            case "〉":
                return "\\right\\rangle "
            case "⌋":
                return "\\right\\rfloor "
            case "⌉":
                return "\\right\\rceil "
            case "‖":
                return "\\right\\| "
            case "⟧":
                return "\\right.⟧ "
            case _:
                return "\\right. "


@dataclass
class OfficeMathRun(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        math_string = ""
        flag_bold = False

        for el in self.node:
            if el.tag == qname("m", "rPr"):
                for rpr in el:
                    if rpr.tag == qname("m", "sty") and rpr.get(qname("m", "val")) == "b":
                        flag_bold = True
            elif el.tag == qname("m", "t"):
                text_content = (el.text or "").strip()
                if el.get(qname("xml", "space")) == "preserve":
                    math_string += "\\ \\ " if text_content == "" else OfficeMathFieldCodeText(text_content).process(chr_)
                else:
                    math_string += text_content

        replacements = [
            (r"π", r"\pi "),
            (r"∞", r"\infty "),
            (r"→", r"\rightarrow "),
            (r"±", r"\pm "),
            (r"∓", r"\mp "),
            (r"α", r"\alpha "),
            (r"β", r"\beta "),
            (r"γ", r"\gamma "),
            (r"…", r"\ldots "),
            (r"⋅", r"\cdot "),
            (r"×", r"\times "),
            (r"θ", r"\theta "),
            (r"Γ", r"\Gamma "),
            (r"≈", r"\approx "),
            (r"ⅈ", r"i "),
            (r"∇", r"\nabla "),
            (r"ⅆ", r"d "),
            (r"≥", r"\geq "),
            (r"∀", r"\forall "),
            (r"∃", r"\exists "),
            (r"∧", r"\land "),
            (r"⇒", r"\Rightarrow "),
            (r"ψ", r"\psi "),
            (r"∂", r"\partial "),
            (r"≠", r"\neq "),
            (r"~", r"\sim "),
            (r"÷", r"\div "),
            (r"∝", r"\propto "),
            (r"≪", r"\ll "),
            (r"≫", r"\gg "),
            (r"≤", r"\leq "),
            (r"≅", r"\cong "),
            (r"≡", r"\equiv "),
            (r"∁", r"\complement "),
            (r"∪", r"\cup "),
            (r"∩", r"\cap "),
            (r"∅", r"\varnothing "),
            (r"∆", r"\mathrm{\\Delta} "),
            (r"∄", r"\nexists "),
            (r"∈", r"\in "),
            (r"∋", r"\ni "),
            (r"←", r"\leftarrow "),
            (r"↑", r"\uparrow "),
            (r"↓", r"\downarrow "),
            (r"↔", r"\leftrightarrow "),
            (r"∴", r"\therefore "),
            (r"¬", r"\neg "),
            (r"δ", r"\delta "),
            (r"ε", r"\varepsilon "),
            (r"ϵ", r"\epsilon "),
            (r"ϑ", r"\vartheta "),
            (r"μ", r"\mu "),
            (r"ρ", r"\rho "),
            (r"σ", r"\sigma "),
            (r"τ", r"\tau "),
            (r"φ", r"\varphi "),
            (r"ω", r"\omega "),
            (r"∙", r"\bullet "),
            (r"⋮", r"\vdots "),
            (r"⋱", r"\ddots "),
            (r"ℵ", r"\aleph "),
            (r"ℶ", r"\beth "),
            (r"∎", r"\blacksquare "),
            (r"%°", r"\%{^\\circ} "),
            (r"√", r"\sqrt{} "),
            (r"∛", r"\sqrt[3]{} "),
            (r"∜", r"\sqrt[4]{} "),
            (r"≜", r"\triangleq "),
        ]

        for pre, post in replacements:
            math_string = math_string.replace(pre, post)

        if flag_bold:
            math_string = f"\\mathbf{{{math_string}}}"

        return math_string


@dataclass
class OfficeMathFraction(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        frac_type = self.get_fraction_type()
        return self.process_fraction(chr_, frac_type)

    def get_fraction_type(self) -> str:
        frac_type = ""
        for el in self.node:
            if el.tag == qname("m", "fPr"):
                for fpr in el:
                    if fpr.tag == qname("m", "type"):
                        frac_type = fpr.get(qname("m", "val")) or ""
        return frac_type

    def process_fraction(self, chr_: str, frac_type: str) -> str:
        num_string = ""
        den_string = ""

        for el in self.node:
            if el.tag == qname("m", "num"):
                num_string = OfficeMathNode(el).process(chr_)
            elif el.tag == qname("m", "den"):
                den_string = OfficeMathNode(el).process(chr_)

        if frac_type == "noBar":
            return f"\\genfrac{{}}{{}}{{0pt}}{{}}{{{num_string}}}{{{den_string}}}"
        elif frac_type == "skw":
            return f"\\nicefrac{{{num_string}}}{{{den_string}}}"
        elif frac_type == "lin":
            return f"{num_string}/{den_string}"
        else:
            return f"\\frac{{{num_string}}}{{{den_string}}}"


@dataclass
class OfficeMathNary(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        math_string = "\\int"
        sub_string = ""
        sup_string = ""
        post_string = ""

        for el in self.node:
            if el.tag == qname("m", "naryPr"):
                for npr in el:
                    if npr.tag == qname("m", "chr"):
                        val = npr.get(qname("m", "val"))
                        math_string = self.get_nary_operator(val)
            elif el.tag == qname("m", "sub"):
                sub_string = "_{" + OfficeMathNode(el).process(chr_) + "}"
            elif el.tag == qname("m", "sup"):
                sup_string = "^{" + OfficeMathNode(el).process(chr_) + "}"
            else:
                post_string += "{" + OfficeMathNode(el).process(chr_) + "}"

        return f"{math_string}{sub_string}{sup_string}{post_string}"

    def get_nary_operator(self, val: Optional[str]) -> str:
        match val:
            case "∑":
                return "\\sum"
            case "∏":
                return "\\prod"
            case "∐":
                return "\\coprod"
            case "∬":
                return "\\iint"
            case "∭":
                return "\\iiint"
            case "∮":
                return "\\oint"
            case "∯":
                return "\\oiint"
            case "∰":
                return "\\oiiint"
            case "⋃":
                return "\\bigcup"
            case "⋂":
                return "\\bigcap"
            case "⋁":
                return "\\bigvee"
            case "⋀":
                return "\\bigwedge"
            case _:
                return "\\int"


@dataclass
class OfficeMathFunction(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        math_string = ""
        for el in self.node:
            if el.tag == qname("m", "fName"):
                function_name = OfficeMathNode(el).process(chr_).strip()
                math_string += self.get_function_string(function_name)
            else:
                math_string += OfficeMathNode(el).process(chr_)
        return math_string + "}"

    def get_function_string(self, function_name: str) -> str:
        funcs = {
            "tan", "csc", "sec", "cot", "sin", "cos",
            "sinh", "cosh", "tanh", "coth",
        }
        if function_name in funcs or any(
            function_name.startswith(p) for p in ("log", "ln", "max", "min")
        ):
            return f"\\{function_name}{{"
        else:
            return f"{function_name}{{"


@dataclass
class OfficeMathLimLowerUpper(OfficeMathElement):
    def process(self, chr_: str = "", type_: str = "^") -> str:
        math_string = ""
        for el in self.node:
            if el.tag == qname("m", "e"):
                element_string = OfficeMathNode(el).process(chr_)
                if element_string.strip() == "lim":
                    math_string += "\\" + element_string.strip()
                else:
                    math_string += element_string
            elif el.tag == qname("m", "lim"):
                math_string += f"{type_}{{{OfficeMathNode(el).process(chr_)}}}"
        return math_string


@dataclass
class OfficeMathMatrix(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        rows: List[str] = []
        for el in self.node:
            if el.tag == qname("m", "mr"):
                row_string = OfficeMathNode(el).process("&")
                if row_string.endswith("&"):
                    row_string = row_string[:-1]
                rows.append(row_string)
        return "\\begin{matrix}\n" + " \\\\\n".join(rows) + "\n\\end{matrix}"


@dataclass
class OfficeMathAccent(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        accent_string = "\\widehat{"
        math_string = ""
        for el in self.node:
            if el.tag == qname("m", "accPr"):
                for apr in el:
                    if apr.tag == qname("m", "chr"):
                        val = apr.get(qname("m", "val"))
                        accent_string = self.get_accent_operator(val)
            if el.tag == qname("m", "e"):
                math_string += OfficeMathNode(el).process(chr_)
        opens = accent_string.count("{")
        closes = accent_string.count("}")
        return accent_string + math_string + ("}" * (opens - closes))

    def get_accent_operator(self, val: Optional[str]) -> str:
        match val:
            case "̇":
                return "\\dot{"
            case "̈":
                return "\\ddot{"
            case "⃛":
                return "\\dddot{"
            case "̌":
                return "\\check{"
            case "́":
                return "\\acute{"
            case "̀":
                return "\\grave{"
            case "̆":
                return "\\breve{"
            case "̃":
                return "\\widetilde{"
            case "̅":
                return "\\overline{"
            case "̿":
                return "\\overline{\\overline{"
            case "⃖":
                return "\\overleftarrow{"
            case "⃡":
                return "\\overleftrightarrow{"
            case "⃐":
                return "\\overset{\\leftharpoonup}{"
            case "⃑":
                return "\\overset{\\rightharpoonup}{"
            case _:
                return "\\overrightarrow{"


@dataclass
class OfficeMathGroupCharacter(OfficeMathElement):
    accent_prefix: str = "\\underbrace{"
    accent_postfix: str = "}"

    def process(self, chr_: str = "") -> str:
        math_string = ""
        for el in self.node:
            if el.tag == qname("m", "groupChrPr"):
                pos_elems = el.findall(qname("m", "pos"))
                for gpr in el:
                    if gpr.tag == qname("m", "chr"):
                        val = gpr.get(qname("m", "val"))
                        if len(pos_elems) == 1:
                            self.accent_prefix = self.get_accent_operator_top(val)
                        else:
                            self.accent_prefix = self.get_accent_operator_bottom(val)
            if el.tag == qname("m", "e"):
                math_string += OfficeMathNode(el).process(chr_)
        return f"{self.accent_prefix}{math_string}{self.accent_postfix}"

    def get_accent_operator_top(self, val: Optional[str]) -> str:
        match val:
            case "⏞":
                self.accent_postfix = "}"
                return "\\overbrace{"
            case "←":
                self.accent_postfix = "}"
                return "\\overset{\\leftarrow}{"
            case "→":
                self.accent_postfix = "}"
                return "\\overset{\\rightarrow}{"
            case "⇐":
                self.accent_postfix = "}"
                return "\\overset{\\Leftarrow}{"
            case "⇒":
                self.accent_postfix = "}"
                return "\\overset{\\Rightarrow}{"
            case "↔":
                self.accent_postfix = "}"
                return "\\overset{\\leftrightarrow}{"
            case "⇔":
                self.accent_postfix = "}"
                return "\\overset{\\Leftrightarrow}{"
            case _:
                self.accent_postfix = "}"
                return "{"

    def get_accent_operator_bottom(self, val: Optional[str]) -> str:
        match val:
            case "←":
                self.accent_postfix = "}{\\leftarrow}"
                return "\\overset{"
            case "→":
                self.accent_postfix = "}{\\rightarrow}"
                return "\\overset{"
            case "⇐":
                self.accent_postfix = "}{\\Leftarrow}"
                return "\\overset{"
            case "⇒":
                self.accent_postfix = "}{\\Rightarrow}"
                return "\\overset{"
            case "↔":
                self.accent_postfix = "}{\\leftrightarrow}"
                return "\\overset{"
            case "⇔":
                self.accent_postfix = "}{\\Leftrightarrow}"
                return "\\overset{"
            case _:
                self.accent_postfix = "}"
                return "{"


@dataclass
class OfficeMathBar(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        accent_string = "\\underline{"
        math_string = ""
        for el in self.node:
            if el.tag == qname("m", "barPr"):
                for bpr in el:
                    if bpr.tag == qname("m", "pos"):
                        val = bpr.get(qname("m", "val"))
                        if val == "top":
                            accent_string = "\\overline{"
            elif el.tag == qname("m", "e"):
                math_string += OfficeMathNode(el).process(chr_)
        opens = accent_string.count("{")
        closes = accent_string.count("}")
        return accent_string + math_string + ("}" * (opens - closes))


@dataclass
class OfficeMathRadical(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        math_string = "\\sqrt"
        for el in self.node:
            if el.tag == qname("m", "deg"):
                math_string += "[" + OfficeMathNode(el).process(chr_) + "]"
            elif el.tag == qname("m", "e"):
                math_string += "{" + OfficeMathNode(el).process(chr_) + "}"
        return math_string


@dataclass
class OfficeMathEquationArray(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        math_string = "\\begin{aligned}\n"
        for el in self.node:
            if el.tag == qname("m", "e"):
                math_string += f"{OfficeMathNode(el).process(chr_)} \\\\ \n"
        # Replace leading alignment spaces: " &" -> "\\ \\ &"
        math_string = re.sub(r" &", r"\\ \\ &", math_string)
        if math_string.endswith(" \\\\ \n"):
            math_string = math_string[:-5] + "\n"
        return math_string + "\\end{aligned} "


@dataclass
class OfficeMathSPre(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        math_string = ""
        for el in self.node:
            if el.tag == qname("m", "sub"):
                math_string += "_{" + OfficeMathNode(el).process(chr_) + "}"
            elif el.tag == qname("m", "sup"):
                math_string += "^{" + OfficeMathNode(el).process(chr_) + "}"
            elif el.tag != qname("m", "ctrlPr"):
                math_string += OfficeMathNode(el).process(chr_)
        return math_string


@dataclass
class OfficeMathText(OfficeMathElement):
    def process(self, chr_: str = "") -> str:
        text_content = (self.node.text or "").strip()
        if self.node.get(qname("xml", "space")) == "preserve":
            return "\\ \\ " if text_content == "" else OfficeMathFieldCodeText(text_content).process(chr_)
        else:
            return text_content


@dataclass
class OfficeMathFieldCodeText:
    math_text: str

    def process(self, chr_: str = "") -> str:
        # Cancel patterns: eq \\o(...,/)
        cancel_match1 = re.search(r"eq \\o\s?\((.*?),\/\)", self.math_text, re.IGNORECASE)
        cancel_match2 = re.search(r"eq \\o\s?\((.*?),／\)", self.math_text, re.IGNORECASE)
        overline_match = re.search(r"eq \\x\s?\\to \((.*?)\)", self.math_text, re.IGNORECASE)

        if cancel_match1:
            return f"\\cancel{{{cancel_match1.group(1)}}}"
        if cancel_match2:
            return f"\\cancel{{{cancel_match2.group(1)}}}"
        if overline_match:
            return f"\\overline{{{overline_match.group(1)}}}"

        return self.math_text


__all__ = [
    "process_math_string",
    "process_math_node",
]
