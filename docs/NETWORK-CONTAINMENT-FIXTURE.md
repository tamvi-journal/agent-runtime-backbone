# Network containment — isolated topology experiment

The shared spine's mandatory network/data law remains unchanged. This
experiment tests the proposed independent boundary using the existing
Docker engine, not a new agent runtime. It is not a production backend,
installer, VPN, proxy service, or browser integration.

The owner-run script scripts/containment_fixture.py creates two uniquely
labelled, internal, isolated-mode IPv4 bridge networks with IPv6 disabled.
A synthetic client is attached to the first, a synthetic canary to the
second, and a fixed-message relay to both. All containers use one reviewed
local immutable image, run non-root with dropped capabilities and no host
mounts, published ports, or image pulls. Inspection is required before
starting each process. No real network destination is contacted.

The script accepts an explicit reviewed local image ID. Run only in an
approved separate Docker environment:

    PYTHONPATH=src:. python scripts/containment_fixture.py --image-id sha256:REVIEWED_LOCAL_IMAGE_ID

A failure is a blocked/failed fixture, not authorization to use another
route. The script attempts cleanup only of the exact labelled resources
it creates, never prunes other resources. If cleanup cannot be confirmed,
its scoped identifier is emitted for owner inspection.

## Observed local experiment (extended fixture)

Docker server 29.5.3 on macOS (Linux container environment), using an
already-present reviewed Python 3.11.15 slim image:

| Observation | Result |
|---|---|
| Both internal isolated networks inspected | PASS |
| Client and child non-root; no IPv4 or IPv6 default route | PASS |
| Direct TCP and UDP to synthetic canary | Blocked; zero direct UDP receipts |
| IPv6 TCP/UDP to reserved documentation range | No connection/route available |
| Child process with empty inherited environment | Same enforced route boundary |
| Registered relay path | Two successful fixed-message responses (client and child) |
| Canary independent receipts | Exactly two, both from relay |
| Relay stopped | Relay request, direct TCP and UDP remain blocked for client and child |
| Scoped container and network cleanup | Confirmed |

The local CLI's default Docker configuration produced a permission warning
during read-only image lookup. The fixture uses the existing runtime's
explicit local daemon binding and isolated temporary Docker configuration;
it never opens that private Docker configuration file.

See [the generated receipt](../evidence/containment-fixture.json). The
extended fixture was author-run; it was not part of the independent
source-parity review.

## Remaining deployment gate

This result is intentionally narrow. It does not establish real protected
egress, public IP privacy, external DNS or WebRTC isolation, comprehensive
UDP/IPv6 isolation, browser startup,
host switching, or safe handling of external connectors. The lab cannot
certify a VM, host, account or browser outside its two synthetic networks.

A production integration requires an owner-approved protection mechanism
and separately qualified OS-level enforcement on the actual selected
backend. Require independent observation of approved destination traffic,
direct-route denial and failure behavior, DNS/IPv4/IPv6/UDP coverage,
child process and browser behavior, startup/restart and relevant data
boundaries. The absence of one required acceptance result blocks the
corresponding protected operation. Do not install a global firewall, change
host routes, move an existing working application, or reuse its live
session merely to run this experiment. Do not use privacy controls to evade
service rules or access restrictions.

The current four opt-in execution extensions and original host inference
loop are unchanged. No new optional production module is advertised by
this experiment.
