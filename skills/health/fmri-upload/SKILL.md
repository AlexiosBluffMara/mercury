---
name: fmri-upload
description: Discord-side flow for the Cortex fMRI upload + auto-training pipeline. Use when a user mentions uploading an fMRI scan, NIfTI/DICOM/BIDS data, brain imaging upload, opting in to research data sharing, or asks about the status/deletion of a previously uploaded scan.
version: 1.0.0
author: Mercury
license: MIT
metadata:
  hermes:
    tags: [fmri, brain, upload, gcs, signed-url, cortex, isu, research]
    category: health
    related_skills: [cortex-bridge, brain-viz]
---

# fMRI Upload Flow

Mercury is the Discord front-end for Cortex's fMRI upload pipeline. Anyone with a
Discord account can upload a scan; Mercury mints a 15-minute signed URL via the
Cortex relay and returns it to the user. The browser uploads directly to a
CMEK-encrypted GCS bucket. Validation, storage, and (opt-in) training are all
handled server-side.

## Slash commands

| Command | Effect |
|---|---|
| `/upload-fmri <format>` | Mercury POSTs to `<RELAY>/api/fmri/upload-url` and DMs the user a signed PUT URL + curl example. Format is one of `nii`, `nii.gz`, `dcm`, `zip`, `mat`, `edf`. Rate-limited 3/hour per user. |
| `/my-uploads` | Mercury GETs `<RELAY>/api/fmri/my-uploads/{user_id}` and renders an embed listing the user's last 50 uploads with status (`pending_upload`, `validated`, `rejected`, `soft_deleted`). |
| `/opt-in-research <on|off>` | Toggles the user's `opted_in_research` flag in Firestore via `<RELAY>/api/fmri/opt-in/{user_id}`. **Default is OFF.** Only opted-in scans are eligible for TRIBE v2 fine-tuning. |
| `/delete-upload <scan_id>` | Soft-deletes the scan via `DELETE <RELAY>/api/fmri/scan/{scan_id}?user_id=<id>`. Object is purged after 30 days by the bucket lifecycle rule. |

## Routing

The Mercury → Cortex routing for scan submission already exists. For fMRI we
extend the same gateway:

```
Discord  →  Mercury slash command  →  Mercury gateway
         →  https://cortex.redteamkitchen.com/api/fmri/*
         →  Cortex relay (Cloud Run)
         →  GCS / Firestore / Cloud Function / 5090 or Vertex
```

The relay base URL is read from the `CORTEX_RELAY_URL` env var on Mercury
(default `https://cortex.redteamkitchen.com`). Every request includes the
Discord user ID so the relay can authorize ownership for `/my-uploads` and
`/delete-upload`.

## Upload UX

When `/upload-fmri` returns, the user gets an ephemeral DM containing:

1. The signed PUT URL (15-minute expiry, single use, CMEK-encrypted target).
2. A ready-to-paste `curl` line:
   ```
   curl -X PUT --upload-file scan.nii.gz \
     -H "Content-Type: application/octet-stream" \
     "<signed-url>"
   ```
3. The `scan_id` so they can poll status with `/my-uploads`.
4. A reminder of the 2 GB hard cap and supported formats.

Mercury never sees scan bytes. The DM auto-deletes the signed URL after 15 minutes.

## Privacy invariants

- Default `opted_in_research = false`.
- Mercury never logs scan content; only `scan_id`, status, and Discord user id.
- Validation errors are surfaced verbatim from the Cloud Function (they describe
  shape/header issues only — never scan content).
- DM-rejection notifications come from the Cloud Function via the
  `MERCURY_DM_WEBHOOK` secret, not from the user-facing slash command runtime.

## Failure modes

| Symptom | Cause |
|---|---|
| `400 user_id is not a valid Discord snowflake` | Mercury passed the wrong field — make sure it's the snowflake, not the username. |
| `429 Too Many Requests` | User hit the 3/hour upload-url cap. Tell them to wait. |
| Status stuck on `pending_upload` after 20 min | Browser upload failed silently or the signed URL expired. Re-issue with `/upload-fmri`. |
| Status `rejected` with empty errors | Cloud Function couldn't read the header bytes (object truncated). Re-upload. |
