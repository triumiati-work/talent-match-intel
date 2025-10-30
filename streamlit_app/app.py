# streamlit_app/app.py
import os
import uuid
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from dotenv import load_dotenv
from utils.db import load_sql, run_parameterized_sql

# Load local env (key.env) if exists, else rely on Streamlit secrets
if os.path.exists("../key.env"):
    load_dotenv(dotenv_path="../key.env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# DATABASE_URL must be set in key.env

st.set_page_config(page_title="Talent Match Dashboard", layout="wide")
st.title("🎯 Talent Match Dashboard")

with st.sidebar:
    st.header("Job vacancy inputs")
    role_name = st.text_input("Role name", value="")
    job_level = st.text_input("Job level", value="")
    role_purpose = st.text_area("Role purpose", value="")
    benchmark_input = st.text_input("Selected benchmark employee IDs (comma-separated)", value="")
    if st.button("Run Analysis"):
        run_click = True
    else:
        run_click = False

def generate_job_profile(role_name, job_level, role_purpose):
    if not GROQ_API_KEY:
        return "Groq API key not configured."
    prompt = f"""
    Generate an actionable job profile for:
    Role: {role_name}
    Level: {job_level}
    Purpose: {role_purpose}

    Include: Job Overview, Key Responsibilities, Core Competencies, Success Attributes, Assessment Focus.
    """
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    data = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
    try:
        res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=30)
        res.raise_for_status()
        out = res.json()
        return out["choices"][0]["message"]["content"]
    except Exception as e:
        st.error(f"Groq API error: {e}")
        return ""

# Run analysis
if run_click:
    # basic validation
    if not role_name or not job_level or not role_purpose or not benchmark_input:
        st.error("Please fill all fields and provide benchmark employee IDs (comma-separated).")
        st.stop()

    # parse benchmark ids into list
    benchmark_ids = [s.strip() for s in benchmark_input.split(",") if s.strip()]
    if len(benchmark_ids) == 0:
        st.error("Provide at least one benchmark employee id.")
        st.stop()

    job_vacancy_id = str(uuid.uuid4())
    st.success(f"Job Vacancy ID: {job_vacancy_id}")

    # 1) AI Job profile
    with st.expander("🧠 AI-Generated Job Profile (open)"):
        with st.spinner("Generating job profile..."):
            profile_text = generate_job_profile(role_name, job_level, role_purpose)
            st.markdown(profile_text)

    # 2) Run parameterized SQL
    sql_path = "queries/talent_match.sql"
    sql = load_sql(sql_path)

    # Prepare params — SQL expects benchmark_employee_ids as text[]
    params = {
        "role_name": role_name,
        "job_level": job_level,
        "role_purpose": role_purpose,
        "benchmark_employee_ids": benchmark_ids  # list -> will be bound as array
    }

    with st.spinner("Running Talent Match SQL (this may take a few seconds)..."):
        try:
            df = run_parameterized_sql(sql, params)
        except Exception as e:
            st.error(f"SQL execution error: {e}")
            st.stop()

    if df.empty:
        st.warning("No results returned from DB. Check inputs and that the profiles_psych table has data.")
        st.stop()

    # 3) Ranked Talent List (one row per employee could be multiple rows per TV)
    st.subheader("🏆 Ranked Talent List (per TV rows included)")
    # show an employee-level ranking (unique)
    ranked_employees = (
        df[["employee_id", "fullname", "position", "final_match_rate"]]
        .drop_duplicates(subset=["employee_id"])
        .sort_values("final_match_rate", ascending=False)
    )
    st.dataframe(ranked_employees, use_container_width=True)

    # detail view for a selected employee
    selected_emp = st.selectbox("Select employee for details", ranked_employees["employee_id"])
    emp_rows = df[df["employee_id"] == selected_emp]
    st.write("Detailed TV-level rows for the selected employee:")
    st.dataframe(emp_rows[["tgv_name", "tv_name", "baseline_score", "user_score", "tv_match_rate"]], use_container_width=True)

    # 4) Visuals
    st.subheader("📊 Visualizations")

    # final match distribution (employee-level)
    final_df = ranked_employees.copy()
    fig_hist = px.histogram(final_df, x="final_match_rate", nbins=12, title="Distribution of Final Match Rates")
    st.plotly_chart(fig_hist, use_container_width=True)

    # TGV summary: average TGV match across employees
    tgv_summary = df.groupby("tgv_name").tgv_match_rate.mean().reset_index().sort_values("tgv_match_rate", ascending=False)
    fig_tgv = px.bar(tgv_summary, x="tgv_name", y="tgv_match_rate", title="Average TGV Match Rate")
    st.plotly_chart(fig_tgv, use_container_width=True)

    # radar: compare top candidate vs benchmark (100 per TGV)
    top_emp = ranked_employees.iloc[0]["employee_id"]
    emp_tgv = df[df["employee_id"] == top_emp].groupby("tgv_name").tv_match_rate.mean().reset_index()
    categories = emp_tgv["tgv_name"].tolist()
    values = emp_tgv["tv_match_rate"].tolist() if "tv_match_rate" in emp_tgv.columns else emp_tgv["tgv_match_rate"].tolist()
    # ensure full circle
    fig_radar = px.line_polar(r=values + [values[0]], theta=categories + [categories[0]], line_close=True, title="Top Candidate vs Benchmark (radar)")
    st.plotly_chart(fig_radar, use_container_width=True)

    # 5) Insights summary (quick)
    st.subheader("📌 Quick Insights")
    st.markdown(f"- **Top candidate**: {ranked_employees.iloc[0]['fullname']} — **{ranked_employees.iloc[0]['final_match_rate']:.2f}%**")
    st.markdown(f"- **Median match rate**: {ranked_employees['final_match_rate'].median():.2f}%")
