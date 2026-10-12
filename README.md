# Embedded & Hardware Test Portfolio

Hands-on projects in **hardware-in-the-loop (HIL) testing**, **electronics design** and **test automation for embedded systems**.
 
I am **Oleksandr Pohribnyi**, an automation QA engineer with 4+ years of experience in web, mobile, API and embedded test automation, and a B.Sc. in Electronics (Igor Sikorsky Kyiv Polytechnic Institute, 2021-2025). I am moving into embedded QA and hardware roles, and this repository is where I build and document the work that shows it.

> **Status:** this portfolio is under active construction. Each project below states exactly what is finished, what is in progress and what is only planned

## Projects
| # | Project | What it is | Status |
|---|---|---|---|
| 01 | [`01-hil-test-stand`](01-hil-test-stand) | A pytest-driven HIL test stand that uses the board from project 03 to power-cycle a DUT, read its current and drive its serial console. | Planned |
| 02 | [`02-uav-sitl-tests`](02-uav-sitl-tests) | Automated tests for drone flight-controller software running in a software-in-the-loop (SITL) simulator. | Planned |
| 03 | [`03-pcb-test-interface-board`](03-pcb-test-interface-board) | A USB-controlled ESP32-S3 board that powers a device under test (DUT), switches its power, measures its current and exposes its UART / RESET / BOOT lines. Designed in KiCad. | Specification and schematic v0.1 done (ERC clean). PCB layout in progress. Not fabricated yet. |

## What this portfolio demonstrates


## Tools and skills
| Area | Tools |
|---|---|
| Electronics design | KiCad (schematic, PCB), ERC / DRC, datasheet-driven part selection |
| Hardware | ESP32-S3, USB-C, LDO and load-switch power paths, INA219 current monitor, I²C, UART |
| Test automation | Python, pytest (planned), Selenium/Selenide and API testing in my day job |
| Version control and docs | Git, GitHub, Markdown |

## Repository layout

```
EmbeddedPortfolio/
├── README.md                         this file
├── 01-hil-test-stand/                planned
    ├── README.md
├── 02-uav-sitl-tests/                planned
    ├── README.md
└── 03-pcb-test-interface-board/
    ├── README.md
    ├── hardware/kicad/               KiCad project
    ├── outputs/                      schematic PDF, later BOM and Gerbers
    └── docs/
        ├── specification.md          what the board must do
        ├── design-notes.md           why each decision was made
        └── testability.md            how the board is tested and debugged
```
## Roadmap
- [x] Project 03: specification, README and design documents
- [x] Project 03: schematic v0.1, ERC clean
- [ ] Project 03: PCB layout, DRC clean, Gerber and BOM export
- [ ] Project 03: prototype and bring-up report with measurements
- [ ] Project 01: firmware for the board and a pytest HIL test stand
- [ ] Project 02: SITL test suite


## Contact
- GitHub: [OleksandPogribnij](https://github.com/OleksandPogribnij)
- LinkedIn: https://www.linkedin.com/in/oleksandr-pogribnij-2004pos
- Email: pogribnijoleksandr2004@gmail.com
- Location: Ivano-Frankivsk, Ukraine. Open to on-site, hybrid roles and remote work.
