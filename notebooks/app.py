import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
import uuid
from dotenv import load_dotenv
from supabase import create_client
from postgrest.exceptions import APIError

# --- 1. Load Environment Variables (Robust & Consolidated)
try:
    # Check for local .env first
    if os.path.exists("D:/Work/Projects/Notebooks/talent-match-intel/key.env"):
        load_dotenv(dotenv_path="D:/Work/Projects/Notebooks/talent-match-intel/key.env")
        SUPABASE_URL = os.getenv("SUPABASE_URL")
        SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    else:
        # Load from Streamlit secrets
        SUPABASE_URL = st.secrets["SUPABASE_URL"]
        SUPABASE_KEY = st.secrets["SUPABASE_SERVICE_KEY"]
        GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except KeyError as e:
    st.error(f"❌ Configuration Error: Missing key in environment or secrets: {e}. Please ensure all keys are set.")
    st.stop()
except Exception as e:
    st.error(f"❌ Configuration Error: Could not load environment variables or secrets. Details: {e}")
    st.stop()

# --- 2. Initialize Supabase Client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 3. Page Config and Title
st.set_page_config(page_title="Talent Benchmark Dashboard", layout="wide")
st.title("🎯 Talent Benchmark Dashboard")

# --- Step 1: Role input
role_name = st.text_input("Role Name")
job_level = st.text_input("Job Level")
role_purpose = st.text_area("Role Purpose")

# Normalize role name
normalized_role = role_name.strip().title()

# --- Step 2: Fetch employees with matching role

# FIX 1 (NameError): Initialize variables for global scope access
employee_map = {}
employee_ids = []
employee_names = []
employee_options = []

if normalized_role:
    try:
        # FIX 2 (Column Name): Changed 'name' to 'fullname' based on the ERD
        employee_result = supabase.from_("employees").select("employee_id, fullname, positions:dim_positions(name)").eq("positions.name", normalized_role).execute()
        
        # FIX 2 (Column Name): Updated dictionary comprehension to use 'fullname'
        employee_map = {row['employee_id']: row['fullname'] for row in employee_result.data if 'fullname' in row}
        
        employee_ids = list(employee_map.keys())
        employee_names = [f"{employee_map[id]} ({id[:8]})" for id in employee_ids]

    except Exception as e:
        st.error(f"Database Query Error: Failed to fetch employees for role. {e}")
        employee_map = {}
        employee_ids = []
        employee_names = []

# --- Step 3: Benchmark selection + submit
submitted = False
if employee_ids:
    # FIX 3 (IndentationError): Corrected indentation for the 'with st.form' block
    with st.form("benchmark_form"):
        selected_names = st.multiselect(
            f"👥 Select Benchmark Employees for {normalized_role} (max 3)",
            options=employee_names,
            max_selections=3
        )
        # Map selected names (which contain IDs) back to just the IDs
        selected_employees = [id for id, name in employee_map.items() if f"{name} ({str(id)[:8]})" in selected_names]
        submitted = st.form_submit_button("Generate Benchmark")
else:
    if normalized_role:
        st.warning(f"No employees found for role: {normalized_role}")


