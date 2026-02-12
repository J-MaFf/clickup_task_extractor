# Changelog

All notable changes to the ClickUp Task Extractor project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Markdown Export Regression**: Fixed line break handling in markdown table exports
  - Changed newline replacement strategy from two trailing spaces (`  \n`) to single spaces (` `)
  - Eliminates markdown lint violations (MD055, MD056, MD009)
  - Maintains valid table structure with consistent column counts
  - Resolves issue regression from #86 fix
  - See `MARKDOWN_LINEBREAK_FIX_SUMMARY.md` for detailed explanation

### Changed

- Markdown export now normalizes multi-line notes to single-line cells for better table compatibility
  - Multi-line content is preserved but displayed on single line
  - Example: "Line one\nLine two" → "Line one Line two"

## [1.03] - 2026-01-29

### Added

- Support for markdown exports with proper table formatting
- Initial markdown export feature with column headers
- Line break handling for multi-line task notes

### Fixed

- (#86) MD060 table separator consistency in markdown exports

## [1.02] - Previous

### Features

- Core task extraction functionality
- Multiple export formats (CSV, HTML, PDF)
- Rich console UI
- Interactive task selection
- AI summaries with Google Gemini
- 1Password integration for secure API key storage
- ETA calculation
