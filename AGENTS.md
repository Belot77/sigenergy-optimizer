# AGENTS.md - sigenergy_optimizer

## Project purpose
Home Assistant energy optimization project for SigEnergy battery and tariff-aware control with safety-first operation.

## Context loading order
1. Root AGENTS.md.
2. This file.
3. README.md and key docs for behaviour assumptions.
4. Only required files in app/, tests/, and sigenergy_optimizer_addon/.

## Token-saving rules
- Use targeted reads for touched control paths and related tests.
- Do not scan unrelated modules or historical artifacts.
- Read only the minimum config/docs needed to validate assumptions.

## Files and folders to avoid
- Do not inspect or edit .git/, .venv/, caches, backups, generated artifacts, or ZIP files.
- Do not inspect unrelated projects.
- Do not treat local test outputs as source of truth.

## Safety rules
- Be conservative with battery, grid, solar, import/export, and live-control assumptions.
- Clearly separate monitor-only, dry-run, and live-control behaviour.
- Preserve manual override and safety behaviour.
- Avoid unsafe assumptions about grid sign convention, export/import semantics, battery SoC, inverter state, or tariff interpretation.
- Document all entity and integration assumptions for changed logic.

## Documentation update rules
- Update CHANGELOG.md for behaviour and control-path changes.
- Update README.md and operational docs for changed assumptions or setup.
- Document before/after control reasoning for logic changes.

## Testing and audit expectations
- Run targeted tests for modified control and forecast paths, then broader tests as needed.
- For control logic changes, include before/after reasoning plus test notes.
- Include manual verification steps for monitor-only, dry-run, and live-control modes.

## Packaging and release rules
- Source of truth is this project folder.
- Keep add-on files aligned with app behaviour and required settings.
- Exclude local env files, coverage/test outputs, caches, and release artifacts from packages.

## Git and security rules
- Do not force push or rewrite history unless explicitly requested.
- Never commit secrets, .env files, credentials, tokens, or private infrastructure details.
- Flag sensitive values, private hostnames, and unsafe hardcoded endpoints before commit/push.
