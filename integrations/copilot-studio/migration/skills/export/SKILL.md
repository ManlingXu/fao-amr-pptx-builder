---
name: export-presentation-draft
description: Generate an authorized editable PowerPoint draft and check its output and delivery location.
---

After the requester confirms the current ordered plan, call CreateDraftFromPlan with the matching plan ID, expected_revision and confirmed=true. Store the job ID. Poll GetDraftStatus until the service reports completion or failure. If the requester changes template after generation, apply the selected template to the completed job with explicit confirmation and poll the new job.

Check GetLayoutReport, the returned sourceMap and any warnings. Report the actual number of pages and outstanding issues. Give the requester the authenticated webUrl returned by the service for the file when available. Report a missing output URL, access error or failed job accurately. For production acceptance, test the link using the intended requesting identity.
