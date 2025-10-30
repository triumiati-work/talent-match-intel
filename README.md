# 🎯 Talent Match Benchmarking System (Streamlit, Groq, Supabase)

Talent Match is a data-driven system for talent benchmarking, combining robust SQL logic with Generative AI to evaluate employee psychometric profiles against high-performing role models. It provides match rates and actionable visualizations to support objective talent decisions (hiring, promotion, and development).

## Features

### Role Definition & Benchmarking

- **AI-Powered Job Profiles:** Uses the Groq LLM (Llama 3.1) to generate detailed role requirements and key competencies based on simple user input, defining the target profile shape.
- **Objective Benchmark:** Automatically identifies high-performers (`rating = 5` in the database) and uses their **median psychometric scores** to set a statistically sound ideal benchmark.

### Analysis & Visualization

- **Talent Ranking:** Ranks all employees based on their **Final Match Rate**, showing alignment with the benchmark standard.
- **Insight Visualization:** Presents a **Competency Radar Chart** to visualize a candidate's profile shape, quickly identifying psychometric strengths and gaps against the ideal benchmark.
- **Detailed Metrics:** Provides granular data including `tv_match_rate` (trait level) and `tgv_match_rate` (group level) for in-depth analysis.

---

## Tech Stack

- **Front-End/Dashboard:**
  - **Streamlit:** Python library used to create the interactive web application and user interface.

- **Back-End & Data:**
  - **PostgreSQL/Supabase:** Used as the primary data store for employee data, performance records, and psychometric profiles.
  - **SQLAlchemy:** Python library used to establish a robust connection and execute complex SQL queries against the database.
  - **Custom SQL Logic:** The core benchmarking algorithm is executed via a complex SQL query (`talent_match.sql`) within the database.

- **Generative AI:**
  - **Groq LLM (Llama 3.1):** Used for generating the structured, narrative job profiles and competency descriptions.

---

## Setup Instructions

### 1. Prerequisites

Ensure you have the following installed:

* **Python (3.9+):** The application is built with Python.
* **API Key for LLM:** A **Groq API Key** is required for the Generative AI component.
* **Database Access:** Access to a Supabase/PostgreSQL instance containing the required schema (detailed below).

### 2. Clone the Repository

Start by cloning the project to your local machine:

git clone https://github.com/triumiati-work/talent-match-intel.git
cd talent-match-intel