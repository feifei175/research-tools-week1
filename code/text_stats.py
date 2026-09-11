# code/text_stats.py
"""文本词频统计工具（仅使用 Python 标准库）。

用法示例（在项目根目录执行）：
    python code/text_stats.py report/week1.md
    python code/text_stats.py report/week1.md --top 5
    Get-Content report/week1.md | python code/text_stats.py
"""

import argparse
import re
import sys
from collections import Counter

# 一个“英文单词”：字母或数字开头，中间可以夹撇号，例如 don't
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)*")
# 一个汉字
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
# 常见字节序标记（BOM）对应的编码，用来判断文件的真实编码
BOM_ENCODINGS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32"),
    (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe", "utf-16"),
    (b"\xfe\xff", "utf-16"),
)


def decode_bytes(data, encoding="auto"):
    """把字节解码成文本。

    encoding="auto" 时先看文件开头的 BOM 判断编码，没有 BOM 就按 UTF-8
    处理，因此 UTF-8、带 BOM 的 UTF-8、Windows 记事本的 UTF-16 文件都能读。
    """
    if encoding in (None, "auto"):
        for bom, name in BOM_ENCODINGS:
            if data.startswith(bom):
                return data.decode(name)
        encoding = "utf-8"
    return data.decode(encoding)


def read_text(path, encoding="auto"):
    """读取文本；path 为 None 或 "-" 时从标准输入读取。"""
    if path is None or path == "-":
        return decode_bytes(sys.stdin.buffer.read(), encoding)
    with open(path, "rb") as fp:
        return decode_bytes(fp.read(), encoding)


def tokenize(text, cjk=False, lower=True):
    """把文本切成单词列表。

    默认只把连续的英文字母/数字（中间可夹撇号）看作一个单词，
    并统一转成小写，所以 "The" 和 "the" 会算作同一个词。
    cjk=True 时，每个汉字单独算作一个词（中文没有空格分词）。
    """
    words = WORD_RE.findall(text)
    if lower:
        words = [w.lower() for w in words]
    if cjk:
        words += CJK_RE.findall(text)
    return words


def count_words(text, cjk=False, case_sensitive=False):
    """统计词频，返回 Counter：单词 -> 出现次数。"""
    return Counter(tokenize(text, cjk=cjk, lower=not case_sensitive))


def top_words(counter, top=10, min_count=1):
    """按次数从高到低排序；次数相同按单词字母顺序，保证输出稳定。

    top 为 0 或 None 表示不限制条数。
    """
    items = [(word, count) for word, count in counter.items() if count >= min_count]
    items.sort(key=lambda item: (-item[1], item[0]))
    if top:
        items = items[:top]
    return items


def format_stats(counter, label=None, top=10, min_count=1):
    """把统计结果整理成可以直接打印的多行文本。"""
    lines = []
    if label:
        lines.append("== {} ==".format(label))
    lines.append("总词数 {}，不同单词 {}".format(sum(counter.values()), len(counter)))
    items = top_words(counter, top=top, min_count=min_count)
    if not items:
        lines.append("(没有满足条件的单词)")
        return "\n".join(lines)
    width = max(len(word) for word, _ in items)
    lines.append("{:>6}  {}".format("次数", "单词"))
    for word, count in items:
        lines.append("{:>6}  {}".format(count, word.ljust(width)))
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(
        description="统计文本文件（或标准输入）中的单词出现频率。"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="要统计的文本文件，可以写多个；留空或写 - 表示从标准输入读取",
    )
    parser.add_argument(
        "-n", "--top",
        type=int,
        default=10,
        metavar="N",
        help="只显示出现次数最多的 N 个词，0 表示全部（默认 10）",
    )
    parser.add_argument(
        "-m", "--min-count",
        type=int,
        default=1,
        metavar="N",
        help="只显示出现次数不少于 N 的词（默认 1）",
    )
    parser.add_argument(
        "--cjk",
        action="store_true",
        help="把每个汉字单独算作一个词，用于统计中文文本",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="区分大小写，即 The 和 the 算作两个不同的词",
    )
    parser.add_argument(
        "--encoding",
        default="auto",
        help="读取文件使用的编码，默认 auto（按 BOM 自动识别，否则按 UTF-8）；读 GBK 文件可写 gbk",
    )
    return parser


def main(argv=None):
    # 控制台编码可能装不下某些字符（例如 GBK 控制台里的特殊符号），
    # 这里只把无法编码的字符替换掉，避免程序直接崩溃。
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = args.paths or ["-"]
    blocks = []
    for path in paths:
        label = "<标准输入>" if path == "-" else path
        try:
            text = read_text(path, encoding=args.encoding)
        except OSError as exc:
            print("读取 {} 失败：{}".format(label, exc), file=sys.stderr)
            return 1
        except UnicodeDecodeError:
            print(
                "解码 {} 失败：文件既没有可识别的 BOM，也不是 UTF-8，"
                "可尝试用 --encoding gbk 指定编码".format(label),
                file=sys.stderr,
            )
            return 1
        counter = count_words(text, cjk=args.cjk, case_sensitive=args.case_sensitive)
        blocks.append(
            format_stats(counter, label=label, top=args.top, min_count=args.min_count)
        )
    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
