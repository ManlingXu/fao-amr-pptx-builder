# FAO AMR PPTX Builder User Manual

This manual is for colleagues who are new to GitHub, Codex, and Codex skills.

The short version: this repository gives Codex a reusable workflow for creating editable PowerPoint drafts about antimicrobial resistance (AMR) in the FAO context. You give Codex a topic, a title, a folder of source materials, and optionally a PowerPoint template. Codex uses the skill to build a first draft `.pptx` and a source map.

## What This Skill Does

The FAO AMR PPTX Builder helps Codex:

- Look through a local folder of AMR materials.
- Read text from previous PowerPoint decks, reports, Word documents, and text files.
- Select relevant source content for a new deck request.
- Plan a slide-by-slide outline.
- Create an editable PowerPoint file.
- Save a source map showing which source materials informed each slide.
- Revise the draft deck after you review it.

The output is an editable `.pptx` file. It is not a screenshot or a flattened image deck.

## What This Skill Does Not Do Yet

This is a working v1 skill, not a final fully automated publishing system.

It does not:

- Connect directly to OneDrive cloud links.
- Download files from Microsoft Graph.
- Automatically make old complex slides pixel-perfect in a new template.
- Automatically redraw every chart or figure as a native editable PowerPoint chart.
- Replace human review for accuracy, clearance, or FAO publication quality.

For v1, the source materials must be available as a local folder on the computer running Codex. A OneDrive-synced folder is fine.

## Key Words

GitHub:
A website where the skill files are stored and shared. You do not need to edit code in GitHub to use the skill.

Repository:
A project folder on GitHub. This skill is stored in the repository named `fao-amr-pptx-builder`.

Codex:
The AI coding assistant that can install and use skills.

Codex skill:
A small package of instructions, scripts, and references that teaches Codex how to do a specialized task.

Local folder:
A folder on your computer, such as a synced OneDrive folder.

Template:
A `.pptx` file whose layouts, fonts, colors, or visual style should guide the generated deck.

Source map:
A JSON file created with the deck. It records which source materials were used for each substantive slide.

## What You Need Before You Start

You need:

1. Access to the private GitHub repository.
2. Codex installed and running.
3. Python 3.10 or newer.
4. The Python packages listed in `requirements.txt`.
5. A local folder containing approved AMR materials.
6. A PowerPoint template file if you want the deck to follow a specific FAO template.

The repository does not include AMR source materials or FAO templates. Those stay in your local approved storage location.

## Step 1: Get Access To The Repository

If the repository is private, the owner must give you access.

Ask the owner to invite your GitHub account as a collaborator on:

```text
https://github.com/ManlingXu/fao-amr-pptx-builder
```

After accepting the invitation, you should be able to open the repository link in your browser.

If you do not have a GitHub account, ask your team lead or repository owner which account you should use.

## Step 2: Install The Skill In Codex

Open Codex and send this exact message:

```text
Install the Codex skill from https://github.com/ManlingXu/fao-amr-pptx-builder/tree/main/skills/fao-amr-pptx-builder
```

Codex should install the skill into your local Codex skills folder.

After installation, restart Codex. Restarting is important because Codex discovers new skills when it starts.

## Step 3: Install Python Dependencies

The skill uses Python scripts to read files and create PowerPoint decks.

In Codex, ask:

```text
Install the Python dependencies for the FAO AMR PPTX builder skill from requirements.txt.
```

If Codex asks for permission to run the install command, approve it if you trust the repository and are working on your own machine.

The dependencies are:

```text
python-pptx
python-docx
pypdf
```

These packages let the skill create PowerPoint files and extract text from PowerPoint, Word, and PDF materials.

## Step 4: Prepare Your Materials Folder

Create or identify one local folder that contains the approved AMR materials you want Codex to use.

Good examples:

```text
C:\Users\YourName\OneDrive - FAO\AMR materials
C:\Users\YourName\Documents\FAO AMR sources
```

The folder can include:

- `.pptx` previous presentation decks
- `.pdf` reports
- `.docx` Word documents
- `.txt`, `.md`, or `.html` notes

Tips:

- Put the most relevant materials in the folder before asking Codex to draft.
- Remove unrelated files if they may confuse the deck.
- Do not put confidential materials in the folder unless the deck is allowed to use them.
- Avoid temporary Office files such as files beginning with `~$`.

## Step 5: Prepare Your Template

If you have an FAO PowerPoint template, keep it as a local `.pptx` file.

Example:

```text
C:\Users\YourName\Desktop\FAO_AMR_Template.pptx
```

The skill will use the template as the visual system. It will create editable slides using the template layouts when possible.

If you do not provide a template, the skill can still create a simple editable deck, but it may not match FAO visual style.

## Step 6: Give Codex A Good Deck Request

For best results, give Codex:

1. The theme or topic.
2. The exact deck title.
3. The audience.
4. The preferred number of slides.
5. The local materials folder path.
6. The template `.pptx` path.
7. Any style preference.

Use this prompt pattern:

