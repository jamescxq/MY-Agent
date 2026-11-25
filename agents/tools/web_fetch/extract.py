import re
from html.parser import HTMLParser

# 把网页的 HTML 变成纯文字。只用 Python 自带的 html.parser，不装别的包。
# 做得很朴素：去掉脚本和样式，把剩下的文字按段落拼起来。排版复杂的网页会带上一些菜单、页脚的字。

SKIP = ("script", "style", "noscript", "template", "svg", "head")       # 这些标签里的东西不是给人看的正文
BLOCK = ("p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "blockquote", "pre", "table", "ul", "ol")


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.title = ""
        self.skipping = 0           # 现在在几层"不要的标签"里面
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        elif tag in SKIP:
            self.skipping += 1
        elif tag in BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag in SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag in BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skipping:
            self.parts.append(data)


def html_to_text(html):
    """返回 (标题, 正文)。正文里每段一行，多余的空格和空行去掉。"""
    parser = TextOnly()
    parser.feed(html)
    parser.close()
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return " ".join(parser.title.split()), "\n".join(line for line in lines if line)


def decode(body, content_type=""):
    """把下载来的字节变成文字。先看服务器说的编码，再看网页自己写的，都没有就按 UTF-8，不行再试中文网页常用的 GB18030。"""
    found = re.search(r"charset=([\w-]+)", content_type, re.I) or re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", body[:4096], re.I)
    names = []
    if found:
        name = found.group(1)
        names.append(name.decode("ascii", "ignore") if isinstance(name, bytes) else name)
    names += ["utf-8", "gb18030"]
    for name in names:
        try:
            return body.decode(name)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


if __name__ == "__main__":
    page = """<html><head><title> 测试  页面 </title><style>p{color:red}</style></head>
    <body><script>alert('不该出现')</script><h1>大标题</h1><p>第一段，有&amp;符号。</p>
    <div>第二段 <b>加粗</b>   很多空格</div><ul><li>一</li><li>二</li></ul></body></html>"""
    title, text = html_to_text(page)
    print(repr(title))                  # 应该：'测试 页面'
    print(text)                         # 应该：大标题 / 第一段，有&符号。/ 第二段 加粗 很多空格 / 一 / 二，没有脚本和样式里的字
    print(decode("中文".encode("gbk"), "text/html; charset=gbk"), decode("中文".encode("gb18030")), decode("中文".encode("utf-8")))   # 应该：三个都是 中文
