# PET IEEE-488 port tester (universal dynamic board)

Files:
- `IEEETEST.PRG` – a tokenized program that loads at $0401. Use `LOAD"IEEETEST",8` then `RUN`.
- `ieeetest.bas` – the plain-text listing, for typing in or for petcat.

It runs on BASIC 4 (4032/8032) and BASIC 2. It's pure BASIC that uses only PEEK and POKE, with no machine code and no KERNAL IEEE calls.

---

## 1. Signal map (what the program drives and reads)

The bus is active-low. "Asserted" means the line is pulled low, and the matching plug LED is lit.

| Edge pin | Signal | Driven by (register → chip pin) | Read by (register → chip pin) |
|---|---|---|---|
| 1–4 | DIO1–4 | $E822 PIA2 PB0–3 → pins 10–13 | $E820 PIA2 PA0–3 → pins 2–5 |
| A–D | DIO5–8 | $E822 PIA2 PB4–7 → pins 14–17 | $E820 PIA2 PA4–7 → pins 6–9 |
| 5 | EOI | $E811 PIA1 CA2 → pin 39 | $E810 PIA1 PA6 → pin 8 |
| 6 | DAV | $E823 PIA2 CB2 → pin 19 | $E840 VIA PB7 → pin 17 |
| 7 | NRFD | $E840 VIA PB1 → pin 11 | $E840 VIA PB6 → pin 16 |
| 8 | NDAC | $E821 PIA2 CA2 → pin 39 | $E840 VIA PB0 → pin 10 |
| 11 | ATN | $E840 VIA PB2 → pin 12 | PIA2 CA1 → pin 40 (**edge flag only**) |
| 10 | SRQ | – (the PET never drives it) | PIA2 CB1 → pin 18 (**edge flag only**) |
| 9 | IFC | Reset circuit (not software controllable) | – |
| E | REN | Tied to GND on the PET | – |
| 12, F–N | GND | | |

Every PIA/VIA pin passes through an IEEE bus transceiver (MC3446, or 75160/75161 on some boards) on its way to the edge pin. Each transceiver channel's driver and receiver share one bus pin. So when the PET drives a line, it reads that line back itself, with or without a plug fitted.

ATN-in and SRQ-in go to PIA CA1/CB1, which only latch edges. The program arms the edge flag before each step: falling edge for "asserted", rising edge for "released". This works from BASIC because the flags stay set until read.

---

## 2. Test plug design

Fit one LED (lights when the line is low) and one switch to ground on each signal.

```
            +5V ──┬──────────┬──────── ... (16 channels)
                  │          │
                 [680R]     [680R]
                  │          │
                 LED ▼      LED ▼        green/yellow, Vf ≈ 2.0–2.2 V
                  │          │
   edge pin  ─────┴───┐      └──── ...
   (DIO1 etc.)        │
                      o
                     /   SW (SPST or DIP-switch position)
                      o
                      │
                     GND (edge pins 12 / F–N)
```

**Parts**
- One 24-way (2×12) 0.156" card-edge socket. This is the same part an IEEE cable uses on the PET end.
- 16 × green or yellow LEDs and 16 × 680 Ω resistors, one set per signal: DIO1–8, EOI, DAV, NRFD, NDAC, IFC, SRQ, ATN, REN.
- 14 switches to ground, for DIO1–8, EOI, DAV, NRFD, NDAC, ATN and SRQ. Two 8-way DIP switches are the easiest option. Switches on IFC and REN are pointless.
- A 100 nF decoupling capacitor across +5V/GND on the plug.
- A +5V lead. The PET's **second cassette port** has GND on pin 1/A and +5V on pin 2/B. If you use a separate 5 V supply instead, its ground must be tied to the IEEE ground pins, and it must only be powered while the PET is on.

Use green or yellow LEDs, not red. The PET's bus termination holds an idle line at about 3.3 V. With a ~2.1 V LED, that leaves the LED dark when the line is released. Red LEDs (~1.7 V) can glow faintly on idle lines and confuse you.

You can ground the lines straight through the switches with no series resistor. The bus is open-collector, so shorting a line to ground is exactly what a device on the bus does to assert it. Fitting a resistor would stop the line from going below the receiver's ~0.8 V threshold.

Before you plug it in, use an ohmmeter to check that the PET's edge pins 12 and N read 0 Ω to chassis. That confirms the plug's orientation. The REN LED (pin E) acts as a "plug is powered and fitted the right way round" indicator, because REN is grounded on the PET.

---

## 3. Running it

