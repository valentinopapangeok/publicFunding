# Systematic Funding Monitor Roadmap

Generated: 2026-09-01

## Objective

Build a public, periodically refreshed funding monitor for Geo-K that covers ESA, EU, ECMWF, LIFE/CINEA and FAO/UNGM opportunities while keeping restricted tender documents and internal bid material out of the public repository.

## Current State

Implemented:

- ESA-star public metadata monitor
- active-only filtering
- deadline urgency colour coding
- broad European / Italian scope filtering
- manufacturing-heavy exclusion terms
- GitHub Pages publication from the `gh-pages` branch

## Next Implementation Steps

1. Refactor source configuration
   Keep source definitions in `monitoring/funding-sources.json` and matching themes in `monitoring/esa-star/geok-keywords.json` plus `monitoring/geok-profile.md`.

2. Add EU Funding & Tenders monitor
   Use the public SEDIA Search API documented by the European Commission. This should cover Horizon Europe, Digital Europe, LIFE topic records and EU tenders.

3. Add ECMWF Copernicus procurement monitor
   Scrape or parse the public ECMWF Copernicus ITT update page and procurement plan links. Filter for C3S/CAMS/operational data, validation, quality control, climate evidence layers and EO processing.

4. Add LIFE/CINEA monitor
   Prefer EU Funding & Tenders topic records for structured metadata. Use CINEA pages as a fallback/summary source for deadlines and call families.

5. Add FAO/UNGM monitor
   Track FAO notices through UNGM. Confirm whether public notice search can be reliably automated without authenticated API access. If not, use a controlled browser/export approach or UNGM alert emails as an ingestion source.

6. Create a unified output schema
   Each source should produce the same fields:

   - Source
   - Provider
   - Programme
   - Call ID
   - Title
   - Status
   - Opening date
   - Deadline
   - Clarification deadline
   - Geography / eligibility
   - Instrument type
   - Consortium burden
   - Matched Geo-K themes
   - Relevance score
   - Urgency
   - Public URL
   - Notes

7. Publish one combined page
   Replace the ESA-only page with a multi-source page that supports source/theme filters and keeps the same urgency colour coding.

## Source Notes

### ESA-star

Current source. Works from the public ESA-star API for metadata. Tender packages and clarifications require ESA-star login.

### EU Funding & Tenders

The European Commission documents public REST APIs for Funding & Tenders Portal data via the SEDIA search API. This is the best source for Horizon Europe, LIFE, Digital Europe, security, space, environment and cultural-heritage opportunities.

### LIFE / CINEA

LIFE calls are published on CINEA pages and the EU Funding & Tenders Portal. For 2026, many LIFE calls list a deadline of 2026-09-22 17:00 CEST, while strategic two-stage calls list concept-note deadlines on 2026-09-03 and full-proposal deadlines on 2027-03-04. Large strategic LIFE projects should usually be downgraded for Geo-K unless Geo-K is a specialist subcontractor.

### ECMWF

ECMWF publishes Copernicus ITTs and procurement-plan information publicly. Current examples include C3S/CAMS operational data and quality-control tenders. These may be relevant when they involve data processing, validation, climate evidence layers or operational EO/climate services.

### FAO / UNGM

FAO procurement opportunities are published through UNGM. UNGM registration is required for supplier participation. Public notices can be searched manually; API automation requires further testing because the official UNGM API documentation is oriented toward authenticated agency/vendor integration.

## References

- ESA-star Publication: https://esastar-publication-ext.sso.esa.int/
- European Commission Funding & Tenders Portal APIs: https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/support/apis
- LIFE Calls for proposals 2026: https://cinea.ec.europa.eu/life-calls-proposals-2026_en
- ECMWF Copernicus procurement ITTs: https://www.ecmwf.int/en/about/suppliers/copernicus-procurement/update-itts
- FAO procurement: https://www.fao.org/unfao/procurement/en
- UNGM procurement opportunities help: https://help.ungm.org/hc/en-us/articles/360012821740-How-to-access-procurement-opportunities-on-UNGM
