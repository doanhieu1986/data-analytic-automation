/*
 * Funnel Analysis — Luồng Mở Tài Khoản (Open Account)
 * Mục đích : Đo lường drop-off, thời gian trung bình, tỷ lệ lỗi từng bước (7 bước)
 * Platform  : Trino (Trino_superset)
 * Nguồn     : bronze.cpm_event_raw   (catalog đầy đủ: hive.bronze.cpm_event_raw)
 * Output    : 1 dòng / bước
 * Generated : 2026-04-08
 *
 * ⚠️  Thay DATE '2026-01-01' / DATE '2026-04-08' trước khi chạy để tránh full scan.
 *     Nếu muốn lọc theo app cụ thể, thêm AND app_key = '<hash>' vào classified_events.
 */

WITH

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 1: Phân loại mỗi event vào step OA + đánh dấu lỗi
-- ──────────────────────────────────────────────────────────────────────────────
classified_events AS (
    SELECT
        acountid
        , sessionid
        , key
        -- timestamp là VARCHAR chứa Unix-ms → CAST sang BIGINT để sắp xếp
        , CAST(timestamp AS BIGINT)     AS event_ts
        , data_date
        , segmentation
        , CASE
            WHEN key IN (
                'acc_open_click_mkt'        , 'oa_registration_random'
                , 'oa_registration_vanity'  , 'oa_registration_mobile'
                , 'oa_registration_email'   , 'oa_registration_mkt_id'
                , 'oa_registration_next'    , 'oa_registration_back'
            ) THEN 1    -- Nhập thông tin đăng ký

            WHEN key IN (
                'oa_validation_next'            , 'oa_validation_nfc_device_fail'
                , 'oa_validation_front'         , 'oa_validation_back'
            ) THEN 2    -- Xác thực CCCD/CMND

            WHEN key IN (
                'acc_open_faceid'               , 'oa_faceid_back'
                , 'oa_validation_faceid_next'
            ) THEN 3    -- Xác thực khuôn mặt (FaceID)

            WHEN key IN (
                'oa_signature_ready'            , 'oa_signature_back'
                , 'oa_signature_take_photo'     , 'oa_retake_signature_photo'
                , 'oa_upload_signature'         , 'oa_upload_signature_select'
                , 'oa_upload_signature_next'
            ) THEN 4    -- Chữ ký

            WHEN key IN (
                'oa_create_account_back'                , 'oa_create_account_smartid'
                , 'oa_create_account_password'          , 'oa_create_account_repeat_password'
                , 'oa_create_account_password_instruction', 'oa_create_account_next'
            ) THEN 5    -- Tạo tài khoản

            WHEN key IN (
                'acc_open_confirm_otp'          , 'acc_open_confirm_otp_back'
            ) THEN 6    -- Xác nhận OTP

            WHEN key IN (
                'account_open_complete'         , 'acc_open_finish_login'
            ) THEN 7    -- Hoàn thành

            ELSE NULL   -- Không thuộc OA flow
          END AS step

        -- Lỗi: event key chứa fail/error HOẶC segmentation chứa error_code
        , CASE
            WHEN LOWER(key) LIKE '%fail%'
              OR LOWER(key) LIKE '%error%'
              OR CAST(segmentation AS VARCHAR) LIKE '%error_code%'
            THEN 1
            ELSE 0
          END AS is_error

    FROM bronze.cpm_event_raw
    WHERE acountid IS NOT NULL
      AND data_date >= DATE '2026-01-01'   -- ⚠️ điều chỉnh khoảng thời gian
      AND data_date <= DATE '2026-04-08'
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 2: Chỉ giữ event thuộc OA flow
-- ──────────────────────────────────────────────────────────────────────────────
oa_events AS (
    SELECT *
    FROM classified_events
    WHERE step IS NOT NULL
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 3: Đánh số luồng OA (flow_id) trong mỗi (acountid, sessionid)
-- Logic: mỗi lần Step 1 xuất hiện = bắt đầu luồng mới
--        → cumulative sum of step=1 events, sort theo event_ts
-- ──────────────────────────────────────────────────────────────────────────────
flow_marked AS (
    SELECT
        *
        , SUM(CASE WHEN step = 1 THEN 1 ELSE 0 END)
            OVER (
                PARTITION BY acountid, sessionid
                ORDER BY event_ts
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS flow_id
    FROM oa_events
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 4: Bỏ event xảy ra trước Step 1 đầu tiên (flow_id = 0)
-- ──────────────────────────────────────────────────────────────────────────────
valid_flow_events AS (
    SELECT *
    FROM flow_marked
    WHERE flow_id > 0
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 5: Max step từng luồng OA đạt được → dùng để tính funnel cumulative
-- ──────────────────────────────────────────────────────────────────────────────
flow_max_step AS (
    SELECT
        acountid
        , sessionid
        , flow_id
        , MAX(step) AS max_step
    FROM valid_flow_events
    GROUP BY acountid, sessionid, flow_id
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 6: Thời gian thực hiện từng step theo từng luồng (milliseconds)
--         duration = MAX(event_ts) - MIN(event_ts) trong bước đó
-- ──────────────────────────────────────────────────────────────────────────────
flow_step_duration AS (
    SELECT
        acountid
        , sessionid
        , flow_id
        , step
        , MAX(event_ts) - MIN(event_ts) AS duration_ms
    FROM valid_flow_events
    GROUP BY acountid, sessionid, flow_id, step
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 7: Thời gian trung bình mỗi step (giây) — tính trên tất cả flows
-- ──────────────────────────────────────────────────────────────────────────────
step_avg_duration AS (
    SELECT
        step
        , AVG(CAST(duration_ms AS DOUBLE)) / 1000.0 AS avg_duration_sec
    FROM flow_step_duration
    GROUP BY step
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 8: Funnel — số KH distinct đạt từng step (cumulative)
--         Một KH tính là đến Step N nếu max_step >= N
--         Đếm distinct acountid gộp qua tất cả flows
-- ──────────────────────────────────────────────────────────────────────────────
funnel_users AS (
    SELECT
        step_n
        , COUNT(DISTINCT acountid) AS users_reached
    FROM flow_max_step
    CROSS JOIN (
             SELECT 1 AS step_n
        UNION ALL SELECT 2
        UNION ALL SELECT 3
        UNION ALL SELECT 4
        UNION ALL SELECT 5
        UNION ALL SELECT 6
        UNION ALL SELECT 7
    ) steps
    WHERE max_step >= step_n
    GROUP BY step_n
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 9: Error metrics per step
--         Tính trên event level (không giới hạn theo funnel cumulative)
-- ──────────────────────────────────────────────────────────────────────────────
step_error_metrics AS (
    SELECT
        step
        , SUM(is_error)                                             AS total_error_events
        , COUNT(DISTINCT CASE WHEN is_error = 1 THEN acountid END) AS users_with_error
        , COUNT(DISTINCT CASE WHEN is_error = 1 THEN key END)      AS distinct_error_types
    FROM valid_flow_events
    GROUP BY step
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 10: Số KH thực sự tham gia (có event) trong từng step → để tính error rate
-- ──────────────────────────────────────────────────────────────────────────────
step_participants AS (
    SELECT
        step
        , COUNT(DISTINCT acountid) AS users_in_step
    FROM valid_flow_events
    GROUP BY step
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 11: Lookup tên bước
-- ──────────────────────────────────────────────────────────────────────────────
step_names AS (
         SELECT 1 AS step, 'Nhập thông tin đăng ký'        AS step_name
    UNION ALL SELECT 2,    'Xác thực CCCD/CMND'
    UNION ALL SELECT 3,    'Xác thực khuôn mặt (FaceID)'
    UNION ALL SELECT 4,    'Chữ ký'
    UNION ALL SELECT 5,    'Tạo tài khoản'
    UNION ALL SELECT 6,    'Xác nhận OTP'
    UNION ALL SELECT 7,    'Hoàn thành'
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 12: Join tất cả metrics, tính LAG để có users_prev_step
-- ──────────────────────────────────────────────────────────────────────────────
funnel_base AS (
    SELECT
        fu.step_n                                                       AS step
        , sn.step_name
        , fu.users_reached
        , LAG(fu.users_reached) OVER (ORDER BY fu.step_n)              AS users_prev_step
        , FIRST_VALUE(fu.users_reached) OVER (ORDER BY fu.step_n)      AS users_step1
        , COALESCE(sem.total_error_events, 0)                          AS total_error_events
        , COALESCE(sem.users_with_error, 0)                            AS users_with_error
        , COALESCE(sem.distinct_error_types, 0)                        AS distinct_error_types
        , COALESCE(sp.users_in_step, 0)                                AS users_in_step
        , COALESCE(sad.avg_duration_sec, 0)                            AS avg_duration_sec
    FROM funnel_users fu
    LEFT JOIN step_names         sn  ON fu.step_n = sn.step
    LEFT JOIN step_error_metrics sem ON fu.step_n = sem.step
    LEFT JOIN step_participants  sp  ON fu.step_n = sp.step
    LEFT JOIN step_avg_duration  sad ON fu.step_n = sad.step
)

-- ──────────────────────────────────────────────────────────────────────────────
-- Output: Funnel tổng hợp đầy đủ
-- ──────────────────────────────────────────────────────────────────────────────
SELECT
    step
    , step_name

    -- Funnel metrics
    , users_reached
    , users_prev_step
    , COALESCE(users_prev_step - users_reached, 0)                                  AS dropoff_count

    , CASE
        WHEN users_prev_step IS NULL OR users_prev_step = 0 THEN NULL
        ELSE ROUND(
            CAST(users_prev_step - users_reached AS DOUBLE) * 100.0
            / CAST(users_prev_step AS DOUBLE),
            2
        )
      END                                                                            AS dropoff_rate_pct

    , ROUND(
        CAST(users_reached AS DOUBLE) * 100.0
        / NULLIF(CAST(users_step1 AS DOUBLE), 0),
        2
    )                                                                                AS conversion_from_step1_pct

    -- Error metrics
    , total_error_events
    , users_with_error
    , distinct_error_types
    , ROUND(
        CAST(users_with_error AS DOUBLE) * 100.0
        / NULLIF(CAST(users_in_step AS DOUBLE), 0),
        2
    )                                                                                AS error_rate_pct

    -- Time metrics
    , ROUND(CAST(avg_duration_sec AS DOUBLE), 1)                                     AS avg_duration_sec
    , ROUND(CAST(avg_duration_sec AS DOUBLE) / 60.0, 2)                              AS avg_duration_min

FROM funnel_base
ORDER BY step
;
