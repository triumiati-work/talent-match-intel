Talent Match Benchmarking System

This project implements a data-driven system for talent benchmarking, combining robust SQL logic with Generative AI to evaluate employee psychometric profiles against high-performing role models. The system generates match rates and actionable visualizations to support objective talent decisions (hiring, promotion, and development).

1. Features

Objective Benchmarking: Automatically identifies top performers (rating = 5 in performance_yearly) and uses their median psychometric scores to set the ideal benchmark.

AI-Powered Job Profiles: Uses the Groq LLM (Llama 3.1) to generate detailed role requirements and key competencies based on simple user inputs.

Talent Ranking: Ranks all employees based on their Final Match Rate, showing alignment with the benchmark standard.

Insight Visualization: Presents a Competency Radar Chart to visualize a candidate's profile shape and identify gaps.

Detailed Metrics: Provides granular data including tv_match_rate (trait level) and tgv_match_rate (group level).

2. Prerequisites

Before setting up the project, ensure you have the following installed and configured:

Python (3.9+): The application is built using Python.

Supabase/PostgreSQL Access: The application requires access to a PostgreSQL database (typically a Supabase instance) containing the required data tables.

API Key for LLM: A Groq API Key is required for the Generative AI component (job profile creation).

3. Setup and Installation

A. Clone the Repository

git clone <your-repository-url>
cd talent-match-benchmarking


B. Install Dependencies

Install all necessary Python packages using pip.

pip install -r requirements.txt


(Note: If you don't have a requirements.txt, you will need to install the dependencies manually: streamlit pandas plotly-express requests python-dotenv supabase sqlalchemy)

C. Database Schema

The application relies on the following tables and columns in your PostgreSQL database. You must ensure this schema is present and populated with data.

Table Name

Critical Columns

Purpose

employees

employee_id, directorate_id, position_id, grade_id

Core employee metadata.

performance_yearly

employee_id, rating

Used to identify the high-performer benchmark group (rating = 5).

profiles_psych

employee_id, iq, gtq, tiki, etc.

Contains the raw psychometric scores (Talent Variables).

dim_positions, etc.

position_id, name

Lookup tables for displaying descriptive titles.

D. SQL Logic Files

Ensure the directory structure contains the necessary SQL file, which holds the benchmarking algorithm:

.
└── queries/
    └── talent_match.sql


(The file you developed, e.g., talent_match_all_employees_simplified.sql, should be used here, replacing the original talent_match.sql.)

4. Configuration

The application reads critical service keys and connection strings from environment variables. You must create a file named key.env in the root directory of the project and populate it with your credentials:

# key.env

# --- Supabase / PostgreSQL Credentials ---
# Note: SUPABASE_URL and SUPABASE_KEY are used by the Python Supabase client.
SUPABASE_URL="[https://your-supabase-project-ref.supabase.co](https://your-supabase-project-ref.supabase.co)"
SUPABASE_KEY="your_anon_public_key_here"

# Note: DATABASE_URL is the full connection string used by SQLAlchemy for the main queries.
# Format: postgresql://[user]:[password]@[host]:[port]/[database_name]
DATABASE_URL="postgresql://postgres:[password]@db.your-supabase-project-ref.supabase.co:5432/postgres"

# --- LLM Service (Groq) Credentials ---
GROQ_API_KEY="sk_gq_your_groq_api_key_here"


5. Running the Application

Once the dependencies are installed and the key.env file is configured, you can launch the Streamlit dashboard from your terminal:

streamlit run app.py


The application will open in your web browser, typically at http://localhost:8501. You can then interact with the dashboard to define a target role and view the benchmark analysis.