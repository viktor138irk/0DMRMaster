# 0DMRMaster
Private DMR master server. Version 0.5.
Copyright &copy;2025  Alexander Mokrov, UR6LKW.

This project is currently in public alpha and is under active development.
Don't use it in production environment, interfaces may change.


## License
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.


## Overview
This project contains:
1. An implementation of homebrew dmr protocol (which is used by brandmeister and hblink). Not yet complete, but sufficient for #2 and #3.
1. Decoding UDP proxy
1. Basic private dmr master server

### Installation
1. Check basic requirements:
    - Linux or Windows
    - Python 3.11+
1. Clone/download the repo.
1. Create environment and install requirements (linux example):
```
$ python -m venv venv
$ . venv/bin/activate
$ python -m pip install --upgrade pip
$ pip install -r requirements.txt
```

### Configuration
Copy `localmaster_EXAMPLE.py` to `localmaster.py` and edit.

### Run
```
$ . venv/bin/activate
$ python localmaster.py
```
`Ctrl+C` to break and stop.

The running server listens for `62031/udp` as DMR service (may be changed with `--port` command line argument)
and exposes http API/dashboard on `8000/tcp` (may be changed with `--web-port` command line argument):
- API: http://YOUR-SERVER-IP:8000/api/dashboard
- Web dashboard: http://YOUR-SERVER-IP:8000/dashboard/index.html
![web dashboard](https://github.com/olympy/0DMRMaster/blob/master/doc/dashboard-screenshot.png?raw=true)



## Roadmap
### What is this for (general TODO)
- Private dmr network (own registration, admintool, dashboard, voice apps, etc)
- Other dmr networks bridge (configurable group/unit routing rules, ID replacements, etc)
- Bridge/proxy with packet modification (substitute IDs, add TA, etc..)
- Voice robots interface at packet level (parrot for group and unit cals, recording/playback as prewritten packets by events)
- Encoding and decoding of AMBE (allows to build advanced voice services, like voice time, agenda, etc)
- Voice call history dump (ambe files or decoded)


### Features & TODO
- ✔️ basic apps support
- ✔️ parrot
- ✔️ password check
- ✔️ fastapi api
- ✔️ web dashboard
- ✔️ unit call routing
- ✔️ allow single peer id check
- ✔️ TA support (DMRA packet)
- ✔️ dmr internal structure decoding (get LC, voice data)
- 🥕 routing (1 timeslot == 1 routing entity)
- 🥕 only one call per ts for peer (per routing entity)
- 🥕 dmr internal structure encoding (set LC, generate voice data)
- 🥕 apps unit call routing (routing entity for app)
- 🥕 configuration
- 🥕 users configuration (allowed id and passes per id)
- 🥕 resolve id to callsigns
- 🥕 routing 2: group subscriptions
- 🥕 data calls (messages)
- 🥕 ambe decode/encode
- 🥕 log voice calls as files
- 🥕 TA support 2 (inside DMRD packets)
- 🥕 registration
- 🥕 update radiod list and resolve

## Sources
- ETSI TS 102 361-1 V1.2.1 (2006-01)
Technical Specification
Electromagnetic compatibility
and Radio spectrum Matters (ERM);
Digital Mobile Radio (DMR) Systems;
Part 1: DMR Air Interface (AI) protocol
https://www.etsi.org/deliver/etsi_ts/102300_102399/10236101/01.02.01_60/ts_10236101v010201p.pdf

- ETSI TS 102 361-2 V2.3.1 (2016-02)
Electromagnetic compatibility
and Radio spectrum Matters (ERM);
Digital Mobile Radio (DMR) Systems;
Part 2: DMR voice and generic services and facilities
https://www.etsi.org/deliver/etsi_ts/102300_102399/10236102/02.03.01_60/ts_10236102v020301p.pdf

- MMDVMHost by Jonathan Naylor, G4KLX
https://github.com/g4klx/MMDVMHost

- HBLink3 by Cortney T. Buffington, N0MJS
https://github.com/n0mjs710/hblink3

- IPSC Protocol Specs for homebrew DMR repeater by DL5DI, G4KLX, DG1HT 2015 (partially obsolete) 
https://wiki.brandmeister.network/images/5/54/DMRplus_IPSC_Protocol_for_HB_repeater.pdf