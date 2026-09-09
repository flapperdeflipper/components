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
