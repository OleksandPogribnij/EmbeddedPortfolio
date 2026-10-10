# Design notes
 
This document records **why** the board looks the way it does. The *what* is in [`specification.md`](specification.md), the *how it is tested* is in [`testability.md`](testability.md).
 
Each decision has an ID, the reasoning, the alternatives that were considered, and the consequences. Status values: **Accepted**, **To verify** (reasoning is done, but a datasheet value or a measurement is still pending).
 
Revision: schematic v0.1. Nothing here has been validated on real hardware yet.

---
 
## Index
 
| ID | Decision | Status |
|---|---|---|
| D-01 | Separate regulators for the MCU and the DUT | Accepted |
| D-02 | Load switch on the 5 V side, before the DUT LDO | Accepted |
| D-03 | TPS2051C as the DUT load switch | Accepted |
| D-04 | DUT supply is off by default (EN pull-down) | Accepted |
| D-05 | Open-drain fault line with pull-up to 3.3 V | Accepted |
| D-06 | 1 kΩ series resistors on all DUT signals | Accepted |
| D-07 | Unidirectional TVS after the resettable fuse | Accepted |
| D-08 | Dedicated ESD protection on USB data lines | Accepted |
| D-09 | INA219 with a 0.1 Ω high-side shunt after the DUT LDO | Accepted |
| D-10 | Fixed 3.3 V DUT supply, no voltage selection in v0.1 | Accepted |
| D-11 | Native USB of the ESP32-S3 instead of a USB-UART bridge | Accepted |
| D-12 | ESP32-S3 pin assignment avoids strapping pins | Accepted |
| D-13 | Schematic split into labelled blocks with net labels | Accepted |
| D-14 | Values taken from the AP7361C distributor page | To verify |
 
---
 
## D-01 Separate regulators for the MCU and the DUT
 
**Decision.** The ESP32-S3 is powered by its own LDO (AP2112K-3.3). The DUT gets a second LDO (AP7361C-33E) behind the load switch.
 
**Why.**
- The DUT is an unknown load. Its inrush current or a short circuit must not make the controller brown out or reset.
- The controller has to stay alive while the DUT is switched off, otherwise it could not switch it back on or report a fault.
**Alternatives considered.**
- One 3.3 V regulator for everything, with the DUT behind a switch. Simpler and cheaper, but a DUT fault would pull down the same rail as the MCU.
**Consequences.**
- One extra regulator and two extra capacitors.
- Both regulators share the same `+5V` input, so a very large DUT inrush can still dip `+5V`. This is limited by the switch current limit (D-03) and the input capacitors, and should be checked on the scope during bring-up.
---
 
## D-02 Load switch on the 5 V side, before the DUT LDO
 
**Decision.** Power path for the DUT:
 
`+5V → TPS2051C → DUT_5V_SW → AP7361C → DUT_SW → shunt → VDUT → J2`
 
**Why.**
- TPS2051C accepts 4.5–5.5 V at its input. In the first draft it sat *after* the 3.3 V LDO, i.e. at 3.3 V, which is outside its range and below its undervoltage lockout. It would not have worked reliably. This was found by reading the datasheet and corrected.
- With the switch in front, the DUT LDO has no supply when the DUT is off, so the DUT is really de-energised and the LDO consumes nothing.
- The switch current limit also protects the LDO input and the USB port.
**Alternatives considered.**
- Keep the switch on the 3.3 V side and use a switch rated for 3.3 V (for example TPS22918). It was not available in the KiCad library used for this project, and selecting another part would cost time with no benefit for a first revision.
**Consequences.**
- The current limit acts on the LDO *input* current. A linear regulator draws about the same current at its input as at its output, so the limit is a good approximation of the DUT current limit, but it is not an exact one.
- The INA219 measures at the LDO output (D-09), not at the switch.
---
 
## D-03 TPS2051C as the DUT load switch
 
**Decision.** Use a TPS2051C (SOT-23-5) as the switch.
 
