"""Generate docker import --change flags from a saved image config JSON."""
import json
import shlex
import sys

cfg = json.load(open(sys.argv[1]))
changes = []
for e in cfg.get("Env") or []:
    changes.append(("ENV", e))
if cfg.get("WorkingDir"):
    changes.append(("WORKDIR", cfg["WorkingDir"]))
if cfg.get("User"):
    changes.append(("USER", cfg["User"]))
for p in cfg.get("ExposedPorts") or {}:
    changes.append(("EXPOSE", p))
for v in cfg.get("Volumes") or {}:
    changes.append(("VOLUME", v))
for k, v in (cfg.get("Labels") or {}).items():
    changes.append(("LABEL", f'{k}="{v}"'))
if cfg.get("Entrypoint"):
    changes.append(("ENTRYPOINT", json.dumps(cfg["Entrypoint"])))
if cfg.get("Cmd"):
    changes.append(("CMD", json.dumps(cfg["Cmd"])))
if cfg.get("StopSignal"):
    changes.append(("STOPSIGNAL", cfg["StopSignal"]))
out = []
for i, v in changes:
    out.append("--change")
    out.append(shlex.quote(f"{i} {v}"))
print(" ".join(out))
