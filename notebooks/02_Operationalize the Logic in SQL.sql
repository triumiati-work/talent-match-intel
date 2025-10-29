-- ===========================================================================================
-- 1. CONFIGURATION & MAPPING (Setting up the variables and data source)
-- ===========================================================================================

-- 1.1. DEFINE the Talent Benchmark (High Performers: rating = 5)
-- Purpose: This list tells the database exactly who the 'ideal' employees are.
WITH benchmark_talent AS (
    SELECT DISTINCT
        employee_id
    FROM
        performance_yearly
    WHERE
        rating = 5 -- We only select employees with the top annual rating
),

-- 1.2. TALENT VARIABLE (TV) and TALENT GROUP VARIABLE (TGV) Mapping
-- Purpose: This is our 'dictionary'. It groups individual variables (TVs) into categories (TGVs)
-- and defines the rules for each variable (like if a higher score is better).
tv_tgv_mapping AS (
    -- tv_name | tgv_name | is_lower_better (0=Higher is Better, 1=Lower is Better) | default_tv_weight
    SELECT 'iq' AS tv_name, 'Cognitive Ability' AS tgv_name, 0 AS is_lower_better, 1.0 AS default_tv_weight, 'profiles_psych' AS source_table UNION ALL
    SELECT 'tiki' AS tv_name, 'Leadership' AS tgv_name, 0 AS is_lower_better, 1.0 AS default_tv_weight, 'profiles_psych' UNION ALL
    SELECT 'disc_word' AS tv_name, 'Personality' AS tgv_name, 0 AS is_lower_better, 1.0 AS default_tv_weight, 'profiles_psych' UNION ALL
    SELECT 'strategic_thinking' AS tv_name, 'Leadership' AS tgv_name, 0 AS is_lower_better, 1.0 AS default_tv_weight, 'competencies_yearly'
    -- Note: Since 'talent_benchmarks' was missing, all weights are 1.0 (Equal Weighting).
),

-- 1.3. CONSOLIDATE & UNPIVOT ALL SCORES
-- Purpose: Takes scores scattered across different tables/columns (IQ, Tiki, Competencies)
-- and puts them into one tall, consistent list.
-- FIX: We use CAST(column AS NUMERIC) in every SELECT to ensure all 'user_score' types match,
-- preventing the "UNION types cannot be matched" error.
consolidated_scores AS (
    -- Numeric Scores
    SELECT employee_id, 'iq' AS tv_name, CAST(iq AS NUMERIC) AS user_score, NULL AS user_category FROM profiles_psych
    UNION ALL
    SELECT employee_id, 'tiki' AS tv_name, CAST(tiki AS NUMERIC) AS user_score, NULL AS user_category FROM profiles_psych
    -- Categorical Scores (Note: user_score is NULL here)
    UNION ALL
    SELECT employee_id, 'disc_word' AS tv_name, NULL AS user_score, disc_word AS user_category FROM profiles_psych
    -- Numeric Scores from competencies_yearly
    UNION ALL
    SELECT employee_id, 'strategic_thinking' AS tv_name, CAST(score AS NUMERIC) AS user_score, NULL AS user_category
    FROM competencies_yearly WHERE pillar_code = 'STRAT'
),

-- ===========================================================================================
-- 2. BASELINE AND TV MATCH RATE CALCULATION (The Core Logic)
-- ===========================================================================================

-- 2.1. BASELINE AGGREGATION (Median of Selected Talent Scores)
-- Purpose: Calculates the single ideal score (the benchmark) for *each* TV.
tv_baseline_aggregation AS (
    SELECT
        cs.tv_name,
        -- **Median for Numeric Scores:** Finds the middle score among all benchmark employees (rating=5).
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cs.user_score) AS baseline_score,
        -- **Mode for Categorical Scores:** Finds the most common category (e.g., 'Analyst' DISC type).
        (SELECT user_category FROM consolidated_scores WHERE tv_name = cs.tv_name AND employee_id IN (SELECT employee_id FROM benchmark_talent) GROUP BY user_category ORDER BY COUNT(*) DESC LIMIT 1) AS baseline_category
    FROM
        consolidated_scores cs
    JOIN
        benchmark_talent bt ON cs.employee_id = bt.employee_id -- IMPORTANT: Filters scores to only the benchmark employees
    WHERE
        cs.user_score IS NOT NULL OR cs.user_category IS NOT NULL
    GROUP BY
        cs.tv_name
),

