# APEX GEN5 Canonical Pointer (Implementation)

The original frozen specification is preserved unaltered at:

`APEX_GEN5_CANONICALIZED_PHASE113_CORRECTED.md`

This implementation executes PAPER against that document plus the Master Prompt:

- Layer-1 engines E01–E12 are implemented as executable modules (`apex/engines.py`)
- 74-feature registry is executable (`apex/features.py`)
- Layer-2 (setup, playbook, strategy, forecast baseline, P-U-C, risk, execution, ledger, Telegram) is implemented against SL contracts rather than left as “execution team later”
- Funding rate is **NOT_ADMITTED** at runtime
- Forex session gates are not used; E12 uses UTC activity windows only
- Quantity model is crypto-futures quantity, not Forex lots

Code version: `5.0.0-paper`  
Schema version: `1`  
Parameter package: `pp-default-1`
