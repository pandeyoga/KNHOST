"""Daftar className non-Tailwind di berkas JSX yang tidak didefinisikan di CSS mana pun."""
import re, sys, glob, os

SRC = "/app/frontend/src"
css_text = ""
for f in glob.glob(f"{SRC}/**/*.css", recursive=True):
    css_text += open(f, encoding="utf-8").read()
defined = set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", css_text))

TW = re.compile(r"^(-?(m|p)[trblxy]?-|w-|h-|min-|max-|flex|grid|gap-|space-|text-|font-|bg-|border|rounded|shadow|items-|justify-|self-|place-|content-|col-|row-|order-|inline|block|hidden|absolute|relative|fixed|sticky|static|top-|bottom-|left-|right-|inset-|z-|overflow|truncate|whitespace|break-|leading-|tracking-|uppercase|lowercase|capitalize|italic|underline|line-|opacity-|cursor-|pointer-|select-|transition|duration-|ease-|delay-|animate-|transform|scale-|rotate-|translate-|ring|outline|divide-|sr-only|not-sr-only|object-|aspect-|shrink|grow|basis-|table|list-|align-|fill-|stroke-|from-|to-|via-|backdrop-|blur|filter|container|isolate|visible|invisible|tabular-nums|antialiased|appearance-|resize|snap-|scroll-|touch-|will-|decoration-|indent-|columns-|float-|clear-|box-|sm:|md:|lg:|xl:|2xl:|hover:|focus|active:|disabled:|group|peer|data-|dark:|first:|last:|odd:|even:|placeholder|file:|print:|\[|!|size-|accent-|caret-|mix-|ordinal|slashed|lining|oldstyle|proportional|diagonal|stacked|normal-|not-|last-|first-|mt|mb|ml|mr|px|py|pt|pb|pl|pr|sr-)")

files = sys.argv[1:] or glob.glob(f"{SRC}/features/**/*.jsx", recursive=True)
out = {}
for f in files:
    txt = open(f, encoding="utf-8").read()
    for m in re.finditer(r'className=(?:"([^"]*)"|\{`([^`]*)`\}|\{"([^"]*)"\})', txt):
        s = m.group(1) or m.group(2) or m.group(3) or ""
        s = re.sub(r"\$\{[^}]*\}", " ", s)
        for c in s.split():
            if TW.match(c) or c in defined or not re.match(r"^[a-zA-Z][\w-]*$", c):
                continue
            out.setdefault(c, set()).add(os.path.relpath(f, SRC))
for c in sorted(out):
    print(c, "->", ", ".join(sorted(out[c]))[:200])
print("TOTAL", len(out))
