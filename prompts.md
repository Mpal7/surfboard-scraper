**Prompt 1 for the Agent:**

> Build a full-stack web application that scrapes surfboard sales ads from **[https://www.subito.it/](https://www.subito.it/)** and displays them in a user-friendly interface.
>
> **Step-by-step requirements:**
>
> 1. **Scraping Module:**
>
>    * Use Python with **BeautifulSoup** or **Playwright** for scraping.
>    * Collect the following fields from each surfboard ad (when available):
>
>      * Model
>      * Size (length, volume, or both)
>      * Price
>    * Scrape only ads located in **Rome and within an 80 km radius**.
>    * Implement **non-aggressive scraping practices**:
>
>      * Respect `robots.txt` guidelines.
>      * Add random delays between requests.
>      * Use realistic user-agent headers.
> 2. **Data Storage:**
>
>    * Store scraped data in a database (SQLite for simplicity or PostgreSQL for production).
>    * Include fields: id, model, size, price, location, link to ad, timestamp of scraping.
> 3. **Backend API:**
>
>    * Use **FastAPI** or **Flask** to serve the scraped data via a REST API.
>    * Endpoints:
>
>      * `/ads` → List all ads with pagination.
>      * `/ads/filter` → Filter by model, size range, and price range.
>      * `/refresh` → Trigger a new scrape (with proper rate limiting).
> 4. **Frontend:**
>
>    * Use **React** or **Vue.js**.
>    * Display ads in a searchable, filterable list/table.
>    * Show key details (model, size, price, location, link to original ad).
> 5. **Additional Requirements:**
>
>    * Implement a periodic update mechanism (e.g., cron job or scheduled task).
>    * Ensure the UI is clean and minimal.
>    * Include a README with instructions to set up, run, and configure the scraper radius and city filter.
>
> **Deliverables:**
>
> * Fully functional web application (scraper, API, frontend).
> * Source code in a single repository with clear structure.
> * Instructions for local deployment (Dockerfile optional).

---

