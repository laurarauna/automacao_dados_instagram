# Instagram Data Pipeline & GitOps Automation

## Overview

This repository contains the automated data extraction and processing pipeline for the Casa Curadoria ecosystem. Designed from a data analytics and growth perspective, this microservice serves as the analytical engine that feeds the main front-end application (`casa_curadoria_art`). 

By decoupling the data extraction logic from the user interface, this architecture ensures high security (no API keys exposed on the client side), zero-latency data delivery, and automated historical tracking for long-term growth analysis.

## Value Proposition & Ecosystem Integration

In a data-driven growth strategy, maintaining accurate and up-to-date audience metrics is critical for B2B partnerships and content optimization. This project eliminates manual reporting workflows through a fully automated pipeline:

1. **B2B Transparency:** Automatically updates the public media kit with real-time engagement rates, impressions, and demographic data, ensuring sponsors always see accurate metrics.
2. **Historical Data Persistence:** By appending daily/monthly records to a centralized database (Google Sheets), it creates a robust time-series dataset. This enables advanced cohort analysis, growth trend mapping, and performance forecasting.
3. **Headless Architecture:** Uses a GitOps approach to push a compiled JSON payload directly to the static front-end repository. This commit automatically triggers the Vercel CI/CD pipeline to rebuild the front-end with the latest data.

## Architecture Workflow

The pipeline is orchestrated via GitHub Actions and executes the following sequence:

1. **Extraction:** A Python script authenticates with the Meta Graph API to retrieve raw account insights, media performance, and audience demographics.
2. **Processing & Aggregation:** The script processes the raw JSON response, calculates aggregate metrics (e.g., average post reach, engagement rate), and standardizes demographic labels.
3. **Persistence (Data Warehouse):** The processed dataset is appended as a new row in a secure Google Sheets document using a Service Account, serving as the historical data warehouse.
4. **GitOps Deployment:** A `.json` payload is generated and pushed directly to the root directory of the `casa_curadoria_art` repository. This commit automatically triggers the Vercel CI/CD pipeline to rebuild the front-end with the latest data.

## Extracted Metrics

The pipeline tracks and processes the following key performance indicators:

* **Audience Size & Velocity:** Total followers and 30-day growth rate.
* **Demographics:** Gender distribution, top age groups, and top geolocation data (cities).
* **Reach & Impressions:** 30-day aggregate impressions and average reach per post.
* **Engagement:** Average saves, average shares, and overall account engagement rate.

## Technology Stack

* **Language:** Python 3.10
* **APIs:** Meta Graph API (Instagram), Google Drive / Google Sheets API v4
* **Libraries:** `requests` (API consumption), `gspread`, `oauth2client` (Google Auth)
* **CI/CD & Automation:** GitHub Actions (Cron scheduling and cross-repository deployment)

## Execution Protocol

The pipeline is fully automated and runs without human intervention. 

* **Schedule:** Executes automatically on the 1st day of every month at 04:00 AM (BRT) via GitHub Actions cron job (`0 7 1 * *`).
* **Manual Trigger:** Can be executed on-demand via the GitHub Actions `workflow_dispatch` event for immediate data synchronization.
