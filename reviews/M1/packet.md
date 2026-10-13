# M1 review packet

Implementation commit: `890841f5693a94ac388b854c04d4bc03f539e3e2`

Exact-commit hosted CI green: True

Frozen checks: 104 PASS

```text
 .github/workflows/phase-c.yml |  33 +++
 c1/README.md                  |  27 ++
 c1/__init__.py                |   1 +
 c1/faults.py                  | 116 ++++++++
 c1/plant.py                   |  58 ++++
 c1/runner.py                  | 206 ++++++++++++++
 c1/rust/Cargo.lock            | 418 ++++++++++++++++++++++++++++
 c1/rust/Cargo.toml            |   9 +
 c1/rust/src/lib.rs            | 171 ++++++++++++
 c1/rust/src/main.rs           |  31 +++
 c1/tests/test_injection.py    | 166 +++++++++++
 faults/F1.yaml                |  25 ++
 faults/F2.yaml                |  28 ++
 faults/F3.yaml                |  28 ++
 faults/F4.yaml                |  24 ++
 faults/F5.yaml                |  20 ++
 faults/F6.yaml                |  23 ++
 faults/F7.yaml                |  23 ++
 faults/F8.yaml                |  23 ++
 reviews/M0/claude-round-2.md  |   7 +
 reviews/M0/evidence.json      | 556 +++++++++++++++++++++++++++++++++++++
 reviews/M0/packet.md          |  29 ++
 reviews/M1/local-checks.json  |   8 +
 reviews/M1/round-1.md         |  19 ++
 reviews/index.html            | 619 ++++++++++++++++++++++++++++++++++++++++++
 25 files changed, 2668 insertions(+)
```

- Phase C integrity: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38344360696
- Phase A SIL: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38344360683
- Phase B C32: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38344360686

See round notes for acceptance criteria, artifacts and limitations.
