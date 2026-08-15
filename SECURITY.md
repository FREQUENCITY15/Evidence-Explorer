# Security policy

Evidence Explorer is a public alpha intended for local, loopback-only use. It
must not be treated as a sole control, compliance decision, or production
security boundary.

## Supported versions

Security fixes are applied to the latest `0.8.x` release on `main`. Earlier
Project Mentor milestones are not maintained as separate security branches.

## Report a vulnerability privately

Use GitHub's
[private vulnerability reporting](https://github.com/FREQUENCITY15/Evidence-Explorer/security/advisories/new).
Do not open a public issue for a suspected vulnerability.

Include:

- the affected version or commit;
- a minimal, sanitized reproduction;
- expected and observed behaviour;
- the security impact you believe is possible;
- any suggested mitigation.

Never submit credentials, access tokens, private agent transcripts, proprietary
source, patient information, or other sensitive evidence. Replace sensitive
values with synthetic equivalents that preserve the behaviour.

Reports are handled on a best-effort basis. This alpha has no guaranteed
response or remediation service level.

## Current security boundary

- The supplied launch commands bind only to `127.0.0.1`.
- Evidence is treated as untrusted data and rendered through text-only sinks.
- Imports are validation-first, bounded, flat-file, and append-only.
- Raw checksum inputs are bounded, streamed, hashed, and discarded.
- There is no authentication, authorization, tenancy, or hardened remote
  deployment mode.

If you expose the application beyond loopback, you are operating outside the
supported security model.
