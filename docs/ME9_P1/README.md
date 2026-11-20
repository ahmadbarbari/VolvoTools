# DIY tuning of the Volvo P1 Bosch ME9.0C (C30 / S40 / V50 / C70 T5) with VolvoTools

A free, open chain for **reading, backing up, logging, editing and flashing** the Bosch ME9.0C engine ECU on Volvo P1 cars, using a ~40 $ J2534 cable and this fork of VolvoTools. It includes:

- a **checksum tool** that fixes both checksum tables (VolvoTools does not, see 3.4);
- a **pre-flight checker** and **Windows scripts** that refuse to flash a bad file and verify every flash with a full read-back;
- **TunerPro definitions (XDF, 740 tables)** for software P010D600, plus map lists and 6,897 RAM variables;
- **logger variable files** (boost, knock per cylinder, lambda, load, timing, fuel pressure, cams…);
- everything learned along the way: flash layout, bootloader erase behaviour, logging protocol, how the torque/boost/fuel/timing chain behaves, and real log results.

Developed and verified on one car: a 2008 C30 T5 (B5254T3, 6-speed manual), November 2026. Written by **ahmadbarbari** together with **Claude (Anthropic)**, who did the code tracing, disassembly, tooling and log analysis.

> ⚠️ **Read this first.** Flashing an ECU can leave a car that doesn't start. Everything here was verified on one car only. Items marked *pending* are traced in code but not confirmed by logs. You are responsible for your engine, your clutch and your local emissions law. Start by reading and logging, which can't harm anything. Only write once you have a verified backup and have tested your recovery path.

---

## 1. Quick start (what to do, in order)

| # | Step | Risk |
|---|---|---|
| 1 | Get the hardware and software (section 2) | none |
| 2 | `scripts\1_check_cable.bat`: the flasher must list your cable | none |
| 3 | `scripts\2_backup_stock.bat`: reads the ECU twice, checks they're identical, saves `backups\stock_read.bin`. **Copy it off the PC.** | none (read only) |
| 4 | `python tools\me9_p1_checksum.py backups\stock_read.bin` must end with `ALL OK`. This proves the checksum layout matches your software. If it doesn't, **stop**. | none |
| 5 | Find your software version: `python tools\preflight.py backups\stock_read.bin` prints the ID line (e.g. `…/1X25T06//P010D600/…`) | none |
| 6 | `scripts\3_log.bat`: log idle, cruise and one full-throttle pull on stock. These are your baseline knock, load, lambda and boost figures. *(The variable files are for P010D600; see section 6 for other versions.)* | none (read only) |
| 7 | **Write test:** flash your own `stock_read.bin` back with `scripts\4_flash.bat`. It must end with `SUCCESS`. This proves the write and recovery path on your car. | low |
| 8 | **One-byte test:** change one 0x00 padding byte in the calibration to 0x01 (on P010D600: file 0x1C34F0), fix the checksums, flash, start the engine. This proves the erase works and there is no signature check. | low |
| 9 | Edit maps in TunerPro with the XDF (section 7), **one change at a time**, then `python tools\me9_p1_checksum.py tuned.bin --fix tuned_fixed.bin` | — |
| 10 | Flash `tuned_fixed.bin` with `scripts\4_flash.bat`, then log again and compare with your baseline | medium |

