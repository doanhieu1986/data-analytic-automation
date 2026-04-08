/*
 * Error Detail — Chi tiết lỗi từng bước luồng Mở Tài Khoản
 * Mục đích : Liệt kê từng loại lỗi, nguồn phát sinh, tần suất và số KH bị ảnh hưởng
 * Platform  : Trino (Trino_superset)
 * Nguồn     : bronze.cpm_event_raw   (catalog đầy đủ: hive.bronze.cpm_event_raw)
 * Output    : 1 dòng / loại lỗi / bước
 * Generated : 2026-04-08
 *
 * ⚠️  Thay DATE filter trước khi chạy. Dùng cùng khoảng thời gian với funnel_dropoff.sql.
 */

WITH

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 1–4: Tái sử dụng logic phân loại và gán flow_id (giống funnel_dropoff.sql)
-- ──────────────────────────────────────────────────────────────────────────────
classified_events AS (
    SELECT
        acountid
        , sessionid
        , key
        , CAST(timestamp AS BIGINT)     AS event_ts
        , data_date
        , segmentation
        , CASE
            WHEN key IN (
                'acc_open_click_mkt'        , 'oa_registration_random'
                , 'oa_registration_vanity'  , 'oa_registration_mobile'
                , 'oa_registration_email'   , 'oa_registration_mkt_id'
                , 'oa_registration_next'    , 'oa_registration_back'
            ) THEN 1
            WHEN key IN (
                'oa_validation_next'            , 'oa_validation_nfc_device_fail'
                , 'oa_validation_front'         , 'oa_validation_back'
            ) THEN 2
            WHEN key IN (
                'acc_open_faceid'               , 'oa_faceid_back'
                , 'oa_validation_faceid_next'
            ) THEN 3
            WHEN key IN (
                'oa_signature_ready'            , 'oa_signature_back'
                , 'oa_signature_take_photo'     , 'oa_retake_signature_photo'
                , 'oa_upload_signature'         , 'oa_upload_signature_select'
                , 'oa_upload_signature_next'
            ) THEN 4
            WHEN key IN (
                'oa_create_account_back'                , 'oa_create_account_smartid'
                , 'oa_create_account_password'          , 'oa_create_account_repeat_password'
                , 'oa_create_account_password_instruction', 'oa_create_account_next'
            ) THEN 5
            WHEN key IN (
                'acc_open_confirm_otp'          , 'acc_open_confirm_otp_back'
            ) THEN 6
            WHEN key IN (
                'account_open_complete'         , 'acc_open_finish_login'
            ) THEN 7
            ELSE NULL
          END AS step

        -- Phân loại nguồn lỗi: event_key, segmentation, hoặc cả hai
        , CASE
            WHEN (LOWER(key) LIKE '%fail%' OR LOWER(key) LIKE '%error%')
                 AND CAST(segmentation AS VARCHAR) LIKE '%error_code%'
            THEN 'event_key + segmentation'

            WHEN LOWER(key) LIKE '%fail%' OR LOWER(key) LIKE '%error%'
            THEN 'event_key'

            WHEN CAST(segmentation AS VARCHAR) LIKE '%error_code%'
            THEN 'segmentation'

            ELSE NULL   -- không phải lỗi
          END AS error_source

    FROM bronze.cpm_event_raw
    WHERE acountid IS NOT NULL
      AND data_date >= DATE '2026-01-01'   -- ⚠️ điều chỉnh khoảng thời gian
      AND data_date <= DATE '2026-04-08'
),

oa_events AS (
    SELECT *
    FROM classified_events
    WHERE step IS NOT NULL
),

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

valid_flow_events AS (
    SELECT *
    FROM flow_marked
    WHERE flow_id > 0
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 5: Chỉ giữ event lỗi (error_source IS NOT NULL)
-- ──────────────────────────────────────────────────────────────────────────────
error_events AS (
    SELECT *
    FROM valid_flow_events
    WHERE error_source IS NOT NULL
),

-- ──────────────────────────────────────────────────────────────────────────────
-- CTE 6: Step name lookup
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
-- CTE 7: Tổng hợp chi tiết lỗi theo (step, error_event, error_source)
--         Mỗi dòng = 1 loại lỗi trong 1 bước
-- ──────────────────────────────────────────────────────────────────────────────
error_summary AS (
    SELECT
        ee.step
        , ee.key                        AS error_event
        , ee.error_source
        , COUNT(*)                      AS occurrence
        , COUNT(DISTINCT ee.acountid)   AS affected_users
        , COUNT(DISTINCT ee.data_date)  AS days_observed
    FROM error_events ee
    GROUP BY ee.step, ee.key, ee.error_source
)

-- ──────────────────────────────────────────────────────────────────────────────
-- Output: Chi tiết lỗi, sắp xếp theo bước → tần suất giảm dần
-- ──────────────────────────────────────────────────────────────────────────────
SELECT
    es.step
    , sn.step_name
    , es.error_event
    , es.error_source
    , es.occurrence
    , es.affected_users
    , es.days_observed
    -- % lỗi này chiếm bao nhiêu trong tổng lỗi của bước
    , ROUND(
        CAST(es.occurrence AS DOUBLE) * 100.0
        / NULLIF(
            CAST(SUM(es.occurrence) OVER (PARTITION BY es.step) AS DOUBLE),
            0
        ),
        2
    )                                   AS pct_of_step_errors

FROM error_summary es
LEFT JOIN step_names sn ON es.step = sn.step
ORDER BY
    es.step
    , es.occurrence DESC
;
