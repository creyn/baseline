# 5. No archive of original documents

Date: 2026-11-22

## Status

Proposed

## Context

The original document never leaves the user's device ([ADR-0003](0003-mask-in-the-browser-check-again-on-the-server.md)). The system keeps the masked pages. The question is whether to offer an archive of originals anyway, uploaded separately.

An archive would serve two purposes:
- **Reprocessing** after a masking bug, e.g. a result that was masked by mistake.
- **Provenance:** proof of where every number came from.

Both are mostly covered without it. Every value is shown next to its place on the masked page, and extraction can be rerun from the masked pages. Only a masking bug needs the original, and the user keeps it (e-mail, the lab's portal, their disk) and can import it again.

Standard storage encryption protects against stolen disks, not against anyone with read access in Azure, including a compromised application.

### Considered options

1. **Keep originals with storage encryption only.** The application and the subscription administrator can read every original. Weakens G1 and G5.
2. **Envelope encryption with the key in Key Vault.** Every decryption is logged, but the key lives in the same cloud as the data.
3. **Envelope encryption with an offline key pair.** Each file has its own data key, encrypted with the user's public key; the private key exists only offline. The cloud can write but never read. Needs a separate storage account, a write-only role, key rotation and regular restore tests.
4. **No archive.** Keep the masked pages only. The user keeps the original.

## Decision

We choose option 4.

1. **No original is stored or sent.** The system cannot archive one even by mistake.
2. **The SHA-256 of the original is stored** with every document. It recognises the same document imported again ([ADR-0008](0008-document-lifecycle-and-identifiers.md)), and would let a future archive be filled with old originals and matched to existing documents.
3. **If an archive is ever needed, option 3 is the design**, added as one more step of the upload.

## Consequences

- No archive storage, no key pair, no write-only role, no restore tests.
- Nothing of the original can leak from storage, backups or logs.
- Fixing a masking bug for an existing document needs the user to import the original again. This is deliberate.
- If the user loses their copy, the masked pages and the approved results remain; the original cannot be recovered from Baseline.