-- 2.2. TV MATCH RATE (Employee × TV)
-- Purpose: Compares every employee's score to the ideal benchmark for every TV, giving a % match.
tv_match_rates AS (
    SELECT
        cs.employee_id,
        tvm.tgv_name,
        cs.tv_name,
        COALESCE(cs.user_score, NULL) AS user_score,
        COALESCE(bl.baseline_score, NULL) AS baseline_score,
        tvm.default_tv_weight AS effective_tv_weight,

        -- **MATCH RATE CALCULATION (TV Match Rate)**
        CASE
            -- Numeric Variable Logic
            WHEN cs.user_score IS NOT NULL AND bl.baseline_score IS NOT NULL AND bl.baseline_score > 0 THEN
                CASE
                    -- i. 'Higher is Better' (Standard Ratio)
                    WHEN tvm.is_lower_better = 0 THEN (cs.user_score / bl.baseline_score) * 100
                    -- ii. 'Lower is Better' (Inverted Ratio: (2*B - U) / B * 100)
                    WHEN tvm.is_lower_better = 1 THEN ((2 * bl.baseline_score - cs.user_score) / bl.baseline_score) * 100
                    ELSE 0
                END
            -- Categorical Variable Logic
            WHEN cs.user_category IS NOT NULL AND bl.baseline_category IS NOT NULL THEN
                CASE WHEN cs.user_category = bl.baseline_category THEN 100.0 ELSE 0.0 END -- 100% match or 0% match
            ELSE 0.0
        END AS tv_match_rate
    FROM consolidated_scores cs
    JOIN tv_tgv_mapping tvm ON cs.tv_name = tvm.tv_name
    LEFT JOIN tv_baseline_aggregation bl ON cs.tv_name = bl.tv_name
    WHERE cs.employee_id NOT IN (SELECT employee_id FROM benchmark_talent) -- Only show candidates, not the benchmarks
),

-- ===========================================================================================
-- 3. TGV MATCH RATE CALCULATION
-- ===========================================================================================

-- TGV Match Rate (Employee × TGV)
-- Purpose: Aggregates the TV Match Rates up to the category level (TGV). Since weights are equal, this is a simple average.
tgv_match_rates AS (
    SELECT
        tmr.employee_id,
        tmr.tgv_name,
        1.0 AS effective_tgv_weight, -- Equal TGV Weight
        
        -- Calculate the Weighted Average (which simplifies to a simple average here)
        SUM(tmr.tv_match_rate * tmr.effective_tv_weight) / SUM(tmr.effective_tv_weight) AS tgv_match_rate
    FROM tv_match_rates tmr
    GROUP BY tmr.employee_id, tmr.tgv_name
),

-- ===========================================================================================
-- 4. FINAL MATCH RATE CALCULATION
-- ===========================================================================================

-- Final Match Rate (Employee)
-- Purpose: Aggregates the TGV Match Rates into one overall fit score.
final_match_rate AS (
    SELECT
        tmr.employee_id,
        -- Calculate the Weighted Average (simple average across all TGVs)
        SUM(tmr.tgv_match_rate * tmr.effective_tgv_weight) / SUM(tmr.effective_tgv_weight) AS final_match_rate
    FROM tgv_match_rates tmr
    GROUP BY tmr.employee_id
)

-- ===========================================================================================
-- 5. FINAL OUTPUT ASSEMBLY (Joining everything for the final table)
-- ===========================================================================================

SELECT
    e.employee_id,
    d_dir.name AS directorate,
    d_pos.name AS role,
    d_gr.name AS grade,
    tmr.tgv_name,
    tmr.tv_name,
    
    -- FIX: CASTING TO NUMERIC BEFORE ROUNDING is mandatory in PostgreSQL
    ROUND(CAST(tmr.baseline_score AS NUMERIC), 3) AS baseline_score,
    ROUND(CAST(tmr.user_score AS NUMERIC), 3) AS user_score,
    
    ROUND(CAST(tmr.tv_match_rate AS NUMERIC), 2) AS tv_match_rate,
    ROUND(CAST(tgv.tgv_match_rate AS NUMERIC), 2) AS tgv_match_rate,
    ROUND(CAST(fmr.final_match_rate AS NUMERIC), 2) AS final_match_rate
    
FROM tv_match_rates tmr
-- Join employee details from dim tables
JOIN employees e ON tmr.employee_id = e.employee_id
JOIN dim_directorates d_dir ON e.directorate_id = d_dir.directorate_id
JOIN dim_positions d_pos ON e.position_id = d_pos.position_id
JOIN dim_grades d_gr ON e.grade_id = d_gr.grade_id
-- Join the aggregated match rates
JOIN tgv_match_rates tgv ON tmr.employee_id = tgv.employee_id AND tmr.tgv_name = tgv.tgv_name
JOIN final_match_rate fmr ON tmr.employee_id = fmr.employee_id
ORDER BY e.employee_id, tmr.tgv_name, tmr.tv_name;