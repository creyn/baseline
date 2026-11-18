# 3. Mask all personal data before any AI service

Date: 2026-11-17

## Status

Accepted. Steps 2, 4 and 6 amended by [ADR-0006](0006-zone-based-masking.md): zone-based masking replaces the word-level allowlist and the user's known identifiers.

## Context

Lab results are health data, a special category of personal data under GDPR (Art. 9). Besides the results, a document contains personal data of several people:
- the patient: full name, PESEL (Polish national ID number), date of birth, address, phone number,
- the referring doctor and the lab staff: names, licence numbers (NPWZ), stamps, signatures,
- identifiers that can be linked back to a person: order and sample numbers, barcodes and QR codes.

Facts about Azure services (as of 2026-11-17):
- **Azure OpenAI** stores prompts in an abuse-monitoring data store by default, where humans may review them. Opting out is available only to managed customers working with a Microsoft account team, so it is not available to an individual. Sources: [abuse monitoring](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/abuse-monitoring), [limited access](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/limited-access).
- **Document Intelligence** keeps input data for up to 24 hours, and it cannot be deleted earlier. Source: [data privacy](https://learn.microsoft.com/en-us/legal/cognitive-services/document-intelligence/data-privacy-security).
- **The Azure Health Data Services de-identification service** works on text, not images, has a 50 KB request limit and, according to a third-party source, supports English only. Source: [overview](https://learn.microsoft.com/en-us/azure/healthcare-apis/deidentification/overview).

Requirement: maximum security. **No personal data of anyone** may reach a managed AI service. Only what is needed to read the results may pass: parameter names, values, units, reference ranges, sample and result dates, and the lab's name.

**Terms used in this ADR:**
- **In-house** means code we write and run ourselves, in our own container, in our own Azure subscription, with no internet access. Data processed in-house is read only by our code and is not retained by any third-party service. It does not mean the user's computer.
- **Managed AI service** means a service such as Azure OpenAI or Document Intelligence, which processes and retains data under its own rules.

### Considered options

1. **No masking, rely on Azure's contractual commitments.** Simplest, but personal data ends up in the abuse-monitoring store.
2. **Mask text after Document Intelligence.** The LLM never sees personal data, but Document Intelligence sees the whole document.
3. **Azure de-identification service.** Managed and ready-made, but supports neither Polish nor images, and data reaches the service before it is masked.
4. **In-house NER model**, e.g. Microsoft Presidio. Detects names it has never seen, but it is probabilistic, and its accuracy on Polish documents is unknown. A missed name leaks.
5. **Denylist: in-house OCR and deterministic matching of the user's known identifiers.** Fully testable, but masks only the user's own data. The doctor's name, stamps, signatures and barcodes would pass through.
6. **Allowlist (deny by default): in-house OCR, keep only what the results need, mask everything else.** The denylist from option 5 runs as a second layer.

## Decision

We choose option 6. Masking runs in the isolated sanitiser container (Python), on the page images produced by [ADR-0004](0004-rasterise-pdf-to-png.md).

1. **In-house OCR** (Tesseract, Polish language pack) reads words with their positions.
2. **Allowlist.** A word stays visible only if it is:
   - a known parameter name or part of one (dictionary maintained in the repository, mapped to LOINC codes later),
   - a number, a unit, a reference range or a result flag (e.g. `H`, `L`, `↑`),
   - a sample or result date, recognised by its label (e.g. "Data pobrania"),
   - a lab name or a fixed header from the dictionary.

   Every other word is masked, including names, addresses, licence numbers and dates of birth.
3. **Non-text regions are always masked.** Stamps, signatures, logos, barcodes and QR codes are detected as image regions that OCR cannot read as allowed words, and are painted black. Barcodes may encode identifiers, so they are never kept.
4. **Denylist as a second layer.** The user's known identifiers (stored as a secret in Key Vault, never in the repository) are matched with tolerance for OCR errors. A regular expression detects PESEL numbers and verifies their checksum. A hit is masked even inside a region the allowlist would keep, such as a PESEL printed in a numeric column.
5. Masking is burned into the pixels, not an overlay.
6. **Leak check:** a second OCR pass runs on the masked image. The document is stopped for manual handling (fail-closed) if it finds a denylist hit, a valid PESEL, or any word outside the allowlist.
7. Only the masked image is sent to Document Intelligence and the LLM.

## Consequences

- No managed AI service ever sees personal data, whoever it belongs to: the patient, the doctor or the lab staff.
- The default is to mask. An error in the dictionary hides too much, not too little: an unknown parameter name shows up as a black box on the review screen. The user adds it to the dictionary and reprocesses the document.
- The parameter dictionary becomes part of the system and needs maintenance for every new lab and every new test.
- The approach does not depend on knowing who the user is, so it also works for more than one user.
- Masking is deterministic, so it can be fully tested. The leak check doubles as an eval suite.
- The sanitiser container with Tesseract is an additional component to build and maintain.
- An OCR error may cause a word to be misread. For the allowlist this means more masking. For the denylist, fuzzy matching and the leak check reduce the risk but do not eliminate it. The review screen shows the masked image, so the user sees any leak.
- The lab's name passes through. It identifies an organisation, not a person.