`4_flash.bat` always runs, in this order: pre-flight (size, ID, both checksum tables, no changes in areas the flasher can't write) → dry run (the image the flasher would write must match the file exactly) → you type `FLASH` → write → **full 2 MB read-back compared byte for byte**. Recovery for anything that goes wrong is to flash `backups\stock_read.bin` with the same script. The boot area is never erased (section 4).

*The four .bat files are generic versions of the scripts used on the test car. The commands inside them (read, dry run, flash, log) are the exact ones verified on the car.*

---

## 2. What you need

| Item | Notes |
|---|---|
| J2534 cable | Tested: **MongoosePro JLR clone** (~40 CAD). Install its **32-bit** J2534 driver. A DiCE should also work (supported by VolvoTools), but it wasn't tested here. |
| VolvoTools build | This fork → **Actions** tab → latest successful run → download **`VolvoTools_Build_x86`** (you must be signed in to GitHub). Put `VolvoFlasher*.exe` and `VolvoLogger*.exe` in `ME9_P1\tools\`. Tested: commit **ee3d57f**. |
| Visual C++ runtime | x86 and x64 redistributables from Microsoft, or VolvoTools won't start |
| Python 3 | python.org, tick "Add to PATH". Used for the checksum tool and pre-flight. |
| TunerPro RT | Free map editor that opens the XDF |
| Battery charger | Connected and ON for every read and write |
| Windows laptop | Mains power, sleep and USB power saving off. **No parentheses in the folder path** (they break .bat files). |

**Folder layout** (keep it like this, because the scripts use relative paths):

```
ME9_P1\
  README.md
  scripts\    1_check_cable.bat  2_backup_stock.bat  3_log.bat  4_flash.bat
  tools\      me9_p1_checksum.py  preflight.py  clutch_slip_check.py  (+ VolvoFlasher*.exe, VolvoLogger*.exe)
  logger\     P010D600_log_full_40.ecu  P010D600_log_short_12.ecu  P010D600_log_oiltemp_clutch_test.ecu
  definitions\P010D600\  XDF, map list, RAM variable list, Ford A2L name port, DTC table
  examples\   Stage1_change_list_P010D600.md
  backups\  logs\  work\   (created by the scripts)
```

**Manual commands** (global options go *before* the subcommand):

```
VolvoFlasher.exe devices
VolvoFlasher.exe -f P1 -e 7A --cm-info me9_p1 -v read -o read1.bin -s 0 -sz 200000
VolvoFlasher.exe -f P1 -e 7A --cm-info me9_p1 --json flash -i file.bin --dry-run --emit-image emitted.bin
VolvoFlasher.exe -f P1 -e 7A --cm-info me9_p1 -v flash -i file.bin > flash_output.txt 2>&1
VolvoLogger.exe  -f P1 -e 7A --variables vars.ecu -o log.csv -p 8
```

Timings on the test car: read about 5 min 50 s; flash about 3 min 20 s (erase ~20 s, block A ~38 s, block B ~108 s). No security access or PIN was needed (2008 C30).

---

## 3. Bugs found in VolvoTools (P1 ME9)

### 3.1 Upstream CLI loads the wrong bootloader on P1 *(verified)*
In prometey1982/VolvoTools (build e725176), the command-line `read` and `flash` never pass the `me9_p1` setting, so a P1 car gets the **P2 ME7 bootloader at 0x31C000**. The log shows `startPBL` answered (`7a c6`), then `write chunk 31c000`, and then the ECU stops answering. No harm is done because it goes to RAM only and clears with an ignition cycle, but the read fails. The Najiy fork's `--cm-info me9_p1` (default for `-f P1 -e 7A`) loads the ME9 SBL at **0x7F81D0**.

### 3.2 False "Flashing error" after a good write *(fixed in ee3d57f, verified)*
After block B the flasher printed `Write flash failed` / `Flashing error`, although the full read-back was identical. Cause: a **stale 0x9C reply was taken as the answer to the B4 (block checksum) request**. Commit ee3d57f clears the RX queue before B4 and accepts the B1 confirmation among the next 5 frames. A wrong checksum still fails.

### 3.3 Exit code is 0 even on "Flashing error" *(verified)*
Don't trust the exit code. Save the output with a plain redirect (`> file 2>&1`, **no pipe**, so a crashed viewer can't interrupt the write), search it, and **always read back the full 2 MB and compare**. `4_flash.bat` does all of this.

### 3.4 Checksums are neither checked nor fixed on P1 ME9 *(verified)*
- The built-in routine reads the code checksum table **little-endian**. It is big-endian, so nothing is found and the dry run reports `valid: true, checkedBlocks: 0` for any file.
- The **calibration checksum table** (section 5) isn't handled at all.
- So a modified file would be flashed with wrong checksums. Fix them with `tools\me9_p1_checksum.py`.

---

## 4. Flash layout and erase behaviour

**What the tool writes** (`createVBFForME9P1`): **0x020000–0x08FFFF** and **0x0A0000–0x1EFFFF**.

**What the bootloader erases**, from disassembly of the embedded P1 ME9 SBL (11,496 bytes, base 0x7F81D0, erase command 0xF8 handled at 0x7F8498):
- It only accepts erase address **0x20000** or **0x1E0000**; anything else replies `F9 02`.
- Erase at 0x20000 clears **0x020000–0x08FFFF** and **0x0A0000–0x1FFFFF** (table at 0x7F9770), plus 0x404000–0x47FFFF only if a RAM flag at 0x7F8014 == 0x20 (other memory variant).
- Erase at 0x1E0000 clears 0x1E0000–0x1EFFFF only (not used by the tool).
- Before erasing, it overwrites a block-valid marker (pointer table at RAM 0x7FAD84 +4/+8).

**What that means:**
- **Boot 0x000000–0x01FFFF is never erased**, so a failed flash can be redone over OBD.
- **Gap 0x090000–0x09FFFF** is neither erased nor written. It holds code (`ZZZZ3333` header) covered by the code checksum table.
- **Tail 0x1F0000–0x1FFFFF** is erased but not rewritten. It is all 0xFF in stock, so the result is the same.
- **Never change bytes in boot, the gap or the tail.** They won't be written. `preflight.py --stock` checks this for you.
- The dry-run image equals your file with 0x000000–0x01FFFF and 0x090000–0x09FFFF set to 0xFF. `preflight.py --expected` builds that image, and `4_flash.bat` compares against it.

---

## 5. Checksums: two tables, both required *(verified on the car)*

Both tables use the same format: 16-byte entries, big-endian u32 **start, end (inclusive), sum, ~sum**, where **sum = 32-bit total of 16-bit big-endian words** from start to end.

| Table | Location (P010D600) | Entries | Address type | Covers |
|---|---|---|---|---|
| Code | file 0x0A0000–0x0A0360 | 54 | file offsets | 0x020000–0x1BFFFF and 0x1F0000–0x1FFFFF |
| **Calibration** | file **0x1CA9E0** | 6 | **CPU addresses (file + 0x400000)** | 0x1CA540–0x1CA9DF, 0x1C2000–0x1C34FF, 0x1C4320–0x1C7FFF, 0x1C8000–0x1CFFFF, 0x1D0000–0x1D7FFF, 0x1D8000–0x1DFFFF |

- **Every map lives in the calibration ranges, so every tune must fix the calibration table.**
- The tool finds the calibration table **by structure** (address pairs plus sum/complement pairs), so it works on other software versions. The same algorithm validates a 2006 Volvo P010BB00 (0261209009) file (table at 0x1C8F20), a 2011 C30 P010E500 file and Ford Focus RS ME9.0C files (0x1CA8A0, 7 entries). It was found by comparing an original with a commercially checksum-corrected Ford RS file.
- Cross-check: a file corrected by a commercial tuner's tool came back **byte-identical** to the same file fixed with this script.
- **No signature check:** the one-byte test (0x1C34F0 00→01, sums fixed) flashed and ran normally.
- `me9_p1_checksum.py` refuses to write if anything outside the sum fields would change. Run it on the output again: it must say `ALL OK`.

---

## 6. Logging (VolvoLogger, D2 over CAN)

- High-speed CAN (OBD pins 6/14), 500 kbps, 29-bit IDs. Requests on **0x000FFFFE**, ECM address **0x7A**, replies seen on 0x00400021.
- Sequence: clear list `CB 7A AA 00 00 00 00 00` → register each RAM variable `CF 7A AA 50 A2 A1 A0 SZ` (24-bit address + size) → poll all `CD 7A A6 F0 00 01 00 00` → reply echo `7A E6 F0 00` + values in registration order, big-endian, multi-frame. Read-only.
- About 11 Hz with 32 values (`-p 8`). Start the logger after the engine is running.
- Real boost is **not** available through standard OBD PID 0x0B on these cars. Only the ECU's own variables give it.

**The RAM addresses below and in `logger\*.ecu` are for P010D600.** RAM layout changes between software versions. For another version, port the addresses through the code references, as was done here (section 7), then check every value on the car (rpm and speed against the dash, coolant against the gauge) before trusting it. `definitions\P010D600\…logging_variables_v0.1.csv` lists all 6,897 ported variables with vote counts.

| Variable | Address | Size | Scale | Status |
|---|---|---|---|---|
| nmot_w rpm | 0x7FB3AA | 2 | ×0.25 rpm | verified |
| pvdkds_w boost (abs, before throttle) | 0x7FB20A | 2 | ×0.0390625 hPa | verified |
| plsol_w boost target (abs) | 0x8034C4 | 2 | ×0.0390625 hPa | verified |
| pu_w ambient | 0x803518 | 2 | ×0.0390625 hPa | verified |
| ps_w manifold (abs) | 0x7FB906 | 2 | ×0.0390625 hPa | **modelled from the MAF, not measured** |
| rl_w / rlsol_w load / target | 0x7FB90A / 0x7FB018 | 2 | ×0.0234375 % | verified |
| wkrm mean knock retard | 0x8045BF | 1 | ×−0.75 ° | verified |
| wkr_1..5 per-cylinder retard | 0x8045B9–BD | 1 | ×−0.75 ° | verified |
| zwout ignition | 0x7FB8EC | 1 | signed ×0.75 ° | verified |
| ldtvm wastegate duty | 0x8043E8 | 1 | ×0.390625 % | verified |
| lamsoni_w / lamsbg_w lambda / target | 0x7FABDC / 0x7FAD98 | 2 | ×0.0002441406 | verified |
| ml_w air mass | 0x7FB904 | 2 | ×0.1 kg/h | verified |
| tmot / tans coolant / intake air | 0x8045ED / 0x8041B1 | 1 | ×0.75 − 48 °C | verified |
| tabgm_w modelled EGT | 0x803A42 | 2 | ×0.01953125 − 50 °C | verified |
| vfzg_w speed | 0x7FAE96 | 2 | ×0.0078125 km/h | verified |
| tef_w injection time | 0x7FB2C2 | 2 | ×0.016 ms | verified (no dead time). Duty % ≈ ms × rpm / 1200 |
| pistnd_w / psollnd_w fuel pressure / target | 0x7FAE1C / 0x803F74 | 2 | ×0.1 kPa abs | verified |
| mibgrg_w torque limit by gear | 0x8042C4 | 2 | ×0.0015259 % | verified |
| gangi gear | 0x8045F0 | 1 | | verified, lags 1–5 s after a shift |
| wnwe_w / wnwse_w intake cam actual / target | 0x7FB430 / 0x7FAB0A | 2 | signed ×0.0078125 °CA | *pending* |
| wnwa_w / wnwsa_w exhaust cam actual / target | 0x7FB42E / 0x7FAAF0 | 2 | signed ×0.0078125 °CA | *pending* |
| tapcm_w fuel pump duty | 0x803ED6 | 2 | ×0.0015259 % | *pending* |
| pssol_w manifold pressure target | 0x7FAA5A | 2 | ×0.0390625 hPa | *pending* |
| minmxl_w rev-limiter torque (air path) | 0x7FAEF8 | 2 | ×0.0015259 % | *pending* |
| uhfm_w MAF voltage | 0x80428E | 2 | ×0.0048828 V | *pending* |

Boost psi = (pvdkds_w − pu_w) / 68.948. Oil temperature: the oil level sender is a Hella thermal sensor (level + temperature). Candidates `toel` 0x804183 and `toelk_w` 0x804136 are *pending* (`P010D600_log_oiltemp_clutch_test.ecu`). Oil pressure is only an on/off switch.

**Clutch slip check:** `python tools\clutch_slip_check.py log.csv` (needs nmot_w, vfzg_w, rl_w). Event = speed ≥ 15 km/h and load ≥ 100 %. The gear is locked at the start of the event; slip = (rpm/speed) ÷ gear ratio − 1, median of 5 samples, flagged if > 3 % for ≥ 0.4 s. Edit the gear ratios for your gearbox (default: M66 6-speed, stock tyres). Worth running before you add torque to an old clutch.

---

## 7. Map definitions

There is no public damos for P010D600. The definitions were built from:
- PowerPC disassembly of the map-lookup calls (r2 = 0x5CB1F0, r13 = 0x7FFFF0);
- two Volvo P010BB00 (HW 0261209009) WinOLS packs, ported by aligning lookup calls between versions;
- the Ford Focus RS Mk2 ME9.0C A2L (`P050F100.a2l`, SW 1037501201). Its code is close to the Volvo code: 874 of 1,079 map-lookup calls align. A Ford name is only used when two independent porting methods land on the same address.

**Files in `definitions\P010D600\`:**

| File | What |
|---|---|
| `C30_T5_P010D600_bosch_names_v0.5.xdf` | TunerPro XDF: **740 tables + 6 constants**. Each description says how it was located and whether it is confirmed |
| `…map_list_v0.4.csv` | Every table and scalar with address, size, scaling and confidence (`how_located`) |
| `…logging_variables_v0.1.csv` | 6,897 RAM variables with addresses, scaling and vote counts |
| `…ford_a2l_names_v0.1.csv` | 3,166 calibration names ported from the Ford A2L (single-vote entries unverified) |
| `…DTC_table_v0.1.csv` | Fault-code class table (0x1D5E2F, 4 bytes per path) ↔ P-codes (0x1D6A06). Set a path's class to 00 to turn its codes off |

**Other software versions:** the XDF only matches P010D600 (HW 0261209038, Bosch SW 1039S13190). Many maps sit at different addresses in other versions. To port: compare the map-lookup code between your file and P010D600 (the same routines exist in every ME9.0C), or search for each map's axis header bytes. Check every key map's axes and values look sensible before editing. The checksum tool, pre-flight and scripts work on any P1 ME9.0C.

**File layout:** calibration at file 0x1C3000–0x1DA000, seen by the CPU at file + 0x400000. Inline maps are X-major: `[nx][ny][X axis][Y axis][data]`, 8-bit (lookup 0x10BE2C) or 16-bit (0x10BF98). Curves use 0x10DA84 / 0x10DC4C. Group maps hold data only, with separate axis objects, stored rpm-major. ID block at 0x1C34B0.

**Key tables (P010D600 file address of the data):**

| Name | Address | Format | What it does | Status |
|---|---|---|---|---|
| KFLDRX | 0x1D5766 | 16 rpm × 6, u16 ×0.0234375 % | **The real max load / boost ceiling** (Volvo uses it instead of LDRXN). Stock 123–132 % to 5000 rpm | log-confirmed |
| MDMAXNMOT | 0x1D586A | 16-pt vs rpm, % | Max indicated torque. Stock 40 % falling to 32.5 %. Raise it together with KFLDRX | log-confirmed |
| KFMIRL | 0x1C9AA0 | 16×16 u16 | Torque → load. Tops out at 165.8 % (not the limit) | confirmed |
| KFMIOP | 0x1CA3AC | 16×11 u16 ×0.0015259 % | Optimum torque from load | |
| KFZW / KFZW2 / KFZWA / KFZWA2 | 0x1C6E75 / 0x1C6F35 / 0x1C6FF5 / 0x1C70B5 | 16 rpm × 12 load, s8 ×0.75° | Ignition, blended by cam position. Identical in stock; edit all four | log-confirmed |
| KFDZWKG | 0x1D31CE | 8 rpm × 5 λ, s8 ×0.75° | **Timing added for rich mixture**: +6 to +9° at λ 0.75 | log-confirmed |
| DZWOLA | 0x1CA397 | 10-pt vs λ | −3° at λ 0.80–0.85, +3° at 1.10 | log-confirmed |
| KFLDIMX | 0x1CB7E4 | 16×8 u16 ×0.005 % | Wastegate duty I-limit (last column = high boost) | |
| KFLDRL / KFLDRQ0-2 | 0x1CB8E4 / 0x1CBA24… | | Duty linearisation / boost PID | |
| LAMFA | 0x1D1B48 | 15 rpm × 6 request, u8 ×0.0078125 | Driver-demand lambda. **Flat 1.00 in stock** | log-confirmed |
| KFLBTS / KFFDLBTS / KFDLBTS | 0x1D058D / 0x1D04CD / 0x1D0693 | | Component protection. Stock full-load enrichment comes from the **EGT model**, not a lambda map | log-confirmed (KFLBTS) |
| KFPED | 0x1C92F8 | 16 pedal × 12 rpm, u16 | Pedal map (KFPED is the active one, not KFPEDL) | log-confirmed |
| KFMDBGRG | 0x1D44D6 (gear axis 0x1D44C8) | 4 × 7 gear pts | Torque limit per gear. Stock 25.2 / 100 ×5 / 25.2 % | log-confirmed |
| KFPNDSOL | 0x1D2EBA (header 0x1D2E9E) | 6 rpm × 6 load, u16 ×0.1 kPa | Fuel pressure target: 400 kPa to 2500 rpm, 480 at 5000+ / high load | log-confirmed |
| PNDMAX / PNDMIN | 0x1D2F14 / 0x1D2F16 | u16 | Clamp 550 / 400 kPa | confirmed |
| KRKATE | 0x1D27B6 | u16, /96000 ms/% | Injector constant 0.0861 ms per % load at ~382 kPa ΔP | log-confirmed |
| FRLFSDP | 0x1D279E (header 0x1D2786) | 11-pt vs ΔP, /32768 | Fuel pressure correction (the ECU compensates for real ΔP) | log-confirmed |
| FKKVS / TVUBAT / TEMN | 0x1D2586 / 0x1D27D2 / 0x1C6C24 | | +10 % at ≥ 16 ms / dead time 0.65 ms at 14 V / min injection 0.700 ms | confirmed |
| KFNWSE / KFNWSA | 0x1CDB5E / 0x1CD40C | 16 rpm × 8 load, s16 ×0.0078125 °CA | Intake / exhaust cam targets (warm). Lower = advanced | *pending* |
| NMAXGA / NMAX | | | Rev limit 6500 (all gears) / 6800 rpm | confirmed |

**Behaviours worth knowing before you tune:**
- **Fired timing = cam-weighted KFZW + KFDZWKG(rpm, λ) + DZWOLA(λ) − knock retard.** At λ 0.82 the lambda terms add about +1.7° (3000 rpm), +2.4° (4000) and +2.9° (5500). So making LAMFA richer adds timing by itself (about +0.9° per 0.03 λ). Count this before adding timing.
- To raise boost, raise **KFLDRX and MDMAXNMOT together**, check the wastegate limit (KFLDIMX), add enrichment (LAMFA, which is flat in stock), then log knock, lambda and injector duty.
- **ps_w is modelled.** At full throttle it runs 0.8–1.0 psi under the real boost up to 5500 rpm and 1.6 psi above that, with raised load.
- The **diverter/bypass valve is not ECU-controlled** on this software (`B_ldsua` is only cleared at init). It's the factory pneumatic valve.
- Injection time = rk × KRKATE × FRLFSDP(ΔP) × FKKVS. Raising the fuel pressure target shortens injection time with no injector re-scaling, up to the 550 kPa clamp.
- Cat/rear-O2 codewords (CDKAT 0x1D4082 etc.) are in the map list but **unverified**. Turning off individual DTCs through the class table *was* verified. Check what your local law allows.

---

## 8. Results from the test car (91 AKI fuel, catless downpipe + intake, stock turbo / intercooler / injectors)

- **Stock** already pulled ignition above ~75–80 % load on 91, evenly across all 5 cylinders.
- **Stage 1** (`examples\Stage1_change_list_P010D600.md`: KFLDRX up to 155.5 %, MDMAXNMOT up to 46 %, LAMFA 0.82 at full load, timing −0.75 to −3.75°): about 13–14 psi, load ~150 %, mean knock retard 0.6–2.1° per rpm band, worst 4.5°. **No room for more timing on 91.**
- **Stock injectors** reach ~89 % duty (~92 % with dead time) at 5000–5300 rpm, ~150 % load, λ 0.82. Cold air makes it worse because the load target is easier to reach. Shift around 5500 rpm or limit the top end.
- **Bypass valve:** lift-off spikes grow from +1.2 psi at ~340 kg/h (stock) to +4.4–6.8 psi at 720–760 kg/h. The factory valve is too slow for the extra airflow.
- An original high-mileage clutch slipped in 4th/5th at 136–143 % load when warm (caught by the slip check). KFMDBGRG can cap torque in specific gears.

---

## 9. Credits

- **prometey1982**: VolvoTools.
- **Najiy**: the P1 ME9 fork (`--cm-info me9_p1`, dry run, desktop UI).
- **NefMoto** community: the shared Volvo ME9 packs, IDA database and Ford RS A2L, and prj's note that Volvo ME9 needs no security access.
- **Claude (Anthropic)**: co-author of the analysis, tools and documentation in this folder.

No ECU binaries are shared here. Bring your own read. Questions and results from other software versions are welcome as issues on this repository.
