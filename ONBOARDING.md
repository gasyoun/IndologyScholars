# 🧭 IndologyScholars Onboarding Guide

Welcome to **IndologyScholars**! This guide is designed to get you fully oriented, set up, and ready to contribute to this state-of-the-art Digital Humanities (DH) research platform and automated data pipeline.

---

## 🌟 1. Project Vision & Research Context

Historically, the Russian Indological research community has been divided into two preeminent metropolitan schools:
1. **The St. Petersburg School** (centered around the Institute of Oriental Manuscripts, IOM RAS, and Saint Petersburg State University, SPbSU), which hosts the annual **Zograf Readings** (since 2004).
2. **The Moscow School** (centered around the Institute of Oriental Studies, IAS RAS, and Russian State University for the Humanities, RSUH), which hosts the annual **Roerich Readings** (since 2007).

Before this project, their archives were fragmented, stored in raw HTML bulletins, and lacked standard naming conventions. **IndologyScholars** integrates over **22 years** of historical conference records into a single referentially-sound, 100% complete biographical relational database.

By compiling a unified dataset of **220 unique scholars** and **895 presentations**, the platform enables researchers to test quantitative sociological hypotheses (e.g. generational aging, institutional gatekeeping, gender balance, geographic mobility) and explore academic lineages through interactive visualization interfaces.

---

## ⚡ 2. Getting Started (Fast Track)

Follow these steps to get the project running locally on your machine.

### Prerequisites
- **Python 3.8+** installed.
- A modern web browser.
- **Git** installed.
- *(Optional but Recommended)* **Pandoc** and **LaTeX** (for compiling academic manuscripts to DOCX/PDF).

