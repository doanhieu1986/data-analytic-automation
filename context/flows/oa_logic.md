# Logic Nghiệp Vụ — Luồng Mở Tài Khoản (Open Account)

> File này mô tả **logic xử lý dữ liệu** của luồng mở tài khoản bằng ngôn ngữ nghiệp vụ.
> Claude Code đọc file này để generate SQL/code mà không cần hỏi thêm về logic.
>
> **Nguồn dữ liệu:** `bronze.cpm_event_raw` (xem chi tiết schema tại `context/data-dictionary.md`)

---

## 1. Tổng quan luồng.

- Khách hàng mở tài khoản chứng khoán qua app SmartOne (VPS) trải qua **7 bước tuần tự**.
Mỗi hành động của KH trong app phát sinh một **event** được ghi vào bảng `cpm_event_raw`.
- Trong một phiên đăng nhập, khách hàng có thể thực hiện nhiều hành động khác nhau, do đó có thể có nhiều event thuộc cùng một bước và khách hàng **có thể thực hiện nhiều lần mở tài khoản khác nhau**. Ví dụ: lần 1 mở tài khoản thành công, mở tiếp tài khoản lần 2 (cho một đối tượng khác) thất bại, mở tiếp một luồng mở tài khoản lần 3 thành công.
- Mục tiêu phân tích: đo lường **bao nhiêu KH hoàn thành từng bước** và **bao nhiêu KH bỏ cuộc (drop-off)** giữa các bước và **khi tham gia các bước tỷ lệ số lần mở tài khoản có gặp lỗi phát sinh và tỷ lệ lỗi phát sinh theo từng bước**

---

## 2. Định nghĩa 7 bước

| Bước | Tên bước | Ý nghĩa nghiệp vụ | Event thuộc bước |
|------|----------|-------------------|-----------------|
| Step 1 | Nhập thông tin đăng ký | KH điền thông tin ban đầu: số điện thoại, email, chọn loại tài khoản. Đây là điểm vào của funnel. | `acc_open_click_mkt`, `oa_registration_random`, `oa_registration_vanity`, `oa_registration_mobile`, `oa_registration_email`, `oa_registration_mkt_id`, `oa_registration_next`, `oa_registration_back` |
| Step 2 | Xác thực CCCD/CMND | KH chụp ảnh giấy tờ tùy thân mặt trước/sau hoặc dùng NFC. Bước này hay phát sinh lỗi nhất do chất lượng ảnh hoặc thiết bị không hỗ trợ NFC. | `oa_validation_next`, `oa_validation_nfc_device_fail`, `oa_validation_front`, `oa_validation_back` |
| Step 3 | Xác thực khuôn mặt (FaceID) | KH thực hiện nhận diện khuôn mặt để đối chiếu với ảnh CCCD. | `acc_open_faceid`, `oa_faceid_back`, `oa_validation_faceid_next` |
| Step 4 | Chữ ký | KH ký tên điện tử (chụp ảnh hoặc upload). | `oa_signature_ready`, `oa_signature_back`, `oa_signature_take_photo`, `oa_retake_signature_photo`, `oa_upload_signature`, `oa_upload_signature_select`, `oa_upload_signature_next` |
| Step 5 | Tạo tài khoản | KH đặt Smart ID và mật khẩu đăng nhập. | `oa_create_account_back`, `oa_create_account_smartid`, `oa_create_account_password`, `oa_create_account_repeat_password`, `oa_create_account_password_instruction`, `oa_create_account_next` |
| Step 6 | Xác nhận OTP | KH nhập mã OTP gửi về số điện thoại để xác thực cuối. | `acc_open_confirm_otp`, `acc_open_confirm_otp_back` |
| Step 7 | Hoàn thành | Tài khoản được tạo thành công. KH nhìn thấy màn hình xác nhận. | `account_open_complete`, `acc_open_finish_login` |

---

## 3. Logic xác định KH đã đến bước nào

