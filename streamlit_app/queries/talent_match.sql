-- queries/talent_match.sql
-- Parameterized Talent Match SQL

WITH 
input_params AS (
    -- Parameterized input for role details
    SELECT
       CAST(:role_name AS text) AS role_name,
       CAST(:job_level AS text) AS job_level,
       CAST(:role_purpose AS text) AS role_purpose,
       gen_random_uuid() AS job_vacancy_id
),

benchmark_talent AS (
    -- selected benchmarks come from the app
    -- UNNEST on the parameterized array list passed from the application
    SELECT UNNEST(:benchmark_employee_ids) AS employee_id
),

tv_tgv_mapping AS (
    SELECT 'iq' AS tv_name, 'Cognitive Ability' AS tgv_name, 0 AS is_lower_better, 1.0 AS default_tv_weight UNION ALL
    SELECT 'gtq', 'Cognitive Ability', 0, 1.0 UNION ALL
    SELECT 'pauli', 'Cognitive Ability', 0, 1.0 UNION ALL
    SELECT 'faxtor', 'Cognitive Ability', 0, 1.0 UNION ALL
    SELECT 'tiki', 'Leadership', 0, 1.0 UNION ALL
    SELECT 'disc_word', 'Personality', 0, 1.0
),

consolidated_scores AS (
    -- consolidate psychometric variables into tall format
    SELECT employee_id::text, 'iq' AS tv_name, CAST(iq AS NUMERIC) AS user_score, NULL::text AS user_category FROM profiles_psych
    UNION ALL
    SELECT employee_id::text, 'gtq', CAST(gtq AS NUMERIC), NULL FROM profiles_psych
    UNION ALL
    SELECT employee_id::text, 'pauli', CAST(pauli AS NUMERIC), NULL FROM profiles_psych
    UNION ALL
    SELECT employee_id::text, 'faxtor', CAST(faxtor AS NUMERIC), NULL FROM profiles_psych
    UNION ALL
    SELECT employee_id::text, 'tiki', CAST(tiki AS NUMERIC), NULL FROM profiles_psych
    UNION ALL
    SELECT employee_id::text, 'disc_word', NULL, disc_word FROM profiles_psych
),

tv_baseline_aggregation AS (
    SELECT
        cs.tv_name,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cs.user_score) 
            FILTER (WHERE cs.user_score IS NOT NULL) AS baseline_score,
        (
            SELECT user_category
            FROM consolidated_scores c2
            WHERE c2.tv_name = cs.tv_name
              AND c2.employee_id IN (SELECT employee_id FROM benchmark_talent)
              AND c2.user_category IS NOT NULL
            GROUP BY user_category
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ) AS baseline_category
    FROM consolidated_scores cs
    WHERE cs.employee_id IN (SELECT employee_id FROM benchmark_talent)
    GROUP BY cs.tv_name
),

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
            WHEN cs.user_score IS NOT NULL AND bl.baseline_score IS NOT NULL AND bl.baseline_score > 0 THEN
                CASE
                    WHEN tvm.is_lower_better = 0 THEN LEAST(ROUND((cs.user_score / bl.baseline_score * 100)::NUMERIC, 2), 100)
                    WHEN tvm.is_lower_better = 1 THEN LEAST(ROUND(((2 * bl.baseline_score - cs.user_score) / bl.baseline_score * 100)::NUMERIC, 2), 100)
                    ELSE 0
                END
            WHEN cs.user_category IS NOT NULL AND bl.baseline_category IS NOT NULL THEN
                CASE WHEN cs.user_category = bl.baseline_category THEN 100.0 ELSE 0.0 END
            ELSE 0.0
        END AS tv_match_rate
    FROM consolidated_scores cs
    JOIN tv_tgv_mapping tvm ON cs.tv_name = tvm.tv_name
    LEFT JOIN tv_baseline_aggregation bl ON cs.tv_name = bl.tv_name
),

tgv_match_rates AS (
    SELECT
        tmr.employee_id,
        tmr.tgv_name,
        ROUND(AVG(tmr.tv_match_rate)::NUMERIC, 2) AS tgv_match_rate
    FROM tv_match_rates tmr
    GROUP BY tmr.employee_id, tmr.tgv_name
),

final_match_rate AS (
    SELECT
        employee_id,
        ROUND(LEAST(AVG(tgv_match_rate), 100)::NUMERIC, 2) AS final_match_rate
    FROM tgv_match_rates
    GROUP BY employee_id
)

SELECT
    ip.job_vacancy_id,
    ip.role_name,
    ip.job_level,
    ip.role_purpose,
    e.employee_id,
    COALESCE(e.fullname, '') AS fullname, -- FIX: Removed non-existent 'e.employee_name'
    dd.name AS directorate,
    dp.name AS position,
    dg.name AS grade,
    tmr.tgv_name,
    tmr.tv_name,
    ROUND(CAST(tmr.baseline_score AS NUMERIC), 3) AS baseline_score,
    ROUND(CAST(tmr.user_score AS NUMERIC), 3) AS user_score,
    ROUND(CAST(tmr.tv_match_rate AS NUMERIC), 2) AS tv_match_rate,
    ROUND(CAST(tgv.tgv_match_rate AS NUMERIC), 2) AS tgv_match_rate,
    ROUND(CAST(fmr.final_match_rate AS NUMERIC), 2) AS final_match_rate
FROM input_params ip
CROSS JOIN tv_match_rates tmr
JOIN employees e ON tmr.employee_id = e.employee_id
LEFT JOIN dim_directorates dd ON e.directorate_id = dd.directorate_id
LEFT JOIN dim_positions dp ON e.position_id = dp.position_id
LEFT JOIN dim_grades dg ON e.grade_id = dg.grade_id
JOIN tgv_match_rates tgv ON tmr.employee_id = tgv.employee_id AND tmr.tgv_name = tgv.tgv_name
JOIN final_match_rate fmr ON tmr.employee_id = fmr.employee_id
ORDER BY fmr.final_match_rate DESC, e.employee_id, tmr.tgv_name, tmr.tv_name;