import os
import uuid
import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from dotenv import load_dotenv
from supabase import create_client
from sqlalchemy import create_engine, text

# =============================================================================
# 1. CONFIGURATION - Load Environment Variables
# =============================================================================

def load_config():
    """Load configuration from local .env file or Streamlit secrets"""
    try:
        # Try loading from local file first (for development)
        # Look for key.env in the same directory as this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_env_path = os.path.join(script_dir, "key.env")
        
        if os.path.exists(local_env_path):
            load_dotenv(dotenv_path=local_env_path, override=True)
            config = {
                "SUPABASE_URL": os.getenv("SUPABASE_URL"),
                "SUPABASE_KEY": os.getenv("SUPABASE_KEY"),
                "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
                "DATABASE_URL": os.getenv("DATABASE_URL")
            }
        else:
            # Fall back to Streamlit secrets (for production)
            config = {
                "SUPABASE_URL": st.secrets.get("SUPABASE_URL"),
                "SUPABASE_KEY": st.secrets.get("SUPABASE_KEY"),
                "GROQ_API_KEY": st.secrets.get("GROQ_API_KEY"),
                "DATABASE_URL": st.secrets.get("DATABASE_URL")
            }
        
        # Validate all required keys are present
        missing_keys = [k for k, v in config.items() if not v]
        if missing_keys:
            st.error(f"❌ Missing configuration keys: {', '.join(missing_keys)}")
            st.stop()
        
        return config
    
    except Exception as e:
        st.error(f"❌ Configuration error: {e}")
        st.stop()

# Load configuration
config = load_config()

# =============================================================================
# 2. DATABASE CONNECTION
# =============================================================================