### Step 1: Clone the Repository & Setup Dependencies
```bash
git clone https://github.com/gasyoun/IndologyScholars.git
cd IndologyScholars
pip install -r requirements.txt
```
*Note: The dependencies are minimal (`beautifulsoup4`, `requests` for crawling; python's standard library covers SQLite3, JSON, and standard parsing).*

### Step 2: Compile and Build the entire Local Pipeline
Run the following scripts in sequence to ingest data, run analytics, compile web assets, and verify the build:
```bash
# 1. Rebuild database, parse HTML cache, and resolve deduplicated identities
python build_and_populate_db.py

# 2. Compute cohort overlap, metrics, and export analytical CSV tables
python generate_analytics.py

# 3. Export database states into JS-ready site_data.json payload
python generate_site_data.py

# 4. Generate the 220 individual static scholar HTML profile cards
python generate_scholars_pages.py

# 5. Run the publication validation script to verify referential health
python validate_publication.py
```

### Step 3: Run the Web Server Locally
Start Python's built-in lightweight HTTP server to bypass browser CORS policy restrictions on local file protocols:
```bash
python -m http.server 8000
```
Now, open your browser and navigate to: **`http://localhost:8000/`** (Landing page) and **`http://localhost:8000/networks.html`** (Interactive Network Map).

---

## 🏛️ 3. System Architecture & Modular Design

The pipeline enforces a strict **Separation of Concerns** across five distinct phases:

```
[Phase 1: Local HTML Cache] (html_cache/)
          │
          ▼ (Smart HTML parsing & regex matching)
[Phase 2: Relational Ingestion] (build_and_populate_db.py ──> conferences.db)
          │
          ├─────────────────────────┬─────────────────────────┐
          ▼                         ▼                         ▼
[Phase 3: Scientific Analytics]  [Phase 4: Static Profile]  [Phase 5: Web Portal]
 (generate_analytics.py)       (generate_scholars_pages.py)   (index.html & networks.html)
          │                         │                         │
          ▼                         ▼                         ▼
  analytics_output/*.csv      scholars/*.html               Bilingual SPA
```

### In-Depth Script Directory

*   **`build_and_populate_db.py`**: The ingestion engine. It parses manual seed metadata (`zograf-roerich-db.md`), processes all cached HTML programs, resolves spelling variations into canonical identities using regular expressions, and builds `conferences.db`.
*   **`generate_analytics.py`**: Queries `conferences.db` to calculate scholar metrics (total presentations, debut years, career spans, dominant themes) and creates scientific CSV outputs in `analytics_output/`.
*   **`generate_site_data.py`**: Compiles SQLite tables into a lightweight, highly-compressed JSON structure (`site_data.json`) loaded by the frontend web applications.
*   **`generate_scholars_pages.py`**: Compiles 220 highly structured static HTML files under `scholars/` for individual scholars.
*   **`generate_network_json.py`**: Extracts nodes and co-presence/collaboration linkages, exporting them to `analytics_output/network_data.json` for interactive rendering.
*   **`fetch_latest_programs.py`**: A crawling utility scheduled in CI/CD to scan institutional portals for newly posted programs.

---

## 🗃️ 4. Relational Database Schema (`conferences.db`)

The database uses SQLite3 and is modeled according to **Third Normal Form (3NF)** rules to ensure zero transactional redundancy.

### Database Tables (12 Entities)
1.  **`event_series`**: Tracks the two conference chains (Zograf Readings vs. Roerich Readings).
2.  **`place`**: Stores physical geographical coordinates (lat/lon) and addresses.
3.  **`organization`**: Normalized list of research institutions and universities (e.g. IOM RAS, SPbSU, IAS RAS, HSE).
4.  **`venue`**: Specific institutional venues hosted inside physical places.
5.  **`event`**: Unique annual occurrences of a conference series (e.g. Zograf Readings XLVI in 2025).
6.  **`event_day`**: Tracks daily schedules of an event.
7.  **`event_day_venue`**: Junction table hosting event days at specific venues.
8.  **`session`**: Tracks individual session names and daily structures (e.g. "Sanskrit Linguistics").
9.  **`presentation`**: Focuses on unique paper titles, online/offline status, and semantic codes.
10. **`person`**: Unified canonical scholar records detailing normalized keys, birth years, death years, and genders.
11. **`presentation_person`**: The core junction table connecting authors to their presentations. Stores raw affiliation text, resolved organization links, city tags, and session scheduling order.
12. **`media`**: Attaches external links (articles, slide decks, PDFs) to presentations.

---

## 🎨 5. Frontend & UI Design System

The web interface is designed to look **premium, modern, and visually stunning**.

### Aesthetics & Layout Principles
*   **Theme**: Sleek dark-mode aesthetic utilizing rich, translucent backdrops (**Glassmorphism**) combined with custom CSS gradients and harmonious accent colors (avoiding default primary colors).
*   **Typography**: Outfitted with modern Google Fonts (*Outfit* and *Inter*) rather than basic system font fallbacks.
*   **Client-Side Reactivity**: Filter components, tags, and pagination operate instantly in vanilla JavaScript. Clicking on any city or institutional tag dynamically filters and re-draws the catalog.
*   **Micro-Animations**: Uses subtle CSS hover scaling, box-shadow transitions, and active button scales to provide immediate micro-feedback to user interactions.

### The Bilingual Engine
Every component, table header, button, chart legend, and statistical insight supports real-time bilingual switching (Russian by default; English toggle).
*   No hardcoded English strings must remain in the Russian mode.
*   The entire translation dictionary is embedded client-side, enabling instantaneous toggling without page reloading.

### Vis.js Interactive Network Map (`networks.html`)
The interactive network map compiles all 220 scholars and their linkages into a high-performance Canvas network:
*   **Layout Presets**:
    1.  *Collaborations*: Highlights direct, explicit co-authorship networks.
    2.  *Ecosystem*: Maps the institutional overlaps and bridging researchers across St. Petersburg and Moscow.
    3.  *Co-presence*: Visualizes session-level co-presence in the same room.
    4.  *Attendance*: Tracks scholars grouped by their lifetime presentation frequency.
*   **Live Features**: Dynamic zooming, panning, live filtering by institution, quick search by Cyrillic names, and a detailed profile side panel.

---

## 📄 6. Scientific Manuscript & Hypothesis Validation

The research findings of the project are documented in the manuscript **`article/ppv_draft.md`**.

### Hypothesis-Testing Infrastructure
If you are modifying analytical code or updating demographics, you must check how it affects the **10 Research Hypotheses (H1–H10)**:
-   **`work_ppv_hypotheses.py`**: Executes advanced statistical calculations (Shannon entropy for thematic diversity, Cosine distance for session schedules, Mann-Whitney U test for debut age cohorts, and Pearson correlation for paper serialization) to validate or refine these hypotheses.
-   **Pandoc Rebuilds**: If you update `ppv_draft.md`, re-compile the academic draft to HTML and Microsoft Word formats:
    ```bash
    pandoc article/ppv_draft.md -o article/ppv_draft.html --self-contained
    pandoc article/ppv_draft.md -o article/ppv_draft.docx
    ```

---

## 🛠️ 7. Developer Guidelines & Contribution Workflow

To keep the database, codebase, and site stable and referentially integral, adhere strictly to these rules:

### Rule 1: Maintain Separation of Concerns
Never manually edit generated files:
*   Do NOT edit `scholars/*.html`, `cities/*.html`, or `institutions/*.html` directly. If you need to change a profile card, update `generate_scholars_pages.py` and run the build sequence.
*   Do NOT edit `site_data.json` directly. Re-serialize it using `generate_site_data.py`.

### Rule 2: Strict Encoding Constraints (Cyrillic Safety)
Because the codebase processes diverse Cyrillic text files, all Python scripts must include UTF-8 encoding configuration inside the entry-point to prevent terminal crashes:
```python
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
```
Always use `encoding='utf-8'` when reading or writing local files.

### Rule 3: Git Workflow & Commit Rules
*   Prefix development commits with `ai-wip:` or `feat:`/`fix:` to maintain a clean history.
*   Always run `python validate_publication.py` before pushing to ensure database integrity, checking for orphaned foreign keys and identity mismatches.

### Rule 4: CI/CD & Deployments
The repository runs a GitHub Actions workflow twice a year:
-   **June 20 (00:00 UTC)**: After the spring **Zograf Readings**.
-   **December 20 (00:00 UTC)**: After the winter **Roerich Readings**.

The workflow automatically scrapes institutional portals, regenerates the entire database, builds all web assets, and deploys the live portal to GitHub Pages.

---

## 💬 8. Welcome Aboard!

You are now equipped with a deep understanding of the system, data flows, and code patterns of **IndologyScholars**. If you have any questions or want to plan the next phase of structural extensions, explore the **`CLAUDE.md`** files for commands or run the validation checks to see everything in action!

Happy hacking! 🚀
