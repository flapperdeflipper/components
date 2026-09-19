# components

Our own Home Assistant custom components, pushed from this repo and linked
into the live configuration:

```
/homeassistant/custom_components/<name> -> ../components/<name>   (symlink)
```

The HA config repo ignores `custom_components/*` (HACS-managed components
live only there) and ignores this directory entirely - this repo is
published on its own.

## extended_openai_conversation

Locally patched LLM Assist agent (conversation integration). **Never update
or overwrite it from HACS/upstream** - the running HA version requires the
local patches. Restore snapshot: `.backup-extended_openai_conversation` in
the HA config's `custom_components/` directory.

## jura

Fork of AlexxIT/Jura (vendored from upstream v1.2.2). The live copy in
`/homeassistant/custom_components/jura` was still v1.2.0 (with an accidental
nested v1.2.2 copy inside it). This repo is the source of truth going
forward; quality upgrades happen here, then get copied to
`custom_components/jura` and reloaded.

### jura tests

The core logic tests run without Home Assistant or hardware:

```
python3 -m venv .venv && .venv/bin/pip install bleak bleak-retry-connector xmltodict pytest
.venv/bin/python -m pytest tests/ -q
```

`tests/conftest.py` stubs the few `homeassistant` imports so `jura.core` and
entity naming can be exercised; full integration coverage belongs on a dev
machine with `pytest-homeassistant-custom-component`.
