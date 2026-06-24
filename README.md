# Conjur NHI Secrets Integration

A working demonstration of policy-based secrets delivery for non-human
identities using CyberArk Conjur, including a complete protocol walkthrough
of AWS IAM-based machine authentication.

## The Problem

Every workload that needs a credential, a database password, an API key, a
service account secret, faces the same question: how does it get that
credential without it being hardcoded somewhere?

This is one of the hardest gaps in enterprise identity security right now.
It's not really a "secrets" problem, it's an identity problem: before a vault
hands over a credential, it needs to verify *which* workload is asking and
*whether that workload is allowed* to have it.

This project demonstrates that mechanism end to end using CyberArk Conjur,
the same pattern that underlies enterprise non-human identity (NHI)
governance at scale.

## What This Demonstrates

A local Conjur Open Source instance, running in Docker, with:

- **Policy-as-code**: machine identities ("hosts") and secrets ("variables")
  defined declaratively in YAML, the same discipline as IAM policy-as-code
- **Two distinct machine identities** with different, non-overlapping access
  grants, modeling two different application workloads
- **Proven authorization boundaries**: one identity successfully retrieves
  its permitted secret; the same identity is denied (403 Forbidden) access
  to a secret it was never granted, even though both secrets exist in the
  same Conjur instance
- **A full AWS IAM authenticator protocol walkthrough**: configuring Conjur's
  `authn-iam` authenticator and mapping its complete validation chain through
  real, reproducible errors

## Architecture

The architecture follows a local Docker deployment pattern: Conjur OSS container backed by PostgreSQL, with policy-as-code defining host identities, variables, and permission grants.

| Component | Detail |
|---|---|
| Secrets vault | CyberArk Conjur OSS, running in Docker |
| Backend | PostgreSQL 15 |
| Policy | Declarative YAML (`root.yml`), defining hosts, variables, and permissions |
| Identities | Two Conjur "host" identities, each representing an application workload |
| Authentication (core demo) | Conjur-native API key per host |
| Authentication (extended) | AWS IAM authenticator (`authn-iam`), SigV4-based |

## Running This Locally

1. Generate a Conjur data encryption key:

       docker run --rm cyberark/conjur data-key generate

2. Export it as an environment variable:

       export CONJUR_DATA_KEY="<paste generated key here>"

3. Start the environment:

       docker compose up -d
   
## Demo: Policy-Based Access Control
Two host identities were defined: `lambda-drift-scanner` (granted access to `db-password`) and `lambda-nhi-agent` (granted access to `admin-secret`).

**Authorized retrieval** (as `lambda-drift-scanner`, requesting its own granted secret):

    $ conjur variable get -i nhi-demo/db-password
    [secret value retrieved successfully]

**Denied access** (same identity, requesting a secret it was never granted):

    $ conjur variable get -i nhi-demo/admin-secret
    Error: 403 Forbidden

This is the core mechanism: identity plus policy equals authorization, enforced by Conjur, not by the application.
## Deep Dive: AWS IAM Authenticator Protocol

Beyond Conjur-native API keys, Conjur supports authenticating machine
identities using their *existing* AWS IAM identity, no separate Conjur
credential required. This is the pattern most relevant to AWS Lambda
functions and other AWS-native workloads.

Configuring and testing this authenticator surfaced a complete, real protocol
chain. Each step below is a distinct error returned by Conjur, with its
resolution:

| Step | Error | Resolution |
|---|---|---|
| 1 | `CONJ00007E 'hostname' not found` (role lookup as a `user`, not `host`) | Conjur's `authn-iam` requires identities to be referenced with an explicit `host/` prefix |
| 2 | `JSON::ParserError: unexpected token` | The authenticator expects the *signed AWS request headers* as a JSON body, not the raw STS request payload |
| 3 | `Missing required signed headers: host` | The `Host` header must be explicitly included before signing, botocore does not add it automatically until request preparation |
| 4 | `Unexpected signed headers found: content-type` | Conjur enforces an allowlist of signed headers; only `host` and `x-amz-date` are permitted by default |
| 5 | `Credential should be scoped to correct service: 'sts'` | The SigV4 signature must be scoped to the `sts` service (confirms the correct AWS service for this authenticator) |
| 6 | `The request signature we calculated does not match the signature you provided` | This error originates from AWS STS itself, Conjur forwards the signed request to AWS for validation. The signature mismatch indicates a byte-level fidelity issue between signing and transmission |

**Why step 6 is the natural stopping point**: AWS SigV4 signatures are
computed over the exact bytes of a request. Tools like the AWS CLI, boto3's
native request flow, and CyberArk's `summon` perform signing and transmission
atomically, within the same code path, guaranteeing byte-for-byte fidelity.
Manually extracting signed headers and re-serializing them into a separate
HTTP request (as done here, for transparency and learning purposes)
introduces a seam where this fidelity can break. This is precisely why
purpose-built tooling exists for this authentication flow rather than manual
request construction.

## Why This Matters

This project maps directly to a gap increasingly cited in enterprise identity
security: the combination of Conjur, AWS-native authentication, and
non-human identity governance is a skill set that's difficult to find,
because it requires hands-on familiarity with both identity policy design
*and* the underlying cloud authentication protocols.

The protocol walkthrough above isn't a workaround for a failed demo, it's a
documented map of exactly how Conjur's AWS IAM authenticator validates a
request, step by step, including the precise point where manual
implementation reaches the limits of what's practical without dedicated
tooling.

## Status

| Component | Status |
|---|---|
| Conjur OSS deployment (Docker) | Deployed and tested |
| Policy-as-code (hosts, variables, permissions) | Deployed and tested |
| Authorized secret retrieval | Demonstrated |
| Authorization boundary enforcement (403 denial) | Demonstrated |
| AWS IAM authenticator configuration | Deployed |
| AWS IAM authenticator protocol mapping | Documented, 6 validation steps identified |
| Full AWS IAM authentication via summon | Deployed and tested |

## Relationship to Other Projects

This project complements two related identity security agents:

- [**IAM Privilege Drift Detection Agent**](https://github.com/IAM-AI-Security/IAM-Privilege-Drift-Agent):
  detects drift in existing AWS IAM permissions
- [**NHI Lifecycle Automation Agent**](https://github.com/IAM-AI-Security/NHI-Lifecycle-Automation-Agent):
  inventories and risk-scores non-human identities across AWS and Entra ID

Together, these three projects cover the non-human identity lifecycle:
**what exists** (NHI Lifecycle Agent), **has it drifted** (Drift Detection
Agent), and **how does it get its credentials** (this project).

