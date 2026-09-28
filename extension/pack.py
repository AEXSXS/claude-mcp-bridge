"""Pack extension files into a flat-structure .xpi (Firefox add-on = ZIP).

Usage:  python pack.py          (from extension/ dir, or anywhere via path)
Output: ../claude-mcp-bridge-0.1.0.xpi  (repo root)
Arcnames are the bare filenames so entries sit in the ZIP root.
"""

import os
import zipfile

FILES = ["manifest.json", "background.js", "content.js"]
VERSION = "0.6.1"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", f"claude-mcp-bridge-{VERSION}.xpi")


def pack() -> str:
    out = os.path.normpath(OUT)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            src = os.path.join(HERE, f)
            z.write(src, f)  # arcname = bare filename -> ZIP root
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    print(f"Packed: {out}")
    print(f"Entries: {names}")
    return out


if __name__ == "__main__":
    pack()