# --- 4. Generate Job Profile Function (Groq Fix applied)
def generate_job_profile(role_name, job_level, role_purpose):
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY not configured. Cannot generate job profile."

    prompt = f"Generate a detailed, actionable job profile for the role: {role_name} at the {job_level} level. The core purpose of this role is: {role_purpose}. The profile must include: Key Responsibilities, Work Inputs, Work Outputs, Qualifications, and Competencies."

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "llama-3.1-8b-instant", # Using a stable Groq model
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if "choices" not in result:
            return "Error: No job profile generated."

        return result['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Groq API Request Error: {e}")
        return "Error: Failed to connect to or get a response from the Groq API."


# --- 5. Process Submission
if submitted:
    if not role_name or not job_level or not role_purpose or not selected_employees:
        st.error("🚨 Please fill in all fields and select up to 3 benchmark employees.")
    else:
        # Normalize inputs
        role_name = role_name.strip().title()
        job_level = job_level.strip().capitalize()
        role_purpose = role_purpose.strip()

        job_id = str(uuid.uuid4())
        st.success(f"✅ Job ID created: `{job_id}`")

        # Generate AI job profile
        with st.spinner("Generating AI Job Profile..."):
            st.subheader("🧠 AI-Generated Job Profile")
            job_profile = generate_job_profile(role_name, job_level, role_purpose)
            st.markdown(job_profile)
        
        st.markdown("---")

        # Call Supabase RPC
        st.subheader("📊 Generating Benchmark Scores...")
        with st.spinner("Calling database function..."):
            try:
                # FIX 4 (RPC): Correct parameter names (p_employee_ids, etc.)
                result = supabase.rpc("get_benchmark_scores", {
                    "p_employee_ids": selected_employees,  
                    "p_job_level": job_level,             
                    "p_role_name": role_name,             
                    "p_role_purpose": role_purpose        
                }).execute()

                df_ranked = pd.DataFrame(result.data or [])

                if df_ranked.empty:
                    st.warning("⚠️ No ranked talent found. Check benchmark logic or table data.")
                else:
                    
                    # --- Ranked Talent List ---
                    st.subheader("🏆 Ranked Talent List")
                    
                    # Display the key fields
                    st.dataframe(
                        df_ranked[['employee_id', 'role', 'final_match_rate', 'tgv_name', 'tv_name', 'baseline_score', 'user_score']], 
                        use_container_width=True,
                        column_config={
                            "role": st.column_config.TextColumn("Candidate Role/Position"), 
                            "final_match_rate": st.column_config.NumberColumn("Final Match Rate", format="%.2f"),
                            "baseline_score": st.column_config.NumberColumn("Benchmark Score", format="%.3f"),
                            "user_score": st.column_config.NumberColumn("Candidate Score", format="%.3f"),
                        }
                    )
                    
                    st.markdown("---")

                    # --- Visualizations & Summary ---
                    
                    # Match Rate Distribution
                    st.subheader("📈 Match Rate Distribution")
                    fig = px.histogram(df_ranked, x='final_match_rate', nbins=20, title="Final Match Rate Distribution")
                    st.plotly_chart(fig, use_container_width=True)

                    # Top Strengths Analysis (using TGV/TV match rates)
                    st.subheader("🔥 Top Strengths & Gaps (TGV Match Rate)")
                    # Group by TGV name and find the average TGV match rate across all candidates
                    df_tgv_summary = df_ranked[['tgv_name', 'tgv_match_rate']].drop_duplicates().sort_values(by='tgv_match_rate', ascending=False)
                    
                    fig_tgv = px.bar(
                        df_tgv_summary, 
                        x='tgv_match_rate', 
                        y='tgv_name', 
                        orientation='h', 
                        title="Average Match Rate by Talent Group Variable (TGV)"
                    )
                    st.plotly_chart(fig_tgv, use_container_width=True)


                    # Summary Insights
                    st.subheader("📌 Summary Insights")
                    
                    # Use the median of the returned candidate scores as a proxy for the general candidate pool
                    median_score = df_ranked['final_match_rate'].median()
                    top_candidate = df_ranked.sort_values(by='final_match_rate', ascending=False).iloc[0]
                    
                    # Since the query returns multiple rows per employee (one for each TV), 
                    # we need the unique TGV names for the top candidate
                    top_candidate_tgvs = df_ranked[df_ranked['employee_id'] == top_candidate['employee_id']]['tgv_name'].unique()
                    top_candidate_tgvs_str = ', '.join(top_candidate_tgvs)
                    
                    st.markdown(f"""
                    ---
                    
                    ### **🎯 Benchmarking Summary**

                    * **Benchmark Baseline (Median):** **{median_score:.2f}%**
                        > *This score represents the **typical** proficiency level of the candidates against the selected high-performing benchmark.*
                    
                    ---
                    
                    #### **🏅 Best Match Found**
                    
                    * **Employee Position:** **{top_candidate['role']}**
                    * **Final Match Score:** **{top_candidate['final_match_rate']:.2f}%**
                    * **Key Areas of Fit (TGV):** {top_candidate_tgvs_str}

                    """)


            except APIError as e:
                # The PGRST202 error should be resolved if the SQL function was run correctly
                st.error(f"❌ **CRITICAL Supabase Function Error:** The function is likely still missing or the parameters are wrong.")
                st.code(f"Error Code: {e.code}\nMessage: {e.message}\nDetails: {e.details}")
                st.warning("💡 **Action Required:** Ensure the two-part SQL script was run successfully in Supabase.")
            except Exception as e:
                st.error(f"❌ An unexpected error occurred during benchmarking: {e}")