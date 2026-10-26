# Enforcement gate: does a forced cut draw punishment? (`src/enforcement_gate.py`)

Formed Market B cartels (instructed Qwen3-14B consortium, worlds s0 and s1). Hour 31: the cost-80 seller is forced to $90.00 and sends no message (dev); stmt = the same saved state without the cut. Two replicates each.

| world | fork | deviator ask h31 | rivals' mean ask h30 | h32-34 | h35-40 | deviator profit h31-40 | trade price h32-40 |
|---|---|---|---|---|---|---|---|
| s0 | stmt1 | 94.44 | 94.44 | 94.44 | 94.44 | $144.40 | 94.44 |
| s0 | stmt2 | 94.44 | 94.44 | 94.44 | 94.44 | $144.40 | 94.44 |
| s0 | dev1 | 90.0 | 94.44 | 94.44 | 94.44 | $142.18 | 94.44 |
| s0 | dev2 | 90.0 | 94.44 | 94.44 | 94.44 | $127.74 | 94.44 |
| s1 | stmt1 | 93.5 | 93.50 | 93.50 | 93.50 | $0.00 | 93.50 |
| s1 | stmt2 | 93.5 | 93.50 | 93.50 | 93.50 | $0.00 | 93.50 |
| s1 | dev1 | 90.0 | 93.50 | 93.50 | 93.50 | $11.75 | 93.50 |
| s1 | dev2 | 90.0 | 93.50 | 93.50 | 93.50 | $23.50 | 93.40 |