@st.cache_resource
def get_db_engine():
    """Create and cache database engine"""
    try:
        engine = create_engine(
            config["DATABASE_URL"],
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        st.error(f"❌ Database connection failed: {e}")
        st.stop()

engine = get_db_engine()

# =============================================================================
# 3. SUPABASE CLIENT
# =============================================================================

supabase = create_client(config["SUPABASE_URL"], config["SUPABASE_KEY"])

# =============================================================================
# 4. UTILITY FUNCTIONS
# =============================================================================

def load_sql(filename):
    """Loads a SQL query from the queries directory."""
    try:
        # Determine the absolute path to the directory where app.py resides
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Construct the full path to the SQL file
        file_path = os.path.join(script_dir, "queries", filename)
        
        with open(file_path, 'r') as f:
            return f.read()
            
    except FileNotFoundError:
        st.error(f"❌ SQL file not found: queries/{filename}")
        st.stop()
    except Exception as e:
        st.error(f"❌ Error loading SQL file: {e}")
        st.stop()

def run_query(sql: str, params: dict = None) -> pd.DataFrame:
    """Execute parameterized SQL query and return DataFrame"""
    try:
        with engine.connect() as conn:
            if params:
                stmt = text(sql)
                df = pd.read_sql(stmt, conn, params=params)
            else:
                df = pd.read_sql(sql, conn)
        return df
    except Exception as e:
        st.error(f"❌ Query execution error: {e}")
        raise

def generate_job_profile(role_name: str, job_level: str, role_purpose: str) -> str:
    """Generate job profile using Groq API"""
    prompt = f"""Generate an actionable job profile for:

Role: {role_name}
Level: {job_level}
Purpose: {role_purpose}

Include:
- Job Requirements
- Job Description
- Key Competencies

Format the response in clear markdown."""

    headers = {
        "Authorization": f"Bearer {config['GROQ_API_KEY']}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        st.error(f"❌ Groq API error: {e}")
        return "Error generating job profile. Please try again."

# =============================================================================
# 5. STREAMLIT UI
# =============================================================================

st.set_page_config(page_title="Talent Match Dashboard", layout="wide")
st.title("🎯 Talent Match Dashboard")

# Sidebar inputs
with st.sidebar:
    st.header("Job Vacancy Inputs")
    
    role_name = st.text_input("Role Name", value="", placeholder="e.g., Senior Data Analyst")
    job_level = st.text_input("Job Level", value="", placeholder="e.g., Senior")
    role_purpose = st.text_area(
        "Role Purpose", 
        value="",
        placeholder="Describe the main purpose this role...",
        height=150
    )
    
    st.divider()
    
    # Load employee IDs only
    if role_name:
        # Load employee IDs filtered by role_name
        try:
            sql_filter = """
                SELECT 
                    e.employee_id
                FROM 
                    employees e
                JOIN
                    dim_positions dp ON e.position_id = dp.position_id
                WHERE 
                    dp.name ILIKE :role_pattern
                ORDER BY e.employee_id
            """
            
            # Pass the role name with wildcards for matching
            params_filter = {"role_pattern": f"%{role_name}%"}

            # Assuming run_query is correctly defined and handles parameters
            emp_df = run_query(sql_filter, params=params_filter)
            emp_ids = emp_df["employee_id"].tolist()
            
            # Use the filtered list for the multiselect
            benchmark_ids = st.multiselect(
                f"Select Benchmark IDs (Matching **'{role_name}'**)",
                options=emp_ids,
                max_selections=3,
                help=f"Choose up to 3 employee IDs with a position similar to '{role_name}'."
            )
            
        except Exception as e:
            st.error(f"❌ Error loading filtered employee IDs: {e}")
            benchmark_ids = []
            
        if not emp_ids:
            st.warning(f"No benchmark employees found for the role: **{role_name}**.")
            
    else:
        # If no role name is entered, display a prompt and an empty list
        st.info("Enter a **Role Name** above to load matching benchmark employees.")
        benchmark_ids = []
        

# =============================================================================
# 6. MAIN ANALYSIS - Conditional Execution
# =============================================================================

# Check if the essential parameters are filled before running the analysis.
# We require a Role Name and at least one Benchmark Employee ID.
if role_name and benchmark_ids:
    
    job_vacancy_id = str(uuid.uuid4())
    st.success(f"✅ Job Vacancy ID: `{job_vacancy_id}`")

    # Tab layout for better organization
    tab1, tab2, tab3, tab4 = st.tabs(["🧠 AI Job Profile", "🏆 Talent Ranking", "📊 Visualizations", "📌 Insights"])

    # -------------------------------------------------------------------------
    # Content for Tab 1 (AI Job Profile)
    # -------------------------------------------------------------------------
    with tab1:
        with st.spinner("Generating AI job profile..."):
            # Ensure generate_job_profile is correctly defined elsewhere and potentially cached
            profile_text = generate_job_profile(role_name, job_level, role_purpose)
            st.markdown(profile_text)

    # -------------------------------------------------------------------------
    # Content for Tab 2 (Talent Ranking)
    # -------------------------------------------------------------------------
    with tab2:
        # Load and execute SQL
        sql = load_sql("talent_match.sql")
        params = {
            "role_name": role_name,
            "job_level": job_level,
            "role_purpose": role_purpose,
            "benchmark_employee_ids": benchmark_ids
        }
        
        with st.spinner("Running talent match analysis..."):
            df = run_query(sql, params)
        
        if df.empty:
            st.warning("⚠️ No results found. Please check your inputs and ensure the database has relevant data.")
        
        else:
            # Ranked talent list
            st.subheader("Top Matching Candidates")
            
            ranked_employees = (
                df[["employee_id", "fullname", "position", "final_match_rate"]]
                .drop_duplicates(subset=["employee_id"])
                .sort_values("final_match_rate", ascending=False)
                .reset_index(drop=True)
            )
            
            # Add rank column
            ranked_employees.insert(0, "Rank", range(1, len(ranked_employees) + 1))
            
            st.dataframe(
                ranked_employees,
                use_container_width=True,
                hide_index=True
            )
            
            # Employee detail view
            st.divider()
            st.subheader("Candidate Details")
            
            selected_emp = st.selectbox(
                "Select a candidate to view detailed breakdown",
                ranked_employees["employee_id"],
                format_func=lambda x: f"{x} — {ranked_employees[ranked_employees['employee_id']==x]['fullname'].values[0]}"
            )
            
            emp_rows = df[df["employee_id"] == selected_emp]
            
            st.dataframe(
                emp_rows[["tgv_name", "tv_name", "baseline_score", "user_score", "tv_match_rate"]],
                use_container_width=True,
                hide_index=True
            )

    # -------------------------------------------------------------------------
    # Content for Tab 3 (Visualizations)
    # -------------------------------------------------------------------------
    with tab3:
        if 'ranked_employees' in locals() and not ranked_employees.empty: 
            st.subheader("Match Rate Distribution")
            fig_hist = px.histogram(
                ranked_employees,
                x="final_match_rate",
                nbins=15,
                title="Distribution of Final Match Rates",
                labels={"final_match_rate": "Match Rate (%)"}
            )
            st.plotly_chart(fig_hist, use_container_width=True)
            
            st.divider()
            
            st.subheader("Average TGV Match Rates")
            tgv_summary = (
                df.groupby("tgv_name")["tgv_match_rate"]
                .mean()
                .reset_index()
                .sort_values("tgv_match_rate", ascending=False)
            )
            fig_tgv = px.bar(
                tgv_summary,
                x="tgv_name",
                y="tgv_match_rate",
                title="Average Match Rate by TGV Category",
                labels={"tgv_name": "TGV Category", "tgv_match_rate": "Match Rate (%)"}
            )
            st.plotly_chart(fig_tgv, use_container_width=True)
            
            st.divider()
            
            st.subheader("Top Candidate Profile (Radar Chart)")
            top_emp = ranked_employees.iloc[0]["employee_id"]
            emp_tgv = (
                df[df["employee_id"] == top_emp]
                .groupby("tgv_name")["tv_match_rate"]
                .mean()
                .reset_index()
            )
            
            categories = emp_tgv["tgv_name"].tolist()
            values = emp_tgv["tv_match_rate"].tolist()
            
            fig_radar = px.line_polar(
                r=values + [values[0]],
                theta=categories + [categories[0]],
                line_close=True,
                title=f"Competency Profile: {ranked_employees.iloc[0]['fullname']}"
            )
            fig_radar.update_traces(fill='toself')
            st.plotly_chart(fig_radar, use_container_width=True)
        else:
            st.warning("Analysis results needed for visualizations.")

    # -------------------------------------------------------------------------
    # Content for Tab 4 (Insights)
    # -------------------------------------------------------------------------
    with tab4:
        # Same check as in Tab 3
        if 'ranked_employees' in locals() and not ranked_employees.empty:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "Top Candidate",
                    ranked_employees.iloc[0]['fullname'],
                    f"{ranked_employees.iloc[0]['final_match_rate']:.1f}%"
                )
            
            with col2:
                st.metric(
                    "Median Match Rate",
                    f"{ranked_employees['final_match_rate'].median():.1f}%"
                )
            
            with col3:
                st.metric(
                    "Total Candidates Analyzed",
                    len(ranked_employees)
                )
            
            st.divider()
            
            st.subheader("Key Findings")
            
            top_3 = ranked_employees.head(3)
            st.markdown("**Top 3 Candidates:**")
            for idx, row in top_3.iterrows():
                st.markdown(f"{row['Rank']}. **{row['fullname']}** ({row['position']}) — {row['final_match_rate']:.1f}% match")
            
            st.markdown("---")
            
            # Use tgv_summary from Tab 3 logic
            strongest_tgv = tgv_summary.iloc[0]
            st.markdown(f"**Strongest TGV Category:** {strongest_tgv['tgv_name']} ({strongest_tgv['tgv_match_rate']:.1f}%)")
            
            weakest_tgv = tgv_summary.iloc[-1]
            st.markdown(f"**Weakest TGV Category:** {weakest_tgv['tgv_name']} ({weakest_tgv['tgv_match_rate']:.1f}%)")
        else:
            st.warning("Analysis results needed for insights.")

# =============================================================================
# Execution Block: ELSE (Input Missing)
# =============================================================================
else:
    st.info("👈 Please enter a **Role Name** and select at least one **Benchmark Employee ID** from the sidebar to start the Talent Match analysis.")