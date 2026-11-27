# Shared backbone release status

The source-parity package 0.2.0a5 is accepted as a portable shared scaffold.
Independent review at 96751dd: GO for the package; 536/536 Linux tests,
all runtime imports succeeded, offline wheel build with 125 entries.
The original private checkout was not independently accessible; the
source comparison is author evidence. The author acceptance on 5de711f
also passed 536 tests, 19 isolated mTLS tests, reproducible wheel,
installed-wheel byte checks, SDK/Docker and ledger checks. The wheel
SHA-256 prefix reported independently matches; full independent hash
comparison has not been recorded.

See SOURCE-PARITY.md, the a5 receipt and the extended containment fixture
receipt. The existing a3 bounded execution implementation retains its
prior independent review. Residuals include eager imports and the
source-specific memory/identity integrations documented in the audit.
No new inference loop, live agent migration or automatic activation.

The network/data law is mandatory. Existing bounded worker and registered
read-gateway paths are tested. The separately tested synthetic network
topology also denies direct traffic and fails closed when its relay stops.
It is not a production browser backend or a certification of public IP
privacy. Whole-agent/browser connected operation requires a separately
approved and qualified enforcement/egress environment. If not available,
do not execute an operation requiring that protection. No existing live
application or network route is migrated by this release.
