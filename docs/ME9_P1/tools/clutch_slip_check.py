"""Clutch slip check for the C30 T5 (M66 6-speed; edit GEARS for your gearbox). Reads a VolvoLogger CSV.
Slip = engine rpm higher than the wheels allow in the gear you are in.
Ratio = rpm / km/h. Gear is locked at the start of each load event, so a
slipping clutch (rpm flares, ratio rises) is not mistaken for a downshift.
Usage: python clutch_slip_check.py <log.csv> [more logs]"""
import csv, sys, statistics
GEARS = {1:125.0, 2:64.6, 3:42.0, 4:31.2, 5:25.4, 6:20.5}   # rpm per km/h, measured on a C30 T5 M66 with stock tyres
MIN_SPEED, MIN_LOAD, MATCH, SLIP_WARN = 15.0, 100.0, 0.03, 0.03
WINDOW, HOLD_S = 5, 0.4   # median of 5 samples; slip must last 0.4 s (filters rpm/speed timing jitter)

def col(h, key):
    for i, n in enumerate(h):
        if n.strip().endswith(key): return i
    raise SystemExit("column missing: " + key)

def nearest(r):
    g = min(GEARS, key=lambda k: abs(r/GEARS[k]-1))
    return g, r/GEARS[g]-1

def run(path):
    rows = list(csv.reader(open(path, newline="")))
    h, data = rows[0], rows[1:]
    it, ir, iv, il = col(h,"Time (sec)"), col(h,"nmot_w"), col(h,"vfzg_w"), col(h,"rl_w")
    events, cur, locked = [], None, None
    for row in data:
        try: t, rpm, v, load = (float(row[i]) for i in (it, ir, iv, il))
        except (ValueError, IndexError): continue
        if v < MIN_SPEED or load < MIN_LOAD:
            if cur: events.append(cur)
            cur, locked = None, None
            continue
        r = rpm / v
        if locked is None:
            g, err = nearest(r)
            if abs(err) > MATCH: continue          # clutch pedal down / shifting
            locked = g
        if cur is None: cur = dict(t0=t, gear=locked, peak=-1, t_peak=t, rpm=rpm, load=load, buf=[], above=None, held=0.0)
        cur["buf"] = (cur["buf"] + [r / GEARS[locked] - 1])[-WINDOW:]
        slip = statistics.median(cur["buf"])
        if slip > SLIP_WARN:
            if cur["above"] is None: cur["above"] = t
            cur["held"] = max(cur["held"], t - cur["above"])
        else: cur["above"] = None
        if slip > cur["peak"]: cur.update(peak=slip, t_peak=t, rpm=rpm, load=load)
    if cur: events.append(cur)
    print(f"\n{path}: {len(events)} high-load events")
    for e in events:
        flag = f"SLIP {e['held']:.1f}s" if e["held"] >= HOLD_S else "ok"
        print(f"  t={e['t0']:7.1f}s gear {e['gear']}  peak {e['peak']*100:+5.1f}% at t={e['t_peak']:.1f}s "
              f"{e['rpm']:.0f} rpm load {e['load']:.0f}%  [{flag}]")

for p in sys.argv[1:]: run(p)