**Why.**
- Input 4.5–5.5 V, matches the USB 5 V rail.
- Built-in current limit, typically 0.85 A (datasheet range 0.65–1.05 A).
- Open-drain fault output `FLT`, active low, readable by the firmware.
- Active-high enable.
- Output discharge, so the output does not stay charged after switching off.
**Notes.**
- Rated continuous current is 0.5 A, current limit is 0.85 A. The recommended DUT load for v0.1 is about 300 mA, which also respects the 500 mA USB 2.0 budget shared with the controller.
**Alternatives considered.** A plain MOSFET: cheaper, but no current limit and no fault output. A different switch family: not in the library, see D-02.
 
---
 
## D-04 DUT supply is off by default
 
**Decision.** `DUT_EN` has a 100 kΩ pull-down (R3) to GND.
 
**Why.** During power-up, reset and while the ESP32-S3 GPIOs are high-impedance, the enable line would float. With the pull-down the DUT stays off until the firmware drives `DUT_EN` high on purpose. A test stand that powers a device by accident is worse than one that does nothing.
 
**Consequences.** The firmware has to set `DUT_EN` explicitly, and the board is safe if the MCU crashes or is flashed.
 
---
 
## D-05 Open-drain fault line
 
**Decision.** `DUT_FAULT` (the `FLT` output of the switch) has a 100 kΩ pull-up (R4) to +3.3 V, read by an ESP32-S3 GPIO.
 
**Why.** `FLT` is open-drain. It is pulled low on overcurrent or thermal shutdown. The pull-up goes to the MCU rail (3.3 V), not to `+5V`, so the signal never exceeds the GPIO voltage.
 
---
 
## D-06 1 kΩ series resistors on all DUT signals
 
**Decision.** `DUT_RX`, `DUT_TX`, `RST` and `BOOT` go to J2 through 1 kΩ resistors (R11–R14).
 
**Why.**
- A DUT that is unpowered or misbehaving can drive its pins. Series resistors limit the current into the controller GPIOs.
- A wrong connection (for example 5 V by mistake) is limited by the resistor and the pin clamp diode, which may save the pin.
- RST and BOOT can be driven low or released (high-impedance) by firmware without the board fighting the DUT's own pull-ups.
**Consequences.**
- 1 kΩ is fine for UART at normal baud rates. Very fast signals would be slowed. This is not a concern here.
- Only 3.3 V logic DUTs are supported in v0.1 (D-10).
---
 
## D-07 Unidirectional TVS after the resettable fuse
 
**Decision.** D2 is an SMF5V0A (unidirectional, 5 V standoff) with the cathode on `+5V` and the anode on GND, placed after the PTC fuse F1.
 
**Why.**
- `+5V` is a DC rail. A unidirectional diode clamps positive spikes and conducts like a normal diode for reverse polarity.
- Placing it after the PTC lets the fuse limit the current if the TVS ever conducts for a long time.
**History.** A bidirectional part (SMF5.0CA) was suggested first. It is not the right choice for a DC supply rail and was replaced.
 
---
 
## D-08 Dedicated ESD protection on USB data lines
 
**Decision.** U2 (USBLC6-2SC6) protects D+ and D−. Net names:
 
- `USB_CONN_DP` / `USB_CONN_DN`: from the connector to the protection device.
- `USB_DP` / `USB_DN`: from the protection device to the ESP32-S3.
**Why.** The USB connector is the only external interface that humans touch, so ESD is realistic. The protection device sits right at the connector. Two names make it clear on the schematic and in the layout which side of the protection a trace is on.
 
**Layout consequence.** Keep these traces short, keep the pair together, and keep U2 close to J1.
 
---
 
## D-09 INA219 with a 0.1 Ω high-side shunt after the DUT LDO
 
**Decision.** R5 (0.1 Ω) is in series between `DUT_SW` and `VDUT`. The INA219 (I²C address 0x40) measures across it.
 
