---
name: author-presentation-plan
description: Translate an approved-source brief into an ordered, editable plan and revise it within one conversation.
---

Propose section titles, evidence needs and requested counts. Use PlanPresentation to establish the plan. Store the returned planId and revision in the current conversation. The section query drives retrieval. Review selected pages against the actual scope, period, audience and language.

To revise, fetch the current plan and call RevisePresentationPlan with expected_revision and the complete ordered sections. Supply only slide_ids returned by tools. If a conflict occurs, reload the latest revision and present the differences for review. Return the ordered outline, source deck, page, date and any evidence gaps. For rewritten slides, translated content or generated notes, confirm these features are available through deployed tools before promising them.
