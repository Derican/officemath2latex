import sys
import argparse
from lxml import etree
from officemath2latex import process_math_string, process_math_node, qname, NS


def _process_root_text(xml_text: str) -> str:
    try:
        # 尝试按单一根节点解析
        return process_math_string(xml_text)
    except etree.XMLSyntaxError:
        # 可能是多个并列片段，包一层 root 再解析
        wrapped = f'<root xmlns:m="{NS["m"]}">{xml_text}</root>'
        root = etree.fromstring(wrapped.encode("utf-8"))
        out = []
        # 依次查找所有 OfficeMath 片段
        for el in root.iter():
            if isinstance(el.tag, str) and (el.tag.startswith("{" + NS["m"] + "}") or el.tag == "oMath"):
                # 对每个 OMML 元素做一次转换
                try:
                    out.append(process_math_node(el))
                except Exception:
                    # 忽略非数学节点或无法识别的节点
                    pass
        return "\n".join([s for s in out if s])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert Office Math (OMML) XML to LaTeX")
    parser.add_argument("xml", nargs="?", default="test.xml", help="Input OfficeMath XML file (default: test.xml)")
    args = parser.parse_args(argv)

    try:
        with open(args.xml, "r", encoding="utf-8") as f:
            xml_text = f.read()
    except OSError as e:
        print(f"读取失败: {e}", file=sys.stderr)
        return 1

    try:
        latex = _process_root_text(xml_text)
    except Exception as e:
        print(f"解析失败: {e}", file=sys.stderr)
        return 2

    print(latex)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
