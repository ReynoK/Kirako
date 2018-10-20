import mistune
import re
import datetime

from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import html

example = r"""Date: 2018-09-08 00:00:01
tag: Linux Python python
category: 技术
title: 测试文章

今天在整社团的一些杂碎事务，其中需要打印若干个PDF文档，到打印店一个个文件来打印显然比较麻烦，所以我在思考，有没有把多个PDF合并为一个的操作呢？

想到 Unix 命令强大的数据处理能力，猜测大概也有类似的合并PDF文件的操作？随手 Google 了关键字 `Linux PDF merge`，发现 StackOverflow 的[一篇帖子](https://stackoverflow.com/questions/2507766/merge-convert-multiple-pdf-files-into-one-pdf)。
![41849-evm6cvoqsao.png]()

<!--more-->

试着运行了一下 <code>pdfunite</code>，还真有！所以说生活在 Linux 的世界中常常可以遇到很多惊喜的嘛:D

```
import os
imoprt datetime 

print("hello,world")
```

发现我最近也记录了不少这样的 Linux 世界中的小惊喜，所以还是很推荐看到这篇碎碎念的你，学习一下 Unix 命令的，真的十分灵活和实用。"
"""

META = re.compile(r'^(?P<key>\w+):\s(?P<value>.+?)\n')
BRIEF = re.compile(r'<!--more-->', re.M)
SEPERATE = re.compile(r'^=+\n')

class HighlightRenderer(mistune.Renderer):
    def block_code(self, code, lang):
        if not lang:
            return '\n<pre><code>%s</code></pre>\n' % \
                mistune.escape(code)
        lexer = get_lexer_by_name(lang, stripall=True)
        formatter = html.HtmlFormatter()
        return highlight(code, lexer, formatter)

def parse_post(text):
    """Parse the given text into metadata and strip it for a Markdown parser.
    :param text: text to be parsed
    """
    m = META.match(text)
    
    parse_result = dict()

    while m:
        key = m.group('key')
        value = m.group('value').strip()
        if key.lower() == "date":
            parse_result['date'] = datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        elif key.lower() == "tag":
            tag_list = value.split()
            parse_result['tag'] = [tag.strip() for tag in tag_list]
        else:
            parse_result[key.lower()] = value.strip()

        text = text[len(m.group(0)):]
        m = META.match(text)
    text = SEPERATE.sub("", text, 1).strip()
    m = BRIEF.search(text)
    if m:
        parse_result["description"] = text[:m.start(0)] 
    else:
        parse_result["description"] = ""
    parse_result["content"] = BRIEF.sub("", text, 1).strip()
    return parse_result

def analyze_post(content):
    renderer = HighlightRenderer()
    markdown = mistune.Markdown(renderer=renderer, hard_wrap=True)

    post_compoment = parse_post(content)
    post_compoment["content"] = markdown(post_compoment["content"])
    post_compoment["description"] = markdown(post_compoment["description"])
    
    return post_compoment