**Numbers.**
- Shunt drop at 300 mA: 0.1 Ω × 0.3 A = 30 mV, so `VDUT` is about 30 mV lower than `DUT_SW`.
- The INA219 shunt-voltage LSB is 10 µV, which is 0.1 mA with a 0.1 Ω shunt.
- With the ±160 mV range (PGA /4), the full scale is 1.6 A, well above the 300 mA target.
- Offset: the datasheet gives up to ±150 µV for grade A and ±75 µV for grade B. With 0.1 Ω that is up to about 1.5 mA and 0.75 mA of error at zero current, before shunt tolerance. For small sleep currents the offset matters; for 10–300 mA it does not.
**Why high-side after the LDO.** The DUT current is exactly what flows out of the LDO, and `VDUT` (the voltage at J2) is measured at the same time.
 
**Open point.** The offset error is not yet characterised on a real board. Use a 1 % shunt and measure at known loads during bring-up. Sub-mA sleep current measurement is a limitation of v0.1.
 
---
 
## D-10 Fixed 3.3 V DUT supply
 
**Decision.** v0.1 supplies the DUT with 3.3 V only. No jumper, no level shifters.
 
**Why.** A selectable 3.3 V / 5 V supply also means level shifting on UART, RST and BOOT, a second regulation path and more things that can go wrong on a first prototype. Fixed 3.3 V keeps the first revision simple and verifiable.
 
**Consequence.** A 5 V DUT cannot be connected directly. Planned for v0.2.
 
---
 
## D-11 Native USB of the ESP32-S3
 
**Decision.** The ESP32-S3 talks to the PC over its own USB (D+ on IO20, D− on IO19) as a CDC serial device. There is no USB-UART bridge chip.
 
**Why.** Fewer parts and cost, and the same USB cable carries power and data. The ESP32-S3 USB can also be used for flashing.
 
**Consequence.** UART0 (TXD0/RXD0) stays free for debug, exposed on test points TP10 and TP11.
 
---
 
## D-12 ESP32-S3 pin assignment
 
**Decision.**
 
| Signal | Pin |
|---|---|
| `DUT_EN` | IO4 |
| `DUT_RST` | IO5 |
| `DUT_BOOT` | IO6 |
| `DUT_FAULT` | IO7 |
| `I2C_SDA` / `I2C_SCL` | IO8 / IO9 |
| `UART_TX` / `UART_RX` (to DUT) | IO17 / IO18 |
| `LED_STATUS` | IO15 |
| Boot button | IO0 |
 
**Why.** Strapping pins (IO0, IO3, IO45, IO46) are avoided for application signals, except IO0, which is used on purpose for the BOOT button. The chosen pins are plain GPIOs, so nothing on the DUT side can change the boot mode of the controller.
 
---
 
## D-13 Schematic organisation
 
**Decision.** One sheet, with dashed frames and titles for each functional block. Connections between blocks use net labels, not long wires.
 
**Why.** The schematic is a document for other people. Labelled blocks read left to right (input, protection, regulators, switch, measurement, controller, connector, test points), and net labels remove crossing wires.
 
---
 
## D-14 AP7361C values to be verified
 
The AP7361C-33E data used in the specification (pin order, dropout, minimum capacitors) came from a distributor page, because the manufacturer datasheet could not be opened automatically. **Action:** compare the values with the Diodes Incorporated datasheet and update the specification. Until then they are marked as distributor data.
 
---
 
## Open items
 
- [ ] Verify AP7361C values in the Diodes datasheet (D-14).
- [ ] Confirm the PTC hold and trip current for the selected part against the 500 mA USB budget.
- [ ] Choose the final USB-C connector and check its pin mapping against the symbol.
- [ ] Check the thermal budget of the DUT LDO: about 0.5 W at 300 mA ((5 V − 3.3 V) × 0.3 A), so enough copper under the tab is needed in the layout.
- [ ] Measure inrush and the `+3.3V` MCU rail when the DUT is switched on (bring-up).
- [ ] Characterise the current measurement error against a reference meter (bring-up).
