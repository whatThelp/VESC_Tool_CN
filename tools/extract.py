# -*- coding: utf-8 -*-
"""抽出 res/config/<ver>/*.xml 里所有可翻译文本片段。
只碰 <longName>/<enumNames>/<description>；description 内只碰转义 HTML 的文本节点
（既不含 &lt; 也不含 &gt; 的连续片段），标签、style、转义全部原样保留。"""
import re, json, sys, os, hashlib

NODE_RE  = re.compile(r'<(longName|enumNames|description)>(.*?)</\1>', re.S)
TEXT_RE  = re.compile(r'(?<=&gt;)((?:(?!&lt;)(?!&gt;).)+)(?=&lt;)', re.S)
PARAM_RE = re.compile(r'^[ \t]*<([A-Za-z_][A-Za-z0-9_.]*)>[ \t]*$', re.M)
CSS_RE   = re.compile(r'\{[^}]*\}')
SKIP_PARAMS = {'gpl_text', 'ios_license_text'}   # 许可证正文保持英文

def is_translatable(c):
    if not c.strip():                      return False
    if not re.search(r'[A-Za-z]{2}', c):   return False
    if CSS_RE.search(c):                   return False
    if 'white-space' in c or 'font-family' in c:  return False
    return True

def scan(path):
    src = open(path, encoding='utf-8').read()
    opens = [(m.start(), m.group(1)) for m in PARAM_RE.finditer(src)]
    def owner(pos):
        lo, hi, best = 0, len(opens) - 1, ''
        while lo <= hi:
            mid = (lo + hi) // 2
            if opens[mid][0] <= pos: best = opens[mid][1]; lo = mid + 1
            else: hi = mid - 1
        return best
    items = []
    for m in NODE_RE.finditer(src):
        tag, body, off = m.group(1), m.group(2), m.start(2)
        par = owner(m.start())
        if par in SKIP_PARAMS:
            continue
        if tag in ('longName', 'enumNames'):
            spans = [(0, len(body), body)] if is_translatable(body) else []
        else:
            spans = [(t.start(1), t.end(1), t.group(1)) for t in TEXT_RE.finditer(body)
                     if is_translatable(t.group(1))]
        for s, e, t in spans:
            items.append({'param': par, 'tag': tag, 'start': off + s, 'end': off + e, 'text': t})
    return items

if __name__ == '__main__':
    cfgdir, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    index, freq = {}, {}
    for f in ('parameters_mcconf.xml', 'parameters_appconf.xml', 'info.xml'):
        items = scan(os.path.join(cfgdir, f))
        index[f] = items
        for it in items:
            freq[it['text']] = freq.get(it['text'], 0) + 1
    json.dump(index, open(os.path.join(outdir, 'index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    uniq = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    json.dump([{'id': hashlib.md5(t.encode()).hexdigest()[:10], 'n': n, 'text': t}
               for t, n in uniq],
              open(os.path.join(outdir, 'segments.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'片段 {sum(freq.values())} 处，去重 {len(uniq)} 条，共 {sum(len(t) for t,_ in uniq)} 字符')
    for f in index: print(f'  {f}: {len(index[f])} 处')
