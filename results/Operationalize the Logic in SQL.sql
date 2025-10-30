-- PURPOSE: Calculates the psychometric match rate for ALL employees against a benchmark 
-- defined by employees who have a performance rating = 5. No filtering by role is applied.

-- Step 1: Define Top Benchmark Talent (Rating=5)
-- Selects all employees with a hardcoded performance rating of 5 to establish the high-performer baseline.
WITH 
top_benchmark_talent AS (
    SELECT 
        e.employee_id
    FROM 
        employees e
    -- CORRECTED: Join to performance_yearly to get the rating column
    JOIN
        performance_yearly py ON e.employee_id = py.employee_id
    WHERE 
        py.rating = 5
),

-- Step 2: Define Trait Mappings
-- Maps individual psychometric variables (TV) to broader Trait Group Variables (TGV).
tv_tgv_mapping AS (
    SELECT 'iq' AS tv_name, 'Cognitive Ability' AS tgv_name, 0 AS is_lower_better, 1.0 AS default_tv_weight UNION ALL
    SELECT 'gtq', 'Cognitive Ability', 0, 1.0 UNION ALL
    SELECT 'pauli', 'Cognitive Ability', 0, 1.0 UNION ALL
    SELECT 'faxtor', 'Cognitive Ability', 0, 1.0 UNION ALL
    SELECT 'tiki', 'Leadership', 0, 1.0 UNION ALL
    SELECT 'disc_word', 'Personality', 0, 1.0
),

-- Step 3: Consolidate Psychometric Scores (All Employees)
-- Converts wide psychometric data from profiles_psych into a long/tall format for all employees 
-- who have a psychometric profile.
consolidated_scores AS (
    -- Includes ALL employees with psychometric scores
    SELECT pp.employee_id::text, 'iq' AS tv_name, CAST(pp.iq AS NUMERIC) AS user_score, NULL::text AS user_category 
    FROM profiles_psych pp
    
    UNION ALL
    
    SELECT pp.employee_id::text, 'gtq', CAST(pp.gtq AS NUMERIC), NULL 
    FROM profiles_psych pp
    
    UNION ALL
    
    SELECT pp.employee_id::text, 'pauli', CAST(pp.pauli AS NUMERIC), NULL 
    FROM profiles_psych pp
    
    UNION ALL
    
    SELECT pp.employee_id::text, 'faxtor', CAST(pp.faxtor AS NUMERIC), NULL 
    FROM profiles_psych pp
    
    UNION ALL
    
    SELECT pp.employee_id::text, 'tiki', CAST(pp.tiki AS NUMERIC), NULL 
    FROM profiles_psych pp
    
    UNION ALL
    
    SELECT pp.employee_id::text, 'disc_word', NULL, pp.disc_word 
    FROM profiles_psych pp
),

-- Step 4: Calculate Baseline Scores (Using Rating=5 Benchmark)
-- Calculates the median score (or mode category) for each trait (TV) 
-- exclusively from the `top_benchmark_talent` (Step 1).
tv_baseline_aggregation AS (
    SELECT
        cs.tv_name,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cs.user_score) 
            FILTER (WHERE cs.user_score IS NOT NULL) AS baseline_score,
        (
            SELECT user_category
            FROM consolidated_scores c2
            WHERE c2.tv_name = cs.tv_name
              AND c2.employee_id IN (SELECT employee_id FROM top_benchmark_talent)
              AND c2.user_category IS NOT NULL
            GROUP BY user_category
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ) AS baseline_category
    FROM consolidated_scores cs
    WHERE cs.employee_id IN (SELECT employee_id FROM top_benchmark_talent)
    GROUP BY cs.tv_name
),

-- Step 5: Calculate Trait Match Rates (TV Match Rates)
-- Compares every employee's score against the benchmark score (Step 4) for each trait.
tv_match_rates AS (
    SELECT
        cs.employee_id,
        tvm.tgv_name,
        cs.tv_name,
        cs.user_score,
        cs.user_category,
        bl.baseline_score,
        bl.baseline_category,
        tvm.default_tv_weight,
        CASE
            -- Numeric Comparison Logic (Higher/Lower is Better)
            WHEN cs.user_score IS NOT NULL AND bl.baseline_score IS NOT NULL AND bl.baseline_score > 0 THEN
                CASE
                    WHEN tvm.is_lower_better = 0 THEN LEAST(ROUND((cs.user_score / bl.baseline_score * 100)::NUMERIC, 2), 100)
                    WHEN tvm.is_lower_better = 1 THEN LEAST(ROUND(((2 * bl.baseline_score - cs.user_score) / bl.baseline_score * 100)::NUMERIC, 2), 100)
                    ELSE 0
                END
            -- Category Comparison Logic
            WHEN cs.user_category IS NOT NULL AND bl.baseline_category IS NOT NULL THEN
                CASE WHEN cs.user_category = bl.baseline_category THEN 100.0 ELSE 0.0 END
            ELSE 0.0
        END AS tv_match_rate
    FROM consolidated_scores cs
    JOIN tv_tgv_mapping tvm ON cs.tv_name = tvm.tv_name
    LEFT JOIN tv_baseline_aggregation bl ON cs.tv_name = bl.tv_name
),

-- Step 6: Aggregate to Trait Group Match Rates (TGV Match Rates)
-- Averages the TV match rates to get a match rate for each TGV category.
tgv_match_rates AS (
    SELECT
        tmr.employee_id,
        tmr.tgv_name,
        ROUND(AVG(tmr.tv_match_rate)::NUMERIC, 2) AS tgv_match_rate
    FROM tv_match_rates tmr
    GROUP BY tmr.employee_id, tmr.tgv_name
),

-- Step 7: Calculate Final Match Rate
-- Calculates the final overall match rate by averaging the TGV match rates.
final_match_rate AS (
    SELECT
        employee_id,
        ROUND(LEAST(AVG(tgv_match_rate), 100)::NUMERIC, 2) AS final_match_rate
    FROM tgv_match_rates
    GROUP BY employee_id
)

-- Step 8: Final Selection and Column Renaming (Simplified)
-- Joins all necessary tables to present the full organization-wide benchmark analysis with simplified column names.
SELECT
    e.employee_id AS employee_id,
    dd.name AS directorate,
    dp.name AS role,
    dg.name AS grade,
    tmr.tgv_name AS tgv_name,
    tmr.tv_name AS tv_name,
    ROUND(CAST(tmr.baseline_score AS NUMERIC), 3) AS baseline_score,
    ROUND(CAST(tmr.user_score AS NUMERIC), 3) AS user_score,
    ROUND(CAST(tmr.tv_match_rate AS NUMERIC), 2) AS tv_match_rate,
    ROUND(CAST(tgv.tgv_match_rate AS NUMERIC), 2) AS tgv_match_rate,
    ROUND(CAST(fmr.final_match_rate AS NUMERIC), 2) AS final_match_rate
FROM tv_match_rates tmr
JOIN employees e ON tmr.employee_id = e.employee_id
LEFT JOIN dim_directorates dd ON e.directorate_id = dd.directorate_id
LEFT JOIN dim_positions dp ON e.position_id = dp.position_id
LEFT JOIN dim_grades dg ON e.grade_id = dg.grade_id
JOIN tgv_match_rates tgv ON tmr.employee_id = tgv.employee_id AND tmr.tgv_name = tgv.tgv_name
JOIN final_match_rate fmr ON tmr.employee_id = fmr.employee_id
ORDER BY fmr.final_match_rate DESC, e.employee_id, tmr.tgv_name, tmr.tv_name;
