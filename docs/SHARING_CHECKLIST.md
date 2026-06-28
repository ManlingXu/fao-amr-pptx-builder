# Sharing Checklist

Use this checklist before sharing the FAO AMR PPTX Builder skill with another person.

## Repository Owner Checklist

- [ ] The repository contains only skill code, tests, documentation, and packaging files.
- [ ] No real FAO source materials are committed to the repository.
- [ ] No PowerPoint templates with restricted branding or confidential content are committed unless approved.
- [ ] The repository visibility is set to private if the skill is not ready for public release.
- [ ] The person who will use the skill has been invited to the repository.
- [ ] The person has accepted the GitHub invitation.
- [ ] The `main` branch contains the latest stable version.
- [ ] `docs/USER_MANUAL.md` is shared with the user.

## User Setup Checklist

- [ ] Codex is installed.
- [ ] The user can open the private GitHub repository in a browser.
- [ ] The user installs the skill with:

```text
Install the Codex skill from https://github.com/ManlingXu/fao-amr-pptx-builder/tree/main/skills/fao-amr-pptx-builder
```

- [ ] The user restarts Codex after installation.
- [ ] Python 3.10 or newer is available.
- [ ] Dependencies from `requirements.txt` are installed.
- [ ] The user has a local OneDrive-synced or local folder containing approved AMR materials.
- [ ] The user has a local `.pptx` template if template-based output is needed.

## Functional Check

Ask Codex to validate the installed skill:

```text
Validate the installed FAO AMR PPTX builder skill.
```

Then run a small test request with a small folder of non-confidential sample materials:

```text
Use the FAO AMR PPTX builder skill.

Create a 3-slide editable PPTX about:
AMR history in FAO

Deck title:
Test Deck: AMR History in FAO

Audience:
Internal test user

Materials folder:
[local path to a small approved test folder]

Template:
[local path to a PPTX template, or say no template]

Please create a first draft deck and include a source map.
```

The check is successful if Codex creates:

- `draft.pptx`
- `deck_plan.json`
- `source_map.json`

## Common Sharing Problems

GitHub access problem:
The user has not accepted the repository invitation or is signed into a different GitHub account.

Skill does not trigger:
Restart Codex after installation and mention the skill name directly in the prompt.

Missing Python package:
Install dependencies from `requirements.txt`.

OneDrive link does not work:
Use the local synced folder path instead of a browser URL.

Output is weak:
Use a smaller, more relevant materials folder and provide a clearer topic, title, audience, and slide count.
