"""Audit CSS: kelas non-Tailwind yang dipakai di JSX tetapi TIDAK punya aturan CSS (gaya terlewat)."""
import glob
import re
from collections import defaultdict

SRC = "/app/frontend/src"
TW = re.compile(r"^-?(?:[a-z]+:)*-?(?:p[xytrbl]?|m[xytrbl]?|w|h|min|max|flex|grid|gap|space|text|font|leading|tracking|bg|border|rounded|shadow|ring|outline|opacity|z|top|left|right|bottom|inset|overflow|truncate|whitespace|break|items|justify|self|place|content|order|col|row|basis|grow|shrink|object|cursor|select|pointer|transition|duration|ease|delay|animate|transform|translate|rotate|scale|skew|origin|fill|stroke|sr|not|block|inline|hidden|table|contents|list|absolute|relative|fixed|sticky|static|visible|invisible|underline|line|no|uppercase|lowercase|capitalize|normal|italic|antialiased|tabular|ordinal|aspect|columns|divide|from|via|to|backdrop|blur|filter|drop|decoration|indent|align|resize|appearance|accent|caret|scroll|snap|touch|will|isolate|mix|container|first|last|odd|even|group|peer|placeholder|hover|focus|active|disabled|sm|md|lg|xl|2xl|dark|print|clip|float|clear|box|size|line-clamp|shrink-0|grow-0|bg-gradient|prose|mx|my|ms|me|ps|pe)(?:-|$|\[)")
cls_use = defaultdict(set)
for f in glob.glob(f"{SRC}/**/*.jsx", recursive=True) + glob.glob(f"{SRC}/**/*.js", recursive=True):
    if "/components/ui/" in f:
        continue
    txt = open(f, encoding="utf8").read()
    for m in re.finditer(r'className=(?:"([^"]+)"|\{`([^`]+)`\})', txt):
        s = re.sub(r"\$\{[^}]*\}", " ", m.group(1) or m.group(2))
        for c in s.split():
            if re.match(r"^[a-z][a-z0-9-]*$", c) and not TW.match(c) and len(c) > 2:
                cls_use[c].add(f.replace(SRC + "/", ""))
css = " ".join(open(f, encoding="utf8").read() for f in glob.glob(f"{SRC}/**/*.css", recursive=True))
defined = set(re.findall(r"\.([a-zA-Z][\w-]*)", css))
missing = {c: sorted(fs) for c, fs in cls_use.items() if c not in defined}
for c, fs in sorted(missing.items(), key=lambda x: -len(x[1])):
    print(f"{c} ({len(fs)}): {', '.join(fs[:3])}")
print("TOTAL custom classes:", len(cls_use), "| tanpa CSS:", len(missing))