- **Quy tắc:** 
    - Một KH được tính là **đã đến Step N** nếu có **ít nhất 1 event thuộc Step N** trong `cpm_event_raw`. 
    - **Trong mỗi phiên đăng nhập cần phải phân biệt được các luồng mở tài khoản khác nhau**, khi khách hàng thực hiện Step 1 thì được tính là bắt đầu một luồng mở tài khoản mới. Nếu khách hàng thực hiện Step 1 nhiều lần trong cùng một phiên đăng nhập thì được tính là nhiều luồng mở tài khoản khác nhau.
    - Thời gian khách hàng thực hiện mỗi Step được tính theo timestamp event đầu tiên của bước đó và timestamp event cuối cùng của bước đó hoặc timestamp đầu tiên của bước tiếp theo nếu không có event cuối cùng của bước đó.

- **Định danh KH:** dùng cột `acountid`. Bỏ qua các row có `acountid IS NULL`.

- **Cách tính funnel (cumulative):**
    - Đếm số KH distinct đã đến **ít nhất** Step N (yêu cầu hoàn thành Step N mới tính Step N+1)
    - Cách implement: lấy `MAX(step)` của mỗi KH, sau đó đếm KH có `max_step >= N` cho từng N

---

## 4. Logic tính drop-off

```
Drop-off tại Step N = Số KH đến Step (N-1) - Số KH đến Step N
Drop-off rate (%) = Drop-off tại Step N / Số KH đến Step (N-1) × 100
Conversion từ Step 1 (%) = Số KH đến Step N / Số KH đến Step 1 × 100
```

- **Step 1 không có drop-off** (là điểm bắt đầu)
- Drop-off rate cao bất thường (> 30%) tại một bước → cần điều tra lỗi kỹ thuật hoặc UX

---

## 5. Logic xác định lỗi

Một event được coi là **lỗi** nếu thoả một trong hai điều kiện:

| Nguồn lỗi | Điều kiện | Ví dụ |
|-----------|-----------|-------|
| **Event key** | Tên event chứa `fail` hoặc `error` | `oa_validation_nfc_device_fail` |
| **Segmentation** | Trường `segmentation` chứa chuỗi `error_code` | `{'error_code': '-1986', 'error_description': '...'}` |

**Metrics lỗi cần đo:**
- `total_error_events`: tổng số lần lỗi xảy ra trong bước
- `users_with_error`: số KH distinct gặp lỗi trong bước
- `distinct_error_types`: số loại event lỗi khác nhau trong bước

---

## 6. Các phân tích cần generate

### 6.1 Funnel tổng hợp (1 dòng/bước)
Output gồm: `step`, `step_name`, `users_reached`, `users_prev_step`, `dropoff_count`, `dropoff_rate_pct`, `conversion_from_step1_pct`, `total_error_events`, `users_with_error`, `distinct_error_types`

→ File tham chiếu: `outputs/2026-04-08_oa-funnel/<platform>/funnel_dropoff.sql`

### 6.2 Chi tiết lỗi (1 dòng/loại lỗi/bước)
Output gồm: `step`, `error_event`, `error_source` (event_key | segmentation), `occurrence`, `affected_users`, `days_observed`

→ File tham chiếu: `outputs/2026-04-08_oa-funnel/<platform>/error_detail.sql`

---

## 7. Tham số lọc (filters)

Khi generate query, hỗ trợ các filter sau (thêm vào `WHERE` của `classified_events`):

| Filter | Cột | Ghi chú |
|--------|-----|---------|
| Khoảng thời gian | `data_date` | Ưu tiên luôn có filter này để tránh full scan |
| Ứng dụng cụ thể | `app_key` | Xem mapping app_key → tên app tại `data-dictionary.md` |
| Phiên đăng nhập | `sessionid` | Dùng khi phân tích hành vi trong 1 phiên |

---

## 8. Lưu ý khi generate code

- **Không assume** KH phải đi qua các bước theo thứ tự — chỉ dùng `MAX(step)` để xác định bước xa nhất
- `acountid` trong data có thể là dạng string (`H53165`) — không cast sang số
- `data_date` là ngày event xảy ra, không phải timestamp — filter trực tiếp không cần truncate
- Nếu cần filter theo `app_key`, tra cứu mapping trong `data-dictionary.md` để lấy đúng giá trị hash
- Output SQL lưu vào `outputs/<YYYY-MM-DD>_<task>/<platform>/` theo quy ước tại `context/sql-conventions.md`
