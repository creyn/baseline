# 5. No archive of original documents in the first version

Date: 2026-11-17

## Status

Accepted

## Context

After [ADR-0003](0003-mask-personal-data-before-ai.md) and [ADR-0004](0004-rasterise-pdf-to-png.md), the system works on masked page images only. The question is whether to keep the 1:1 original as well.

An archived original would serve two purposes:
- **Reprocessing.** If masking or extraction had a bug, the document could be processed again.
- **Provenance.** Proof of where every number came from.

Without an archive, both are mostly covered:
- The masked page images are kept, and every value is shown next to its source on the page. This is sufficient provenance.
- Extraction can be rerun from the masked images. A new model or a fixed prompt does not need the original.
- Only a masking bug, e.g. an unknown parameter painted black, needs the original. The user keeps their original files (email, the lab's portal, local disk) and can upload the document again.

The original contains full personal and health data, so an archive must be protected as strongly as possible. Standard Azure Storage encryption protects against stolen disks, not against anyone with read permissions in Azure, including a compromised application.

### Considered options

1. **Keep the original with Azure Storage encryption only.** No work, but the application and the subscription administrator can read every original.
2. **Envelope encryption with the key encryption key (KEK) in Key Vault.** Every decryption is logged, but the key lives in the same cloud as the data, so compromising an identity with key access exposes everything.
3. **Envelope encryption with an offline key pair.** Each file is encrypted with its own data encryption key (DEK, AES-256-GCM), and the DEK is encrypted with the user's public key. The private key exists only offline, e.g. on a YubiKey. The cloud can write but never read the archive. This needs a separate storage account, a write-only custom role, a list of public keys with key rotation, and a regular restore test, because a wrong key or a bug would make the archive silently unreadable.
4. **Do not keep the original.** Keep only the masked page images. The user keeps their own copy.

## Decision

We choose option 4 for the first version.

The plaintext original exists only while it is being masked. If masking runs on the server, this is a short-lived working copy:

| | Working copy |
|---|---|
| Location | the application's Storage account, `quarantine` container |
| Encryption | DEK per file, encrypted with the `quarantine-kek` key in Key Vault |
| Who writes | the API |
| Who reads | the sanitiser only (Managed Identity, `unwrapKey` on `quarantine-kek`) |
| Retention | deleted right after successful masking. A lifecycle policy removes leftovers after 24 hours |
| Data protection | no soft delete, no blob versions, so a deleted copy is really gone |

Whether masking runs on the server or in the browser is still open. If it runs in the browser, the working copy disappears too.

For every document we store the SHA-256 hash of the original. It recognises a repeated upload of the same file, so new results replace the old ones instead of duplicating them.

### How to add an archive later

Option 3 is the intended design if an archive is ever needed. Two things prepare for it now, at almost no cost:
- **The SHA-256 hash of every original.** Old originals that the user still has can be uploaded again and matched to existing documents by their hash, so the archive can be backfilled, not only filled with new documents.
- **Upload as a sequence of steps.** Archiving becomes one more step after validation.

Adding it then means: a storage account in Bicep, encryption with the active public key, a file in the repository listing public keys (id, algorithm, key, fingerprint, created, retired), two columns on the document (archive location, key id), a local decryption script and a monthly restore test. Key rotation re-encrypts only the DEKs, not the files.

## Consequences

- Much less infrastructure and key management: no archive storage account, no key pair, no write-only role, no restore tests.
- No copy of the original is kept in the cloud, so there is nothing to leak from storage, backups or logs.
- Fixing a masking bug for an existing document requires the user to upload the original again. This is a deliberate trade-off.
- If the user loses their own copy, the masked images and the approved results remain. The original cannot be recovered from Baseline.
