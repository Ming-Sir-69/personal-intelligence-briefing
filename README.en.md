<picture>
  <source media="(prefers-color-scheme: dark)" srcset="readme-assets/header-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="readme-assets/header-light.svg">
  <img alt="Personal AI Industry Briefing Pipeline · ✦ EricMingle69" src="readme-assets/header-light.svg" width="100%">
</picture>

<p align="center">
  <a href="README.md">简体中文</a> · <a href="README.en.md">English</a> · <a href="PERSONAL-NOTICE.md">✦ EricMingle69</a>
</p>

# Personal AI Industry Briefing Pipeline

## Purpose

Organizes public AI industry information into traceable candidate events and plain HTML review pages, keeping candidate preparation separate from final editorial review.

## Repository guide

| Entry | Contents |
| --- | --- |
| [Public home](https://ming-sir-69.github.io/personal-intelligence-briefing/) | Read-only entry; availability depends on the current deployment |
| [Current status](https://ming-sir-69.github.io/personal-intelligence-briefing/current/status/) | Inspect the current batch and freshness |
| [Morning review](https://ming-sir-69.github.io/personal-intelligence-briefing/current/morning/) | Morning candidate information |
| [Noon review](https://ming-sir-69.github.io/personal-intelligence-briefing/current/noon/) | Noon candidate information |
| [Core source](src/intelligence_briefing/) | Candidate-processing and page implementation |
| [Page builder](scripts/build_public_pages.py) | Derived public read-only pages |
| [Project dependencies](pyproject.toml) | Version and Python requirements |

## Getting started

1. Check the current status before opening the appropriate review page.
2. Use the page’s `batch_id`, `generated_at` and `source_commit_sha` to assess freshness.
3. Local page generation requires Python ≥3.12; install and run the project in the same virtual environment:

```sh
python -m pip install -e .
python scripts/build_public_pages.py --root "$PWD"
```

## Scope and limitations

- `delivery/current/*.json` is the authoritative state; `docs/current/` is its deterministic read-only presentation.
- Failed or partial batches do not replace the previous successful pages; do not fill a failed batch with old content.
- Only public information is processed; model keys come from Actions Secrets, and the Pages deployment job receives no model keys.
- Assess availability and freshness from the actual batch and deployment; the existence of a page does not establish real-time content.

## Sources and existing licenses

The original repository has no LICENSE/NOTICE; reuse rights for code and existing material are unspecified. Retain traceable links to public sources; internal, client and personal information are outside the input scope.

---

Documentation maintained by **✦ EricMingle69** · [Ming-Sir-69](https://github.com/Ming-Sir-69)  
[Personal identity, licensing and permissions](PERSONAL-NOTICE.md) · The header follows your GitHub theme.
