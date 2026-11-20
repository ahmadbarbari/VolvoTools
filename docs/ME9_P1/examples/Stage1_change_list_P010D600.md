# Example: Stage 1 change list (C30 T5, P010D600, 91 AKI fuel, catless downpipe + intake, stock turbo/intercooler/injectors)

This is the exact change list of a file that ran on one car, shared as a worked example of
which maps a mild ME9.0C tune touches and why. It is NOT a file to copy blindly: it was set
from that car's own logs (knock, load, lambda, injector duty) on 91 octane, with a worn clutch.
Log your own car first (README section 6) and change one thing at a time.

```
STAGE 1 v3 for C30 T5 P010D600 - built 2026-11-15 from the verified stock read and the Stage 1 v1 logs
Checksums: 54 code blocks + 6 calibration blocks ALL OK (me9_p1_checksum.py v3).
820 bytes differ from stock, all inside the calibration. Code and boot area identical to stock.
Everything in v1 is kept unless listed below (v1 = an earlier, milder version of the same changes).

1. IGNITION  KFZW / KFZW2 / KFZWA / KFZWA2 (0x1C6E75, 0x1C6F35, 0x1C6FF5, 0x1C70B5) - timing REMOVED
   where the logs show the knock control pulling it anyway. Degrees removed, by load column:
   rpm          79.5 %  96.75 %  114 %  131.25 %  148.5 %  165.75 %
   2000         -1.5    -2.25    -1.5    -1.5     -1.5     -1.5
   2520         -0.75   -3.0     -2.25   -2.25    -1.5     -1.5
   3000         -0.75   -3.0     -3.75   -3.0     -2.25    -3.0
   3520         -0.75   -3.0     -3.75   -3.75    -3.0     -3.0
   4000-5000     0      -3.0     -3.75   -3.75    -3.0     -3.0
   5520-6520     0      -2.25    -3.0    -3.0     -3.0     -3.0
   Below 2000 rpm and below 79.5 % load: stock. No timing added anywhere.
   Why: on v1 the engine ran 2 to 4 deg of knock retard at full load and had 11-16 knock
   detections per second while the turbo spooled through 97 % load. The new map sits about
   where the engine was already firing, so it should reach it without knocking first.

2. BOOST / LOAD  KFLDRX 0x1D5766 (maximum load)
   rpm     1900   2100   2400   2700   3000   3600   4000-5000   5240   5520   6000   6520
   stock    124    123    123    123  124.5    123   129-129.5  120.1  117.3  112.5  111.5 %
   v1       131    135    141    146  148.2  148.4   148.4-149.4  146.0  142.0  134.5  134.5 %
   v3       134    140    147    152  155.5  155.5       155.5    150.0  142.0  134.5  134.5 %
   Below 1900 rpm: stock. On v1 the real load matched the request at 2700 rpm and fell
   about 8 % short from 3500 rpm up, so expect about 150 % real load near 2700-3000 rpm
   and about 147 % above, at roughly 13 to 13.5 psi.
   MDMAXNMOT 0x1D586A (torque cap): 41.0 % at 2020 rpm, 44.5 % at 2520, 46.0 % from 2853
   to 5000, 44.0 % at 5333. Rest as v1. This also gives about 5 % more torque for the
   same pedal position at part throttle from 2500 rpm up.
   KFLDIMX 0x1CB7E4 (wastegate duty limit), last column, 2240-5000 rpm: 66-70 -> 72 %.
   (The stage 2 tuner used 68-73 % up to 3760 rpm and 73-82 % above.)

3. FUEL  LAMFA 0x1D1B48 - full-load enrichment now starts earlier on the pedal
   driver request     95 %     99.3 %    99.5 %
   2520 rpm           0.94     0.85      0.85
   3000 rpm           0.92     0.82      0.82
   3520-6000 rpm      0.90     0.82      0.82
   (v1: 1.00 / 0.90 / 0.82.) Why: in the v1 logs, pulls at 91-93 % pedal ran lambda 0.90
   at 140 % load instead of 0.82, because the request stayed just under 99.5 %.

4. PEDAL  KFPED 0x1C92F8 - driver request raised by 4 to 12 % between 10 and 40 % pedal,
   from 1250 rpm up. Idle columns, 0-5 % pedal and 50-100 % pedal: stock. KFPEDL: stock.

5. FAULT CODES - downstream (rear) oxygen sensor codes switched off (class 03 -> 00):
   path 79  0x1D5F6B  P0036 / P0037 / P0038 / P0141   rear sensor heater
   path 80  0x1D5F6F  P0036 / P0037 / P0038           rear sensor heater
   path 94  0x1D5FA7  P0139 / P0140                   rear sensor slow / no activity
   path 101 0x1D5FC3  P0136 / P0137 / P0138 / P2232   rear sensor circuit
   path 135 0x1D604B  P2096 / P2097 only              post-catalyst fuel trim
   P0420 was already off in v1. ALL upstream (front) sensor codes stay on, including
   P2195 / P2196 (same path 135, left active) and the front heater codes (path 82).

6. EXPERIMENTAL - torque limit in 5th and 6th gear  KFMDBGRG 0x1D44D6 (+ its gear axis)
   Stock table: gear axis 0,1,2,3,4,5,7 = neutral 25 %, gears 1-5 no limit, last point 25 %.
   v3: gear axis 0,1,3,4,5,6,7 = neutral 25 %, gears 1-4 no limit (full Stage 1 v3),
   5th and 6th limited to 40 % indicated torque, last point 25 % as stock.
   40 % asks for about 133 % load. Stock full throttle was about 120-123 %, v1 about 140 %.
   Later logs showed about 43 % torque in 5th/6th, so the table works as described.

NOT changed from v1: KFLBTS, KFMLDMX, KFMIRL, KFMIOP, compressor pressure-ratio limits,
overboost detection, FRLMXRED, exhaust temperature model, rev limit, load ceiling above 5500 rpm.

Honest limits of this file:
- Power: about 5-7 % more torque than v1 from 2500 to 5000 rpm (estimated, not measured).
- 2000-3000 rpm at full load is where this engine knocks most easily and where the clutch
  slipped. Timing is already low there (7-10 deg); the knock control is the remaining margin.
- Nothing has been logged above 5500 rpm on any Stage 1 file.
- All logs were on 91 AKI (North American) fuel. The timing was set from those logs.
- More torque in 1st-4th means more load on a clutch that already slips when hot.
```
