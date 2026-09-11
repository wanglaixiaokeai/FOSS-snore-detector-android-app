#!/usr/bin/env python3
from pathlib import Path
from localize_cn import REPLACEMENTS, ROOT


def replace_chunk(chunk: str, pairs):
    hits = 0
    for old, new in pairs:
        n = chunk.count(old)
        if n:
            chunk = chunk.replace(old, new)
            hits += n
    return chunk, hits


def skip_quoted_code(text: str, i: int, quote: str) -> int:
    # i points at the opening quote. Used only while finding the end of ${...} code.
    if quote == '"""':
        end = text.find('"""', i + 3)
        return len(text) if end < 0 else end + 3
    q = quote
    i += 1
    while i < len(text):
        if text[i] == '\\':
            i += 2
            continue
        if text[i] == q:
            return i + 1
        i += 1
    return i


def skip_interpolation(text: str, i: int) -> int:
    # i points just after '${'. Returns position just after matching '}'.
    depth = 1
    while i < len(text) and depth:
        if text.startswith('"""', i):
            i = skip_quoted_code(text, i, '"""')
            continue
        c = text[i]
        if c == '"':
            i = skip_quoted_code(text, i, '"')
            continue
        if c == "'":
            i = skip_quoted_code(text, i, "'")
            continue
        if text.startswith('//', i):
            nl = text.find('\n', i + 2)
            i = len(text) if nl < 0 else nl + 1
            continue
        if text.startswith('/*', i):
            end = text.find('*/', i + 2)
            i = len(text) if end < 0 else end + 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        i += 1
    return i


def localize_regular_string(text: str, i: int, pairs):
    # i points at opening double quote. Translate literal text only; interpolation code is copied verbatim.
    out = ['"']
    hits = 0
    i += 1
    literal = []

    def flush():
        nonlocal literal, hits
        if literal:
            chunk = ''.join(literal)
            chunk, n = replace_chunk(chunk, pairs)
            hits += n
            out.append(chunk)
            literal = []

    while i < len(text):
        c = text[i]
        if c == '\\':
            if i + 1 < len(text):
                literal.append(text[i:i+2])
                i += 2
            else:
                literal.append(c)
                i += 1
            continue
        if c == '"':
            flush()
            out.append('"')
            return ''.join(out), i + 1, hits
        if c == '$':
            # ${ expression } interpolation: never translate identifiers/code inside it.
            if i + 1 < len(text) and text[i + 1] == '{':
                flush()
                end = skip_interpolation(text, i + 2)
                out.append(text[i:end])
                i = end
                continue
            # $identifier interpolation: copy identifier verbatim.
            j = i + 1
            if j < len(text) and (text[j].isalpha() or text[j] == '_'):
                flush()
                j += 1
                while j < len(text) and (text[j].isalnum() or text[j] == '_'):
                    j += 1
                out.append(text[i:j])
                i = j
                continue
        literal.append(c)
        i += 1

    flush()
    return ''.join(out), i, hits


def localize_kotlin(text: str, pairs):
    out = []
    i = 0
    hits = 0
    n = len(text)
    while i < n:
        if text.startswith('//', i):
            nl = text.find('\n', i + 2)
            if nl < 0:
                out.append(text[i:])
                break
            out.append(text[i:nl + 1])
            i = nl + 1
            continue
        if text.startswith('/*', i):
            end = text.find('*/', i + 2)
            if end < 0:
                out.append(text[i:])
                break
            out.append(text[i:end + 2])
            i = end + 2
            continue
        if text.startswith('"""', i):
            # Debug multiline/raw strings are left untouched to minimize risk.
            end = text.find('"""', i + 3)
            if end < 0:
                out.append(text[i:])
                break
            out.append(text[i:end + 3])
            i = end + 3
            continue
        if text[i] == "'":
            end = skip_quoted_code(text, i, "'")
            out.append(text[i:end])
            i = end
            continue
        if text[i] == '"':
            token, i, h = localize_regular_string(text, i, pairs)
            out.append(token)
            hits += h
            continue
        out.append(text[i])
        i += 1
    return ''.join(out), hits


def apply(path_str, pairs):
    path = ROOT / path_str
    if not path.exists():
        print(f'[skip] {path_str} not found')
        return 0
    text = path.read_text(encoding='utf-8')
    if path.suffix == '.kt':
        changed, hits = localize_kotlin(text, pairs)
    else:
        changed, hits = replace_chunk(text, pairs)
    if changed != text:
        path.write_text(changed, encoding='utf-8')
        print(f'[ok] {path_str}: {hits} safe replacements')
    else:
        print(f'[nochange] {path_str}')
    return hits


def main():
    total = 0
    for path, pairs in REPLACEMENTS.items():
        total += apply(path, pairs)
    print(f'Safe localization complete: {total} replacements inside user-visible strings')


if __name__ == '__main__':
    main()