1. With everything off, connect the plug's +5V lead to cassette port #2, and leave the IEEE side of the plug unplugged. Power up the PET and the drive, then load the program.
2. Switch off the drive and unplug its IEEE cable from the PET. Push the test plug on squarely, with all its switches OFF.
   - The IEEE edge only carries signals and ground, so plugging it in with the PET on is low-risk. Just don't let the connector skew across pins.
   - To test IFC: IFC pulses when the PET is reset. If you want to check it, power-cycle the PET once with the plug fitted, and watch LED #15 (IFC) flash before you load the program.
3. `RUN`. The program then goes through four parts:
   - **Step 0.** All outputs are released. Confirm that only REN is lit.
   - **Steps 1–13.** The program drives each output low on its own: DIO1–8, EOI, DAV, NRFD, NDAC, ATN. For each one it tells you which LED should be lit, and you answer Y/N and list any other LEDs that are lit. It then shows what the PET read back.
     - The line stays driven until you press RETURN, so you can probe the PIA pin, the transceiver and the edge pin with a meter or scope.
     - Press **R** to repeat a step.
   - **Automatic pattern tests.** These drive all 13 outputs at once (catching loading or ground problems), then run 8 walking-1 patterns on the data lines.
   - **Input tests.** You close each plug switch in turn. These test every receiver independently of the PET's own drivers. This is the only way SRQ-in can be tested. Answer N if your plug has no switches; you can also do these by hand by touching a grounded wire to each edge pin.
4. **Diagnosis.** You get one verdict per line, then a list of every pair of lines that are linked together. That's followed by a ranked suspect list (each chip with the lines that implicate it) and the PIA/VIA pin numbers to probe for each faulty line. Press a key to page through it.

### How faults are told apart

| Observation | Verdict |
|---|---|
| Line reads low with everything released, LED lit | Stuck low on the bus: transceiver, PIA output stuck asserting, or a short to an adjacent GND pin (ATN pin 11 is next to 12; DIO8 pin D is next to REN/GND on E) |
| Reads low with everything released, LED off | Receive side stuck low: transceiver receiver output or PIA/VIA input pin |
| Driven → LED on, not read back; switch also not read | Receive path: transceiver receiver channel → PIA/VIA input pin |
| Driven → LED on, not read back; switch **is** read | Weak driver. The line only gets part-way low; measure it, it should be under 0.5 V |
| Driven → LED off, but read back | Open between transceiver bus pin and edge connector (or a dead plug LED, if the switch test works) |
| Driven → LED off, not read; switch test OK | Driver side: PIA/VIA output pin → transceiver driver input/enable |
| Register readback wrong | The PIA/VIA itself (or its data bus/select) |
| Asserting A also asserts B, visible on the LEDs | Bus-side short (connector, traces, transceiver pins); adjacent edge pins are flagged |
| Asserting A reads B low but B's LED stays off | Receive-side short; adjacent PIA/VIA pins are flagged (e.g. PIA2 pins 9/10 = DI8/DO1) |
| Works alone, fails with all lines driven | Transceiver supply or ground, or a missing decoupling capacitor |

Chip designators differ between board revisions. Find the PIA/VIA pin numbers above on your board's schematic (universal board sheets 8032081) to identify the actual chip locations.

---

## 4. Running from option ROM (UD12 + UD11)

- `ieeetest_UD12_9000.bin`: 4K, for socket **UD12** ($9000–$9FFF).
- `ieeetest_UD11_A000.bin`: 4K, for socket **UD11** ($A000–$AFFF).
- `ieeetest_9000-AFFF_8k.bin`: both halves in one 8K file, for a single-chip adapter covering $9000–$AFFF.

The sockets are wired for 2332 mask ROMs. A **TMS2532** EPROM drops straight in. A **2732** needs a 2332→2732 pin-swap adapter, because pins 18, 20 and 21 differ.

To start it, type `SYS 36864` in direct mode. A 6502 stub at $9000 does the rest:
- unpacks the compressed program to $0401
- sets TXTTAB/VARTAB/ARYTAB/STREND ($28–$2F)
- puts `RUN` + RETURN into the keyboard buffer ($026F, count at $9E)

`READY.` appears briefly and then the program starts. It replaces any BASIC program in memory. To check the chip is seen, `PRINT PEEK(36864)` should give 169.

The ROM copy has spaces and REM text stripped to make it fit: 10,804 bytes compress to 7,749, plus the 160-byte stub, out of 8,192. Once unpacked, `LIST` shows it squashed together, but it runs identically. `mkrom.py` rebuilds the images from `ieeetest.bas` if you change the program.

The stub relies on the BASIC 4 / BASIC 2 (upgrade ROM) zero-page layout. That's every universal board, but not an original 2001 ROM.
