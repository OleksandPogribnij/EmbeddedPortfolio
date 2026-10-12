# HIL Power & Test Interface Board
 
A small USB-controlled board built around an **ESP32-S3** that powers a device under test (DUT), switches its power on and off, **measures its current**, and exposes its **UART / RESET / BOOT** lines to a host PC. It is a hardware building block for hardware-in-the-loop (HIL) test stands, designed in **KiCad**.

> **Status:** schematic v0.1 is complete and passes the electrical rules check (ERC). The PCB layout is in progress (components placed, ground plane added, routing under way). The board has **not been fabricated**, and nothing in this repository has been validated on real hardware yet.

| Stage | State |
|---|---|
| Specification | Done (draft) |
| Design notes and testability plan | Done (draft) |
| Schematic | Done (v0.1, ERC clean) |
| PCB layout | In progress: placement done, ground plane added, routing under way |
| Fabrication | Planned |
| Firmware | Planned |
| Bring-up and measurements | Planned |

## Why this board
 
Automated tests on real devices need three things the PC cannot do by itself: cut and restore the DUT's power, see how much current it draws, and talk to its serial console and boot pins. This board does all of them over a single USB cable, and it is designed with testability in mind (labelled test points, safe power-up state, current limiting).
 
It is the hardware companion of [`01-hil-test-stand`](../01-hil-test-stand), which will drive it from pytest.

## Features
 
- USB-C powered (5 V), native USB connection to the host through the ESP32-S3
- Switched 3.3 V DUT supply with current limiting and a fault output
- DUT supply is **off by default** and while the MCU boots
- Current and voltage measurement of the DUT supply (INA219, 0.1 Ω shunt)
- UART to the DUT, plus firmware-controlled RESET and BOOT lines
- Separate regulators for the MCU and the DUT, so DUT inrush does not disturb the controller
- Input protection: resettable fuse, TVS diode, ESD protection on the USB data lines
- 12 labelled test points, status and power LEDs

## Key specifications
 
| | |
|---|---|
| Input | USB-C, 5 V |
| DUT supply | 3.3 V, switched on the 5 V side (TPS2051C: 0.5 A rated, current limit 0.85 A typical) |
| Recommended DUT current from a USB 2.0 port | about 300 mA continuous |
| Measurement | INA219, 0.1 Ω shunt, about 0.1 mA resolution |
| MCU | ESP32-S3-WROOM-1 |
| Host interface | USB 2.0 full speed (CDC serial) |
| DUT connector (J2) | 1x6, 2.54 mm: `VDUT, GND, DUT_RX, DUT_TX, RST, BOOT` |
| Board | 2 layers; target about 50 x 40 mm (the current layout is larger and will be tightened after routing) |
 
Full details: [`docs/specification.md`](docs/specification.md).

## DUT connector (J2)
 
| Pin | Signal | Note |
|---|---|---|
| 1 | VDUT | Switched 3.3 V supply, measured |
| 2 | GND | |
| 3 | DUT_RX | Board TX goes to the DUT's RX (1 kΩ in series) |
| 4 | DUT_TX | The DUT's TX goes to board RX (1 kΩ in series) |
| 5 | RST | Driven low or released by firmware |
| 6 | BOOT | Driven low or released by firmware |

Only connect 3.3 V logic devices. A 5 V device needs a level shifter, which is not part of v0.1.

| Document | Purpose |
|---|---|
| [`docs/specification.md`](docs/specification.md) | What the board must do: requirements, nets, parameters, pin map, component table, acceptance criteria |
| [`docs/design-notes.md`](docs/design-notes.md) | Why each decision was made, with alternatives and status, including errors found and corrected |
| [`docs/testability.md`](docs/testability.md) | Test points, bring-up procedure, expected values and a failure-diagnosis table |

## Repository layout
 
```
03-pcb-test-interface-board/
├── README.md
├── hardware/
│   └── kicad/                 KiCad project (schematic and PCB)
├── outputs/
│   ├── schematic.pdf
│   ├── bom.csv                (after layout)
│   ├── gerbers.zip            (after layout)
│   └── renders/               (after layout)
└── docs/
    ├── specification.md
    ├── design-notes.md
    └── testability.md
```

## Testability
 
The board has 12 labelled test points (power rails, DUT supply, enable line, I²C, USB data, debug UART) and a bring-up checklist with expected values. See [`docs/testability.md`](docs/testability.md).
 
## Known limitations (v0.1)
 
- The DUT supply is fixed at 3.3 V, with no level translation.
- A standard USB 2.0 port limits the total current to about 500 mA, which leaves roughly 300 mA for the DUT.
- The DUT linear regulator dissipates about 0.5 W at 300 mA, so copper area for cooling is needed on the PCB.
- Current accuracy depends on the INA219 offset and the shunt tolerance; it has not been characterised.
- Some AP7361C values in the specification come from a distributor page and still have to be checked against the manufacturer datasheet.
- The design has not been fabricated or tested yet.
## Roadmap
 
- [x] Specification, design notes and testability plan
- [x] Schematic v0.1, ERC clean
- [ ] PCB layout, DRC clean, 3D render
- [ ] Gerber and BOM export
- [ ] Order and assemble a prototype
- [ ] Firmware: USB serial command protocol, current readout, power-cycle
- [ ] Bring-up report with measurements
- [ ] Integration with `01-hil-test-stand` (pytest)
- [ ] v0.2 ideas: selectable 3.3 V / 5 V supply, level shifter, extra test points (`DUT_FAULT`, `DUT_5V_SW`)
