# Setup

How to run the suite: the simulator on Linux, the tests on the same or
another machine. The reference setup is a Linux laptop running SITL and a
Windows PC running the tests; on a single Linux machine, use `127.0.0.1`
wherever a PC address appears below.

## 1. Simulator (Linux)

ArduPilot SITL is built from source. The reference setup builds it inside
an Ubuntu 22.04 container (distrobox) on a Fedora host, because the
ArduPilot install script targets Ubuntu.

```bash
# optional: an Ubuntu container on a non-Ubuntu host
distrobox create --name ardupilot --image ubuntu:22.04
distrobox enter ardupilot

git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
```

The install script adds `sim_vehicle.py` to the `PATH`. Check the version
the suite was verified with (ArduCopter V4.8.0-dev):

```bash
grep "define THISFIRMWARE" ~/ardupilot/ArduCopter/version.h
```

### Start the simulator

```bash
cd ~/ardupilot/ArduCopter
sim_vehicle.py -v ArduCopter --model + --out 127.0.0.1:14550
```

The first start builds the firmware and takes a few minutes. When MAVProxy
shows the `STABILIZE>` prompt, the vehicle is running.

**Restart the simulator before every full run.** The battery failsafe test
(TC-052/053) leaves the failsafe latched until SITL restarts. If an
earlier experiment changed parameters and TC-070 fails, add `-w` once to
wipe the stored parameters back to the defaults.

### Forward MAVLink to another machine

If the tests run on another PC, add an output in the MAVProxy console:

```
output add <PC_IP>:14550
```

`output` lists the current outputs. On Windows, allow inbound UDP 14550
in the firewall for the Python interpreter.

## 2. Test runner

Python 3.14: the version the suite is developed, linted (`pyproject.toml`) and run in CI with.

```bash
cd 02-uav-sitl-tests
python -m venv .venv
# Windows: .venv\Scripts\activate     Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

`requirements.txt` holds what the tests need; `requirements-dev.txt` adds ruff and allure.

### Connection

The endpoint comes from the `SITL_CONNECTION` environment variable. The
default, `udp:0.0.0.0:14550`, listens for the MAVProxy output above, so
for the reference setup nothing has to be set.

```powershell
# PowerShell
$env:SITL_CONNECTION = "udp:0.0.0.0:14550"
```

```bash
# bash; e.g. SITL without MAVProxy, as in CI
export SITL_CONNECTION=tcp:127.0.0.1:5760
```

Only one program can listen on a UDP port. Close any other MAVLink
client on the PC (a Python console with an open connection, a ground
station on 14550) before running pytest.

## 3. Running the tests

```bash
pytest                              # everything: 52 SITL + 8 unit tests, about 17.5 min
pytest -m "not sitl"                # unit tests only, no simulator needed
pytest -m "sitl and not flight"     # SITL checks without take-off, fast
pytest tests/test_mission.py        # one area
pytest -k test_geofence_breach      # one test
ruff check .                        # lint
```

If the simulator is not reachable, the run stops after 20 s with exit
code 2 and the endpoint in the message.

## 4. Allure report

pytest writes Allure results to `reports/allure-results` on every run
(`pytest.ini`). Allure CLI 2.x needs Java.

```bash
allure serve reports/allure-results          # open the report of the last run

# single-file report, as kept in docs/results
allure generate reports/allure-results --clean --single-file -o docs/results/allure-report
```

A failed SITL test has two attachments: the STATUSTEXT messages received
during the test and the vehicle state at the moment of failure.

## 5. Continuous integration

`.github/workflows/sitl-tests.yml` at the repository root runs on every
push to `main` and pull request that touches this project, and on demand
(Actions → *UAV SITL tests* → *Run workflow*). It builds SITL, runs the
suite against it and publishes the Allure report to GitHub Pages.

One-time repository setting: **Settings → Pages → Source: GitHub Actions**.