```text
Use the FAO AMR PPTX builder skill.

Create an editable PPTX about:
[theme or topic]

Deck title:
[exact title]

Audience:
[audience]

Preferred length:
[number of slides]

Materials folder:
[local folder path]

Template:
[local template path]

Style:
[brief style preference]

Please create a first draft deck and include a source map.
```

Example:

```text
Use the FAO AMR PPTX builder skill.

Create an editable PPTX about:
AMR history in FAO

Deck title:
FAO's Role in the Global AMR Response: History, Milestones, and Next Steps

Audience:
Senior FAO managers

Preferred length:
10 slides

Materials folder:
C:\Users\YourName\OneDrive - FAO\AMR materials

Template:
C:\Users\YourName\Desktop\FAO_AMR_Template.pptx

Style:
Concise, visual, suitable for a management briefing.

Please create a first draft deck and include a source map.
```

## What Codex Creates

Codex should create an output folder, usually under:

```text
outputs\fao-amr-pptx\[topic-name]\
```

The important files are:

```text
draft.pptx
deck_plan.json
source_map.json
```

`draft.pptx`:
The editable PowerPoint deck.

`deck_plan.json`:
The slide-by-slide content plan.

`source_map.json`:
The traceability file showing which source materials supported each slide.

## How To Review The First Draft

Open `draft.pptx` in PowerPoint.

Check:

- Is the topic correct?
- Is the title correct?
- Is the deck length appropriate?
- Are the slides in a logical order?
- Are any important FAO AMR milestones missing?
- Are any claims too vague or unsupported?
- Does the style fit the audience?
- Does the deck need more visuals, fewer bullets, or more technical detail?

Also open or ask Codex to summarize `source_map.json` if you want to understand where the content came from.

## How To Ask For Revisions

After reviewing, give Codex specific revision instructions.

Examples:

```text
Use the FAO AMR PPTX builder skill to revise the previous deck. Make it shorter, around 7 slides, and focus more on FAO milestones before 2020.
```

```text
Revise the draft deck. The audience is technical AMR officers, so add more detail on surveillance, responsible antimicrobial use, and the One Health approach.
```

```text
Revise the deck to make it more visual and less text-heavy. Keep the source map.
```

```text
Revise slide 4. It needs to explain why AMR matters for agrifood systems, not only human health.
```

The skill has a revision script that can update the deck plan while keeping source traceability.

## Good Prompt Examples

Short management briefing:

```text
Use the FAO AMR PPTX builder skill. Create an 8-slide editable PPTX titled "FAO AMR Work: Key Messages for Senior Management" using my AMR materials folder and this FAO template. Keep it concise and strategic.
```

History deck:

```text
Use the FAO AMR PPTX builder skill. Create a 10-slide deck on "AMR history in FAO" using previous PPTs first and reports for supporting facts. Include a timeline-style structure if the sources support it.
```

Technical deck:

```text
Use the FAO AMR PPTX builder skill. Create a technical briefing on FAO AMR work in agrifood systems. Audience: AMR specialists. Include source traceability and keep claims grounded in the source materials.
```

Evidence-gap request:

```text
Use the FAO AMR PPTX builder skill. Create a deck about [topic]. If the materials folder does not contain enough evidence, create an evidence-gap deck instead of inventing content.
```

## Troubleshooting

Problem: Codex says it cannot find the materials folder.

What to do:
Check that the folder path is a local Windows path, not only a OneDrive web link. Open the folder in File Explorer and copy the path from the address bar.

Problem: Codex says the skill is not installed.

What to do:
Install the skill again using the GitHub URL, then restart Codex.

Problem: GitHub access fails.

What to do:
Make sure you accepted the repository invitation and can open the repository in your browser. For private repositories, Codex may need your existing GitHub credentials or a token.

Problem: Python package is missing.

What to do:
Ask Codex to install the dependencies from `requirements.txt`.

Problem: The output deck is too generic.

What to do:
Narrow the materials folder to the most relevant source materials and give a more specific topic, title, audience, and slide count.

Problem: The output deck does not match the old slides exactly.

What to know:
This is expected in v1. The skill rebuilds editable slides into the selected template. It does not copy every old slide design pixel-perfectly.

Problem: The deck has an evidence-gap slide instead of a full deck.

What to know:
That means the indexed materials did not contain enough relevant FAO AMR evidence for the requested topic. Add better source materials or change the topic.

## Privacy And Source Safety

Do not commit FAO source materials, internal reports, or templates to this repository unless your team has approved that.

Recommended practice:

- Keep the skill code in GitHub.
- Keep source materials in approved OneDrive or local folders.
- Give Codex the local folder path when generating a deck.
- Review every generated deck before sharing it.

## Owner Notes

If you are the repository owner:

- Keep the repository private until the team agrees it can be public.
- Invite only users who should access the skill.
- Do not upload confidential AMR materials to this repository.
- Keep `main` as the stable branch for installation.
- After updating the skill, ask users to reinstall or update their local copy and restart Codex.

## Quick Checklist For Each Deck Request

Before asking Codex to create a deck, prepare:

- Topic or theme
- Exact deck title
- Audience
- Preferred slide count
- Local source materials folder
- PowerPoint template path
- Any style preference

Then ask Codex to use the FAO AMR PPTX Builder skill.
