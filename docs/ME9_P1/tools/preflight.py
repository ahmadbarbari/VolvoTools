#!/usr/bin/env python3
"""Pre-flight check for a Volvo P1 Bosch ME9.0 file, run before EVERY flash.

Checks:
  1. size is exactly 2 MB and the ID block looks like ME9.0 (contains "ME90")
  2. both checksum tables are correct (54 code + calibration blocks, me9_p1_checksum.py)
  3. with --stock: every byte that differs from your stock read lies in an area the
     flasher really writes (0x020000-0x08FFFF, 0x0A0000-0x1EFFFF). Changes in the boot
     area, the gap 0x090000-0x09FFFF or the tail 0x1F0000-0x1FFFFF would NOT be written.
  4. with --expected OUT: writes the image the VolvoTools dry run should emit
     (your file with 0x000000-0x01FFFF and 0x090000-0x09FFFF set to 0xFF).

Exit code 0 = all good, 1 = do not flash.
Usage: python preflight.py file.bin [--stock stock_read.bin] [--expected expected.bin]
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import me9_p1_checksum as ck

WRITTEN = [(0x020000, 0x090000), (0x0A0000, 0x1F0000)]
NOT_IN_IMAGE = [(0x000000, 0x020000), (0x090000, 0x0A0000)]

def written(i):
    return any(a <= i < b for a, b in WRITTEN)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bin"); ap.add_argument("--stock"); ap.add_argument("--expected")
    a = ap.parse_args()
    d = bytearray(open(a.bin, "rb").read())
    bad = False
    if len(d) != ck.SIZE:
        print(f"FAIL size is {len(d)} bytes, expected {ck.SIZE}"); return 1
    ident = bytes(d[0x1C0000:0x1E0000])
    k = ident.find(b"/ME90")
    if k < 0:
        print("FAIL no ME9.0 ID string found in the calibration area"); bad = True
    else:
        b = k
        while b > 0 and 32 <= ident[b - 1] < 127:
            b -= 1
        e = k
        while e < len(ident) and 32 <= ident[e] < 127:
            e += 1
        print("ID       :", ident[b:e].decode("latin-1"))
    ok, n = ck.check(d, False)
    print(f"Checksum : {n['code']} code + {n['cal']} calibration blocks: " + ("ALL OK" if ok and n['code'] and n['cal'] else "NOT OK"))
    if not (ok and n["code"] and n["cal"]):
        print("FAIL run: python me9_p1_checksum.py <file> --fix <new file>, then flash the new file"); bad = True
    if a.stock:
        st = open(a.stock, "rb").read()
        if len(st) != ck.SIZE:
            print("FAIL stock file is not 2 MB"); return 1
        diff = [i for i in range(ck.SIZE) if d[i] != st[i]]
        outside = [i for i in diff if not written(i)]
        print(f"vs stock : {len(diff)} bytes differ, {len(outside)} outside the areas the flasher writes")
        if outside:
            print(f"FAIL first unwritable change at 0x{outside[0]:06X}"); bad = True
        if st[0x1C34B0:0x1C3500] != d[0x1C34B0:0x1C3500]:
            print("NOTE the ID block differs from your stock read - is this file for YOUR software version?")
    if a.expected and not bad:
        e = bytearray(d)
        for lo, hi in NOT_IN_IMAGE:
            e[lo:hi] = b"\xFF" * (hi - lo)
        open(a.expected, "wb").write(e)
        print("Expected dry-run image written:", a.expected)
    print("RESULT   :", "DO NOT FLASH" if bad else "OK to dry-run")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
