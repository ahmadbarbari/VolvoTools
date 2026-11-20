#!/usr/bin/env python3
"""
Volvo P1 (C30/S40/V50/C70) Bosch ME9.0 - checksum checker / corrector.  v3 (2026-11-14)

Verified on a 2008 C30 T5 stock read (HW 0261209038, SW P010D600 / S13190):
all 54 code blocks and all 6 calibration blocks match. The calibration table is found by
structure, and the same algorithm also validates a 2006 Volvo P010BB00 (0261209009) file,
a 2011 C30 P010E500 file and Ford Focus RS ME9.0C files.

TWO tables, same entry format (16 bytes, BIG-endian u32: start, end INCLUSIVE, sum, ~sum),
same sum (32-bit total of 16-bit BIG-endian words from start to end inclusive):

  1. CODE table at file 0x0A0000 - 0x0A0360. Addresses are file offsets.
     Covers 0x020000-0x1BFFFF and 0x1F0000-0x1FFFFF.

  2. CALIBRATION table (new in v3). It sits INSIDE the calibration, in the function-
     monitoring block, and is found by scanning 0x1C2000-0x1DFFFF for consecutive valid
     entries. Addresses are CPU addresses (file offset + 0x400000).
     On P010D600 it is at file 0x1CA9E0, 6 entries, covering 0x1C2000-0x1C34FF and
     0x1C4320-0x1DFFFF. EVERY map lives in these ranges, so any tune changes them.
     A block may contain its own entry: because sum and ~sum are stored together, the
     pair always adds the same constant, so the result is stable.

  v2 of this script said the calibration had no known checksum. That was wrong; the
  table was found by comparing an original and a checksum-corrected tuned Ford Focus RS
  ME9.0C file (same table format, verified on 4 files from 3 software versions).

NOTE: VolvoTools (prometey1982 and the Najiy fork, as of 2026-11) reads the code table as
little-endian, finds no valid entry, and neither checks nor corrects anything on P1 ME9.
Always fix checksums with THIS script before flashing a modified file.

NOT covered by either table: 0x000000-0x01FFFF (boot, never written by the flasher),
0x1C3500-0x1C431F and 0x1E0000-0x1EFFFF.

Usage:
  python me9_p1_checksum.py stock.bin                  # check only
  python me9_p1_checksum.py tuned.bin --fix out.bin    # correct and write a NEW file
"""
import argparse, hashlib, struct, sys

CODE_TABLE = (0x0A0000, 0x0A0360)
CAL_SCAN = (0x1C2000, 0x1E0000)
CAL_BASE = 0x400000
SIZE = 0x200000


def code_entries(d):
    i = CODE_TABLE[0]
    while i < CODE_TABLE[1]:
        s, e, cs, cc = struct.unpack_from(">IIII", d, i)
        if s >= len(d) or e >= len(d) or e < s:
            break
        yield i, s, e, cs, cc
        i += 16


def _cal_entry(d, i):
    s, e, cs, cc = struct.unpack_from(">IIII", d, i)
    lo, hi = CAL_SCAN[0] + CAL_BASE, CAL_SCAN[1] + CAL_BASE
    # A real entry always stores a sum together with its complement. That relation
    # survives data edits (the pair is only ever rewritten together), and it is what
    # separates the checksum table from ordinary pointer tables in the calibration.
    if lo <= s < e < hi and (e - s + 1) % 2 == 0 and e - s >= 0xFF and (cs ^ cc) == 0xFFFFFFFF:
        return s - CAL_BASE, e - CAL_BASE, cs, cc
    return None


def find_cal_table(d):
    """Return the file offset of the calibration checksum table, or None.
    The table is located by STRUCTURE (address pairs plus sum/complement pairs),
    not by whether the sums are currently right, so it is still found after the
    data has been modified."""
    best, i = None, CAL_SCAN[0]
    while i < CAL_SCAN[1] - 16:
        n = 0
        while _cal_entry(d, i + 16 * n):
            n += 1
        if n >= 3 and (best is None or n > best[1]):
            best = (i, n)
        i += 16 * n if n else 1
    return best


def cal_entries(d):
    t = find_cal_table(d)
    if not t:
        return
    for k in range(t[1]):
        i = t[0] + 16 * k
        s, e, cs, cc = _cal_entry(d, i)
        yield i, s, e, cs, cc


def calc(d, s, e):
    return sum(struct.unpack_from(">%dH" % ((e - s + 1) // 2), d, s)) & 0xFFFFFFFF


def check(d, verbose=True):
    ok, n = True, {"code": 0, "cal": 0}
    for kind, it in (("code", code_entries(d)), ("cal", cal_entries(d))):
        for i, s, e, cs, cc in it:
            n[kind] += 1
            c = calc(d, s, e)
            good = c == cs and cc == (~c & 0xFFFFFFFF)
            ok &= good
            if verbose or not good:
                print(f"  {kind:4s} @0x{i:06X}  0x{s:06X}-0x{e:06X}  stored {cs:08X}  calc {c:08X}  {'OK' if good else 'BAD'}")
    return ok, n


def fix(d):
    for _ in range(6):  # a block can contain a table entry
        for it in (cal_entries, code_entries):
            for i, s, e, _cs, _cc in list(it(d)):
                c = calc(d, s, e)
                struct.pack_into(">II", d, i + 8, c, ~c & 0xFFFFFFFF)
        if check(d, False)[0]:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bin")
    ap.add_argument("--fix", metavar="OUT")
    ap.add_argument("-q", action="store_true", help="only print bad blocks")
    a = ap.parse_args()
    d = bytearray(open(a.bin, "rb").read())
    print(f"File: {a.bin}  size 0x{len(d):X}  sha256 {hashlib.sha256(d).hexdigest()[:16]}...")
    if len(d) != SIZE:
        sys.exit("Unsupported size - expected a full 2 MB P1 ME9 read.")
    ok, n = check(d, not a.q)
    if n["code"] == 0:
        sys.exit("No code checksum entries found - unknown layout, do NOT flash.")
    if n["cal"] == 0:
        sys.exit("No calibration checksum table found - unknown layout, do NOT flash.")
    print(f"{n['code']} code blocks + {n['cal']} calibration blocks: " + ("ALL OK" if ok else "CHECKSUM MISMATCH"))
    if a.fix:
        if not fix(d):
            sys.exit("Could not converge - nothing written.")
        orig = open(a.bin, "rb").read()
        allowed = set()
        for it in (cal_entries, code_entries):
            for i, *_ in it(d):
                allowed.update(range(i + 8, i + 16))
        stray = [i for i in range(SIZE) if d[i] != orig[i] and i not in allowed]
        if stray:
            sys.exit(f"Internal error: fix touched bytes outside the checksum fields (first 0x{stray[0]:06X}) - nothing written.")
        open(a.fix, "wb").write(d)
        print(f"Corrected file written: {a.fix}")


if __name__ == "__main__":
    main()
