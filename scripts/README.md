# Scripts Directory Governance

This directory is organized to prevent pipeline drift and execution ambiguity.

Structure:

canonical/  
    Official reproducible pipeline scripts.
    These scripts are allowed to generate production artifacts.
    Any modification requires version update and documentation.

cli/  
    Entry-point scripts for running the system (e.g., RAG query interface).
    These do not generate artifacts; they consume canonical outputs.

tools/  
    Utility scripts for maintenance, rebuild, debugging, or patching.
    These must not redefine pipeline logic.

deprecated_archive/  
    Retired experimental scripts.
    Kept for historical traceability only.
    Must not be executed in any active workflow.

deprecated/  
    Older discarded logic preserved for audit transparency.

__pycache__/  
    Python cache (ignored).

Governance Rules:

1. Only scripts under `canonical/` may produce production data.
2. Production artifacts must reference a versioned canonical script.
3. Deprecated scripts must never be moved back without review.
4. Any new experimental script must be explicitly categorized before use.

Philosophy:

Pipeline reproducibility > convenience.
Governance traceability > iteration speed.
Clarity > accumulation.
