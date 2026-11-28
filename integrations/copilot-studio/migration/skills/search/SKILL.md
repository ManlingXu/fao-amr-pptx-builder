---
name: search-presentation-evidence
description: Find candidate slides for a requested briefing, including multilingual and historical searches.
---

Collect topic, named entities, intended audience, language, reporting period and requested length. Preserve place and species names. Form a focused query per section. Offer English and original-language search terms when the corpus uses mixed languages.

Call SearchSlides with each query. Use latest_only for an up-to-date brief; query historical versions explicitly for trends. Keep slideId, deckName, slideNumber, snippet, url, reportDate, effectiveYear and dateReason together. Call GetSlideVersions when two versions offer conflicting figures or dates. Treat a missing date as unknown. Return a shortlist and identify sections without sufficient evidence.
