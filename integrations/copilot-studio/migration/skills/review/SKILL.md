---
name: review-presentation-plan
description: Check selected slides, template feasibility and source coverage before a user confirms a revision.
---

Use GetPresentationPlan to load the current revision and AnalyzeSlides to inspect supported content types and density. Compare the requested slide count and reporting period with the actual selection. Preserve evidence excerpts and sources. Identify missing dates, duplicated claims, unfilled sections and template constraints. Ask the requester to confirm the exact ordered revision before generation.

For an uploaded template, route the file through the approved file-input topic and UploadTemplate. Only use layoutNames returned for that template. Store the returned templateId with the plan. Acquire fresh confirmation after a change to the deck’s contents or template.
