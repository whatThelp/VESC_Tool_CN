# -*- coding: utf-8 -*-
"""第二阶段抽取：.ui / .qml / .cpp 里的界面可见字符串。

设计原则和第一阶段一样 —— 记录"要替换的那一段字节"的绝对偏移，回填时只动那一段，
其余内容逐字节保留，因此 diff 干净、不会破坏结构。
"""
import re, os, sys, json, hashlib

# ---------------- .ui ----------------
# 只翻这些 property；objectName / styleSheet / shortcut / 数值属性一律不碰
UI_PROPS = {'text', 'toolTip', 'statusTip', 'whatsThis', 'title',
            'windowTitle', 'placeholderText', 'iconText'}
# 只匹配无属性的 <string>：这样自然跳过 <string notr="true"> 和自闭合的 <string/>
UI_PROP_RE = re.compile(
    r'<property name="([a-zA-Z]+)"\s*>\s*<string>(.*?)</string>', re.S)
UI_ATTR_RE = re.compile(
    r'<attribute name="(title|toolTip)"\s*>\s*<string>(.*?)</string>', re.S)

# ---------------- .qml ----------------
QML_PROPS = ('text', 'title', 'placeholderText', 'label', 'description')
QML_LINE_RE = re.compile(
    r'^([ \t]*(?:%s|ToolTip\.text)[ \t]*:[ \t]*")([^"\\\n]*)(")'
    % '|'.join(QML_PROPS), re.M)
# VescIf.emitMessageDialog("标题", "正文", ...) —— 前两个参数是可见文本
QML_DLG_RE = re.compile(r'(emitMessageDialog\(\s*")([^"\\\n]*)(")')

# ---------------- .cpp ----------------
CPP_CALLS = ('emitMessageDialog', 'emitStatusMessage', 'setWindowTitle',
             'setToolTip', 'setStatusTip', 'setPlaceholderText', 'setLabelText',
             'showMessage', 'setTitle', 'setSubTitle', 'setText', 'addItem',
             'addTab', 'insertItem', 'setInformativeText', 'setDetailedText',
             'setButtonText', 'setWhatsThis', 'setNameFilter')
# 控件构造函数里的可见文本：new QCheckBox("...") 之类
CPP_CTORS = ('QCheckBox', 'QPushButton', 'QLabel', 'QRadioButton', 'QGroupBox',
             'QAction', 'QToolButton', 'QCommandLinkButton')
CPP_CALL_RE = re.compile(
    r'(?:(?:%s)\(\s*(?:tr\()?|new\s+(?:%s)\(\s*(?:tr\()?)"'
    % ('|'.join(CPP_CALLS), '|'.join(CPP_CTORS)))
CPP_BOX_RE = re.compile(
    r'QMessageBox::(?:information|warning|critical|question)\s*\([^,]*,\s*"')
STR_RE = re.compile(r'"((?:[^"\\\n]|\\.)*)"')

IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
NUMISH_RE = re.compile(r'^[\d\s.,:%+\-/()]*$')


def translatable(t):
    s = t.strip()
    if not s:
        return False
    if not re.search(r'[A-Za-z]{2}', s):
        return False
    if NUMISH_RE.match(s):
        return False
    if s.startswith(('qrc:', 'http', ':/', '#')):
        return False
    if '\\n' in s and len(s) < 4:
        return False
    return True


# 转义 HTML 富文本里的文本节点（既不含 &lt; 也不含 &gt; 的连续片段），和第一阶段同款
HTML_TEXT_RE = re.compile(r'(?<=&gt;)((?:(?!&lt;)(?!&gt;).)+)(?=&lt;)', re.S)
CSS_RE = re.compile(r'\{[^}]*\}')
# QAction 的内部名（图标按钮真正显示的是 toolTip），形如 readMcconf / canFwd
INTERNAL_RE = re.compile(r'^[a-z][A-Za-z0-9]*$')


def _ui_spans(body, off, prop):
    """富文本只取文本节点，普通文本整段取"""
    if '&lt;' in body:
        out = []
        for t in HTML_TEXT_RE.finditer(body):
            s = t.group(1)
            if (ui_translatable(s) and not CSS_RE.search(s)
                    and 'white-space' not in s and 'font-family' not in s):
                out.append((off + t.start(1), off + t.end(1), s, prop + '/html'))
        return out
    if prop == 'text' and INTERNAL_RE.match(body.strip()):
        return []
    return [(off, off + len(body), body, prop)]


def ui_translatable(t):
    # .ui 的字符串内容是转义过的，出现裸 < 说明抽歪了（C++/QML 里 <br> 是合法文本）
    return translatable(t) and '<' not in t


def scan_ui(path, src):
    out = []
    for m in UI_PROP_RE.finditer(src):
        if m.group(1) in UI_PROPS and ui_translatable(m.group(2)):
            out += _ui_spans(m.group(2), m.start(2), m.group(1))
    for m in UI_ATTR_RE.finditer(src):
        if ui_translatable(m.group(2)):
            out += _ui_spans(m.group(2), m.start(2), 'attr:' + m.group(1))
    return out


WS_PLUS_STR = re.compile(r'[\s]*\+[\s]*"((?:[^"\\\n]|\\.)*)"')   # QML: "a" + "b"
WS_STR = re.compile(r'[\s]*"((?:[^"\\\n]|\\.)*)"')               # C++: "a" "b"


def _continuations(src, pos, rx, kind, out, limit=40):
    """把跨行拼接的字符串字面量也一并收进来，否则只翻半句"""
    for _ in range(limit):
        m = rx.match(src, pos)
        if not m:
            break
        if translatable(m.group(1)):
            out.append((m.start(1), m.end(1), m.group(1), kind))
        pos = m.end()
    return pos


def scan_qml(path, src):
    out = []
    for m in QML_LINE_RE.finditer(src):
        if translatable(m.group(2)):
            out.append((m.start(2), m.end(2), m.group(2), 'qml-prop'))
        _continuations(src, m.end(3), WS_PLUS_STR, 'qml-prop', out)
    for m in QML_DLG_RE.finditer(src):
        if translatable(m.group(2)):
            out.append((m.start(2), m.end(2), m.group(2), 'qml-dialog'))
        _continuations(src, m.end(3), WS_PLUS_STR, 'qml-dialog', out)
    return out


CPP_TR_RE = re.compile(r'\btr\(\s*"((?:[^"\\\n]|\\.)*)"')


def scan_cpp(path, src):
    """在目标调用之后取紧跟的字符串字面量（第一个，以及 emitMessageDialog 的第二个）；
    另外单独扫 tr("...") —— Qt 里这就是"这段是给用户看的"的标记。
    QCodeEditor 是第三方代码编辑器，里面的字符串是 API 补全条目，整个跳过。"""
    out = []
    if 'QCodeEditor' not in path.replace(os.sep, '/'):
        for m in CPP_TR_RE.finditer(src):
            if translatable(m.group(1)):
                out.append((m.start(1), m.end(1), m.group(1), 'cpp-tr'))
            # tr("前半句 " "后半句") —— C++ 相邻字面量自动拼接，必须一并取
            _continuations(src, m.end(), WS_STR, 'cpp-tr', out)
    starts = [(m.end() - 1, 2 if 'emitMessageDialog' in m.group(0) else 1)
              for m in CPP_CALL_RE.finditer(src)]
    starts += [(m.end() - 1, 1) for m in CPP_BOX_RE.finditer(src)]
    for pos, count in starts:
        p = pos
        for _ in range(count):
            m = STR_RE.match(src, p)
            if not m:
                break
            if translatable(m.group(1)):
                out.append((m.start(1), m.end(1), m.group(1), 'cpp'))
            # C++ 相邻字面量自动拼接："a" "b"，以及 "a" + QString(...) 之类
            end = _continuations(src, m.end(), WS_STR, 'cpp', out)
            # 跳到下一个参数的字符串
            nxt = src.find('"', end)
            comma = src.find(',', end)
            close = src.find(')', end)
            if nxt < 0 or comma < 0 or nxt > close or nxt < comma:
                break
            p = nxt
    return out


SCANNERS = {'.ui': scan_ui, '.qml': scan_qml, '.cpp': scan_cpp}


def walk(root, kinds):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ('build', '.git')]
        for f in sorted(filenames):
            ext = os.path.splitext(f)[1]
            if ext in kinds:
                yield os.path.join(dirpath, f)


def collect(root, kinds):
    index, freq, order = {}, {}, []
    for path in walk(root, kinds):
        src = open(path, encoding='utf-8').read()
        items = SCANNERS[os.path.splitext(path)[1]](path, src)
        if not items:
            continue
        rel = os.path.relpath(path, root).replace(os.sep, '/')
        index[rel] = [{'start': s, 'end': e, 'text': t, 'prop': p}
                      for (s, e, t, p) in items]
        for (s, e, t, p) in items:
            if t not in freq:
                order.append((t, rel, p))
            freq[t] = freq.get(t, 0) + 1
    return index, freq, order


if __name__ == '__main__':
    root, outdir, kinds = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
    os.makedirs(outdir, exist_ok=True)
    index, freq, order = collect(root, kinds)
    json.dump(index, open(os.path.join(outdir, 'index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    json.dump([{'id': hashlib.md5(t.encode()).hexdigest()[:10], 'n': freq[t],
                'file': f, 'prop': p, 'text': t} for (t, f, p) in order],
              open(os.path.join(outdir, 'segments.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('文件 %d 个，片段 %d 处，去重 %d 条，共 %d 字符'
          % (len(index), sum(freq.values()), len(freq), sum(len(t) for t in freq)))
