# 04 — Đặc tả use case (Chương 2, mục 2.3)

Nguồn ID: `00-id-registry.md`. Đã viết đủ 14 use case: 8 đặc tả đầy đủ (UC-01 đến UC-06, UC-08, UC-09) và 6 đặc tả ngắn (UC-07, UC-10 đến UC-14).

## Quy ước chung cho mọi use case

- Luồng thay thế và ngoại lệ đánh số theo bước của luồng chính (2a, 3b…).
- **Ngoại lệ chung, không nhắc lại ở từng use case** (FR-03, NFR-02, NFR-04):
  - Chưa đăng nhập mà vào trang cần đăng nhập thì hệ thống chuyển tới trang đăng nhập (UC-01) và nhớ địa chỉ đích.
  - Đã đăng nhập nhưng vai trò không đủ quyền thì hệ thống hiện trang "Không có quyền", không đổi dữ liệu nào.
- Mọi thao tác thêm, sửa, xóa dữ liệu quan trọng đều ghi `AuditLog` tự động qua UC-14, che `PasswordHash` (FR-06). Nếu lưu dữ liệu thất bại thì không có dòng audit.
- Biểu mẫu POST có mã chống giả mạo yêu cầu (antiforgery).

---

### UC-01 — Đăng nhập

| Mục | Nội dung |
|---|---|
| ID / Tên | UC-01 / Đăng nhập |
| Mô tả ngắn | Nhân viên xác thực bằng tài khoản Staff để vào các chức năng phù hợp vai trò, và đăng xuất khi xong |
| Actor chính / phụ | ACT-03 Agent (ACT-02, ACT-01 kế thừa) / Không có |
| Độ ưu tiên | Must (riêng khóa tạm FR-05 là Should) |
| Yêu cầu liên quan | FR-01, FR-02, FR-03, FR-04, FR-05; NFR-01, NFR-03, NFR-04 |
| Tác nhân kích hoạt (trigger) | Nhân viên mở trang đăng nhập, hoặc bị chuyển tới đó khi vào trang cần đăng nhập |
| Tiền điều kiện | Tài khoản Staff đã được tạo; nhân viên chưa đăng nhập |
| Hậu điều kiện (thành công) | Có phiên đăng nhập (cookie, hết hạn sau 8 giờ không hoạt động); `LoginAttempts` có dòng thành công; `AuditLog` có dòng `Login`; nhân viên ở trang đích hoặc trang chủ |
| Hậu điều kiện (thất bại) | Không có phiên; `LoginAttempts` có dòng thất bại kèm lý do; không có dòng `AuditLog` (vì `StaffID` bắt buộc) |
| Quy tắc nghiệp vụ | BR-10 (câu báo lỗi chung, tạm khóa sau N lần sai trong M phút) |

Luồng chính
1. Nhân viên nhập tên đăng nhập và mật khẩu rồi chọn "Đăng nhập".
2. Hệ thống kiểm tra hai trường không rỗng.
3. Hệ thống kiểm tra tên đăng nhập chưa bị tạm khóa (số lần thất bại gần đây chưa tới N).
4. Hệ thống tìm Staff theo tên, kiểm tra tài khoản đang hoạt động, rồi đối chiếu mật khẩu với chuỗi băm đã lưu.
5. Hệ thống tạo phiên đăng nhập, ghi một dòng thành công vào `LoginAttempts` và một dòng `Login` vào `AuditLog`.
6. Hệ thống chuyển nhân viên tới địa chỉ đích đã nhớ, hoặc trang chủ nếu không có.

Luồng thay thế
- 2a. Nếu một trong hai trường rỗng: hệ thống báo trường còn thiếu, quay lại bước 1 (chưa ghi `LoginAttempts`).
- 6a. Nếu địa chỉ đích không thuộc hệ thống (địa chỉ ngoài): hệ thống bỏ qua và chuyển tới trang chủ.
- Luồng phụ — Đăng xuất (FR-02): (1) nhân viên đã đăng nhập chọn "Đăng xuất" (gửi bằng POST); (2) hệ thống ghi dòng `Logout` vào `AuditLog`; (3) hệ thống xóa phiên; (4) hệ thống chuyển tới trang đăng nhập.

Luồng ngoại lệ
- 3a. Nếu tên đăng nhập đang bị tạm khóa: hệ thống từ chối, báo đúng câu chung "Tên đăng nhập hoặc mật khẩu không đúng", ghi `LoginAttempts` với lý do `Locked`; use case kết thúc thất bại. Sau M phút hết khóa thì thử lại được.
- 4a. Nếu tên không tồn tại, mật khẩu sai hoặc tài khoản không hoạt động: hệ thống báo đúng câu chung (không nói rõ cái nào sai), ghi `LoginAttempts` với lý do tương ứng (`UnknownUser`, `WrongPassword`, `Inactive`), quay lại bước 1.
- 4b. Nếu không kết nối được SQL Server: hệ thống báo lỗi hệ thống tạm thời, không tạo phiên; use case kết thúc thất bại.

Yêu cầu đặc biệt: NFR-01 (mật khẩu băm, không lưu thuần); NFR-03 (`LoginAttempts` không chứa mật khẩu); NFR-04 (cookie HttpOnly, Secure; chống giả mạo yêu cầu). Tham số N và M đặt ở `appsettings.json`, mặc định N = 5, M = 15 (ĐỀ XUẤT, D-25).

---

### UC-02 — Quản lý khách hàng

| Mục | Nội dung |
|---|---|
| ID / Tên | UC-02 / Quản lý khách hàng |
| Mô tả ngắn | Nhân viên tra cứu và xem hồ sơ khách; Manager và Admin thêm, sửa và ngừng theo dõi khách |
| Actor chính / phụ | ACT-03 Agent (xem), ACT-02 Manager, ACT-01 Admin / Không có |
| Độ ưu tiên | Must |
| Yêu cầu liên quan | FR-09, FR-10, FR-11, FR-12, FR-13; NFR-02, NFR-06, NFR-13, NFR-14 |
| Tác nhân kích hoạt (trigger) | Nhân viên chọn mục "Khách hàng" |
| Tiền điều kiện | Nhân viên đã đăng nhập (UC-01) |
| Hậu điều kiện (thành công) | Xem: không đổi dữ liệu. Thêm, sửa, ngừng theo dõi: dữ liệu đã lưu và có dòng `AuditLog` (UC-14) |
| Hậu điều kiện (thất bại) | Không đổi dữ liệu; hiện thông báo lỗi |
| Quy tắc nghiệp vụ | BR-04 (mỗi khách đúng một hợp đồng đang hiệu lực), BR-05 (không sửa dữ liệu benchmark), BR-12 (`CustomerStatus` khác `ChurnLabel`), BR-14 (khách mới chưa dự báo từ CSDL được) |

Luồng chính (tra cứu và xem chi tiết)
1. Nhân viên mở danh sách khách hàng.
2. Hệ thống hiển thị trang đầu của danh sách, chia trang; mỗi dòng có CustomerID, hợp đồng đang hiệu lực, nhóm tenure, mức rủi ro gần nhất và trạng thái CRM.
3. Nhân viên nhập CustomerID và/hoặc chọn bộ lọc (hợp đồng, nhóm tenure, mức rủi ro) rồi bấm "Lọc".
4. Hệ thống hiển thị các khách khớp điều kiện, vẫn chia trang.
5. Nhân viên chọn một khách.
6. Hệ thống hiển thị trang chi tiết: hồ sơ, hợp đồng và dịch vụ đang hiệu lực, lịch sử tương tác, ticket, dự báo gần nhất, và các nút thao tác theo vai trò.

Luồng thay thế
- 4a. Nếu không khách nào khớp: hệ thống báo "Không tìm thấy khách", quay lại bước 3.
- 6a. Nếu khách chưa có dự báo: hệ thống hiện "Chưa có dự báo" thay cho điểm rủi ro.
- 6b. Nếu khách đã ngừng theo dõi: hệ thống vẫn hiển thị đầy đủ và gắn nhãn "Ngừng theo dõi".
- 6c. Tương tác, ticket hiển thị với nhãn "dữ liệu mô phỏng" nếu `IsSimulated = 1` (FR-20).
- 6d. Từ trang chi tiết, nhân viên có thể đi tiếp tới UC-03 (ghi tương tác), UC-04 (mở ticket), UC-05 (dự báo); Manager và Admin đi tiếp tới UC-08 (đổi hợp đồng). Từ trang danh sách, Manager và Admin đi tới UC-07 (nhập CSV).

Luồng thao tác của Manager và Admin (rẽ từ bước 2 hoặc bước 6)

A. Thêm khách (FR-11)
1. Quản lý chọn "Thêm khách" ở trang danh sách.
2. Hệ thống hiển thị biểu mẫu gồm hồ sơ (CustomerID, giới tính, người cao tuổi, có bạn đời, có người phụ thuộc) và hợp đồng ban đầu (dịch vụ, hợp đồng, thanh toán, mức phí hằng tháng).
3. Quản lý nhập và chọn "Lưu".
4. Hệ thống kiểm tra CustomerID chưa tồn tại, các giá trị nằm trong danh sách cho phép và nhất quán với nhau (BR-15).
5. Hệ thống lưu một dòng `Customers` (trạng thái mặc định `Active`) và một dòng `CustomerContracts` đang hiệu lực (`EffectiveFrom` là ngày nhập) trong cùng một giao dịch, ghi audit, báo thành công và mở trang chi tiết.
- 4a. Nếu CustomerID đã tồn tại: báo trùng, quay lại bước 2.
- 4b. Nếu thiếu trường bắt buộc hoặc giá trị ngoài danh sách: báo từng trường lỗi, quay lại bước 2.
- 5a. Nếu lưu lỗi (mất kết nối SQL Server): báo lỗi, không lưu dòng nào; use case kết thúc thất bại.

B. Sửa hồ sơ (FR-12)
1. Quản lý chọn "Sửa" ở trang chi tiết.
2. Hệ thống hiển thị biểu mẫu hồ sơ điền sẵn, CustomerID không sửa được.
3. Quản lý sửa và chọn "Lưu".
4. Hệ thống kiểm tra giá trị, lưu thay đổi, ghi audit giá trị trước và sau, báo thành công.
- 4a. Nếu giá trị ngoài danh sách: báo lỗi, quay lại bước 2.
- 4b. Nếu lưu lỗi: báo lỗi, giữ nguyên dữ liệu cũ; kết thúc thất bại.

C. Ngừng theo dõi (FR-13)
1. Quản lý chọn "Ngừng theo dõi" ở trang chi tiết.
2. Hệ thống yêu cầu xác nhận.
3. Quản lý xác nhận.
4. Hệ thống đổi `CustomerStatus` sang trạng thái ngừng theo dõi (xóa mềm; khách và lịch sử vẫn còn), ghi audit, báo thành công.
- 3a. Nếu quản lý hủy xác nhận: không đổi gì, quay lại trang chi tiết.

Luồng ngoại lệ (cho phần tra cứu)
- 2b. Nếu không kết nối được SQL Server: hệ thống báo lỗi, không hiện danh sách rỗng giả; use case kết thúc thất bại.

Yêu cầu đặc biệt: NFR-06 (danh sách 7.043 khách, tải ≤ 3 giây, giả định); NFR-13 (không dùng `CustomerStatus` thay cho `ChurnLabel`, không sửa `CustomerSnapshots`); NFR-14 (nhãn tiếng Việt, trạng thái rỗng và lỗi). Quan hệ: include UC-14; extend bởi UC-07, UC-08.

---

### UC-03 — Quản lý tương tác

| Mục | Nội dung |
|---|---|
| ID / Tên | UC-03 / Quản lý tương tác |
| Mô tả ngắn | Nhân viên ghi nhận và xem lại lịch sử tương tác với khách; Manager sửa, Admin xóa |
| Actor chính / phụ | ACT-03 Agent (thêm, xem, lọc), ACT-02 Manager (+ sửa), ACT-01 Admin (+ xóa) / Không có |
| Độ ưu tiên | Must |
| Yêu cầu liên quan | FR-16, FR-17, FR-18, FR-19, FR-20; NFR-02, NFR-13 |
| Tác nhân kích hoạt (trigger) | Nhân viên chọn mục tương tác ở trang chi tiết khách |
| Tiền điều kiện | Nhân viên đã đăng nhập; khách đã tồn tại |
| Hậu điều kiện (thành công) | Dòng `Interactions` được thêm, sửa hoặc xóa; có dòng `AuditLog` (UC-14) |
| Hậu điều kiện (thất bại) | Không đổi dữ liệu; hiện thông báo lỗi |
| Quy tắc nghiệp vụ | BR-09 (dữ liệu mô phỏng có `IsSimulated = 1`, dòng nhập tay là 0) |

Luồng chính (ghi nhận)
1. Nhân viên mở lịch sử tương tác của một khách.
2. Hệ thống hiển thị các tương tác của khách, mới nhất trước; dòng mô phỏng gắn nhãn "dữ liệu mô phỏng".
3. Nhân viên chọn "Ghi nhận tương tác".
4. Hệ thống hiển thị biểu mẫu: kênh (Phone, Email, Chat, Web), loại (Inquiry, Support, Complaint, Renewal), mô tả, kết quả (Resolved, Follow-up, Escalated); thời điểm mặc định là giờ hiện tại; người phụ trách là nhân viên đang đăng nhập.
5. Nhân viên nhập và chọn "Lưu".
6. Hệ thống kiểm tra giá trị, lưu dòng mới với `IsSimulated = 0`, ghi audit, hiển thị lại danh sách kèm thông báo thành công.

Luồng thay thế
- 2a. Lọc (FR-17): nhân viên chọn loại, kênh, khoảng thời gian rồi bấm "Lọc"; hệ thống chỉ hiện dòng thỏa mọi điều kiện, vẫn mới nhất trước. Nếu không dòng nào khớp thì hiện "Không có tương tác".
- 3a. Sửa (Manager, Admin; FR-18): quản lý chọn "Sửa" một dòng; hệ thống hiển thị biểu mẫu điền sẵn; quản lý sửa rồi lưu; hệ thống kiểm tra, lưu, ghi audit giá trị trước và sau. Cờ `IsSimulated` giữ nguyên, không sửa được.
- 3b. Xóa (Admin; FR-19): quản lý chọn "Xóa" một dòng; hệ thống yêu cầu xác nhận; sau khi xác nhận, hệ thống xóa dòng và ghi audit giá trị cũ.

Luồng ngoại lệ
- 6a. Nếu thiếu kênh hoặc loại, giá trị ngoài danh sách, hoặc mô tả dài quá 1.000 ký tự: hệ thống báo từng trường lỗi, quay lại bước 4.
- 6b. Nếu lưu lỗi (mất kết nối SQL Server): hệ thống báo lỗi, không lưu; use case kết thúc thất bại.
- 3c. Nếu Agent gõ trực tiếp địa chỉ sửa hoặc xóa: hệ thống hiện trang "Không có quyền" (quy ước chung), không đổi dữ liệu.

Yêu cầu đặc biệt: NFR-02 (quyền chặn ở máy chủ, kiểm bằng địa chỉ trực tiếp); NFR-13 (nhãn "dữ liệu mô phỏng" đúng chỗ). Quan hệ: include UC-14.

### UC-04 — Xử lý ticket

| Mục | Nội dung |
|---|---|
| ID / Tên | UC-04 / Xử lý ticket |
| Mô tả ngắn | Nhân viên mở ticket, phân công, cập nhật và đóng ticket theo luồng Open → InProgress → Closed |
| Actor chính / phụ | ACT-03 Agent (mở, xem, phân công, cập nhật, đóng), ACT-02 Manager (như Agent, thêm mở lại qua UC-09), ACT-01 Admin (+ xóa) / Không có |
| Độ ưu tiên | Must (riêng xóa ticket FR-26 là Should) |
| Yêu cầu liên quan | FR-20, FR-21, FR-22, FR-23, FR-24, FR-26, FR-27; NFR-02, NFR-13 |
| Tác nhân kích hoạt (trigger) | Nhân viên chọn mục "Ticket", hoặc chọn "Mở ticket" ở trang chi tiết khách |
| Tiền điều kiện | Nhân viên đã đăng nhập; khách đã tồn tại (khi mở ticket mới) |
| Hậu điều kiện (thành công) | Dòng `Tickets` được tạo hoặc cập nhật, đúng ràng buộc BR-02; có dòng `AuditLog` (UC-14) |
| Hậu điều kiện (thất bại) | Ticket giữ nguyên trạng thái cũ; hiện thông báo lỗi |
| Quy tắc nghiệp vụ | BR-01 (Open → InProgress → Closed), BR-02 (ràng buộc `ClosedAt`, `Resolution`, điểm hài lòng), BR-09 (ticket mô phỏng có nhãn) |

Luồng chính (từ mở tới đóng ticket)
1. Nhân viên chọn "Mở ticket".
2. Hệ thống hiển thị biểu mẫu: khách (điền sẵn nếu đi từ trang chi tiết khách), loại (Billing, Technical, Service), mức ưu tiên (Low, Medium, High).
3. Nhân viên chọn và bấm "Lưu".
4. Hệ thống kiểm tra giá trị, tạo ticket với `Status = Open`, `CreatedAt` là giờ hiện tại, `ClosedAt` rỗng, ghi audit và báo thành công.
5. Nhân viên mở danh sách ticket, lọc theo trạng thái, mức ưu tiên, nhân viên phụ trách, khách, rồi chọn một ticket Open.
6. Hệ thống hiển thị chi tiết ticket và chỉ các thao tác hợp lệ với trạng thái hiện tại và vai trò của nhân viên.
7. Nhân viên chọn nhân viên phụ trách (có thể là chính mình), có thể đổi mức ưu tiên, rồi chuyển ticket sang InProgress.
8. Hệ thống lưu `Status = InProgress` và `AssignedStaffID`, ghi audit.
9. Khi xử lý xong, nhân viên chọn "Đóng ticket", nhập kết quả giải quyết (bắt buộc) và có thể nhập điểm hài lòng từ 1 đến 5.
10. Hệ thống kiểm tra, lưu `Status = Closed`, `ClosedAt` là giờ hiện tại, `Resolution`, điểm hài lòng nếu có, ghi audit, và hiển thị thời gian xử lý bằng `ClosedAt` trừ `CreatedAt`.

Luồng thay thế
- 5a. Nếu lọc không có ticket nào: hệ thống hiện "Không có ticket", quay lại bước 5.
- 7a. Nếu ticket đã InProgress: bỏ qua bước 7, nhân viên đi thẳng tới bước 9.
- 7b. Chỉ phân công hoặc đổi mức ưu tiên mà chưa chuyển trạng thái (ticket Open hoặc InProgress): hệ thống lưu thay đổi và ghi audit giá trị trước và sau; trạng thái giữ nguyên.
- 9a. Xóa ticket (Admin, FR-26): Admin chọn "Xóa", hệ thống yêu cầu xác nhận, sau đó xóa dòng và ghi audit giá trị cũ.
- 9b. Mở lại ticket: với ticket Closed, Manager hoặc Admin chọn "Mở lại ticket", chuyển sang UC-09.
- 6a. Ticket mô phỏng (`IsSimulated = 1`) hiển thị nhãn "dữ liệu mô phỏng" ở danh sách và chi tiết (FR-20).

Luồng ngoại lệ
- 4a. Nếu thiếu khách, loại hoặc ưu tiên, hoặc giá trị ngoài danh sách, hoặc khách không tồn tại: hệ thống báo từng trường lỗi, quay lại bước 2.
- 8a. Nếu nhân viên chuyển sai thứ tự (ví dụ Open thẳng sang Closed): hệ thống từ chối, nêu rõ thứ tự hợp lệ, ticket giữ nguyên.
- 10a. Nếu thiếu kết quả giải quyết: hệ thống từ chối đóng, ticket giữ nguyên, quay lại bước 9.
- 10b. Nếu điểm hài lòng ngoài 1 đến 5: hệ thống từ chối, quay lại bước 9.
- 10c. Nếu `ClosedAt` sớm hơn `CreatedAt` (ví dụ giờ máy lệch): CSDL từ chối theo ràng buộc, hệ thống báo lỗi và ticket giữ nguyên. `ClosedAt` do hệ thống gán, nhân viên không nhập tay.
- 4b, 8b, 10d. Nếu lưu lỗi (mất kết nối SQL Server): hệ thống báo lỗi, không lưu; use case kết thúc thất bại.
- Nếu Agent gõ trực tiếp địa chỉ mở lại hoặc xóa ticket: trang "Không có quyền" (quy ước chung).

Yêu cầu đặc biệt: NFR-02 (quyền chặn ở máy chủ); NFR-13 (nhãn mô phỏng đúng chỗ). Quan hệ: include UC-14; extend bởi UC-09.

---

### UC-05 — Dự báo churn

| Mục | Nội dung |
|---|---|
| ID / Tên | UC-05 / Dự báo churn |
| Mô tả ngắn | Nhân viên lấy xác suất churn cho một khách có sẵn hoặc cho đặc trưng nhập tay; hệ thống gán mức rủi ro theo ngưỡng cấu hình và lưu kết quả |
| Actor chính / phụ | ACT-03 Agent (ACT-02, ACT-01 kế thừa) / ACT-04 Dịch vụ dự báo FastAPI |
| Độ ưu tiên | Must |
| Yêu cầu liên quan | FR-28, FR-29, FR-30, FR-31; NFR-05, NFR-08, NFR-13 |
| Tác nhân kích hoạt (trigger) | Nhân viên chọn "Dự báo churn" ở trang chi tiết khách hoặc ở menu |
| Tiền điều kiện | Nhân viên đã đăng nhập; FastAPI đang chạy; `ModelVersions` có phiên bản mô hình; `RiskConfig` có hai ngưỡng hợp lệ (0 ≤ Medium < High ≤ 1) |
| Hậu điều kiện (thành công) | Có một dòng `ChurnPredictions` (`ModelVersionID`, `Probability`, `RiskLevel`, `PredictionTime`, `InputJson`; `CustomerID` rỗng nếu nhập tay); có dòng `AuditLog`; màn hình hiện kết quả |
| Hậu điều kiện (thất bại) | Không có dòng `ChurnPredictions` mới; màn hình báo lỗi, **không** báo thành công |
| Quy tắc nghiệp vụ | BR-06 (mức rủi ro theo ngưỡng), BR-07 (nhập tay phải có `InputJson`), BR-08 (đúng 19 đặc trưng), BR-13 (chỉ hỗ trợ quyết định), BR-14 (khách chưa có snapshot) |

Luồng chính (khách có sẵn)
1. Nhân viên chọn "Dự báo churn" cho một khách (từ trang chi tiết, hoặc nhập CustomerID).
2. Hệ thống lấy 19 đặc trưng từ CSDL (hồ sơ khách, hợp đồng và dịch vụ đang hiệu lực, tenure và `TotalCharges` từ snapshot), đổi `Partner` và `Dependents` từ bit về Yes hoặc No.
3. Hệ thống kiểm tra đủ 19 đặc trưng và đúng danh sách giá trị.
4. Hệ thống gửi 19 đặc trưng tới `/predict` của FastAPI (ACT-04), chờ tối đa T giây.
5. FastAPI trả xác suất churn, phiên bản mô hình và thời gian suy luận.
6. Hệ thống đọc ngưỡng từ `RiskConfig`, gán mức Low, Medium hoặc High, và tra `ModelVersionID` theo phiên bản mô hình.
7. Hệ thống lưu một dòng `ChurnPredictions` kèm `InputJson`, ghi audit.
8. Hệ thống hiển thị xác suất, mức rủi ro, phiên bản mô hình, thời điểm dự báo và ghi chú "chỉ hỗ trợ quyết định, không phải nguyên nhân khiến khách rời bỏ".

Luồng thay thế
- 1a. Nhập thủ công (FR-29): nhân viên chọn "Nhập thủ công"; hệ thống hiển thị biểu mẫu 19 đặc trưng (trường phân loại là danh sách chọn); nhân viên nhập; hệ thống kiểm tra giá trị trước khi gọi API (bỏ bước 2); tiếp tục từ bước 4. Ở bước 7, dòng lưu có `CustomerID` rỗng và `InputJson` là JSON hợp lệ (BR-07).
- 3a. Nhập thủ công có giá trị không hợp lệ (thiếu trường, ngoài danh sách, số âm, `SeniorCitizen` ngoài 0 hoặc 1, mâu thuẫn giữa các cột theo BR-15): hệ thống báo từng trường lỗi, **không gọi API**, quay lại biểu mẫu. `TotalCharges` được phép để trống.
- 8a. Nếu khách chưa có dự báo trước đó: hiển thị như bước 8; nếu đã có thì dự báo mới được lưu thêm, dự báo cũ giữ nguyên làm lịch sử.

Luồng ngoại lệ
- 2a. Nếu khách chưa có snapshot (khách thêm mới qua Web hoặc CSV, BR-14): hệ thống báo "Khách chưa đủ dữ liệu để dự báo từ CSDL (thiếu tenure, TotalCharges), hãy dùng Nhập thủ công"; use case kết thúc thất bại.
- 2b. Nếu khách không có đúng một dòng hợp đồng đang hiệu lực: hệ thống báo lỗi dữ liệu, không gọi API; kết thúc thất bại.
- 4a. Nếu FastAPI chưa chạy, không kết nối được hoặc quá thời gian T: hệ thống báo "Dịch vụ dự báo chưa sẵn sàng, thử lại sau", không ghi `ChurnPredictions`; kết thúc thất bại.
- 5a. Nếu FastAPI trả lỗi dữ liệu không hợp lệ (422) hoặc lỗi nội bộ (500): hệ thống báo lỗi, không lưu; ghi log kỹ thuật; kết thúc thất bại.
- 6a. Nếu `RiskConfig` thiếu khóa ngưỡng hoặc Medium không nhỏ hơn High: hệ thống báo lỗi cấu hình, không gán mức, không lưu; kết thúc thất bại.
- 7a. Nếu lưu `ChurnPredictions` lỗi (mất kết nối SQL Server): hệ thống báo "Kết quả chưa được lưu", **không hiển thị điểm như đã thành công**; kết thúc thất bại.

Yêu cầu đặc biệt: NFR-05 (gọi `/predict` p95 ≤ 500 ms, giả định, đo ở P7 qua HTTP thật); NFR-08 (không treo trang khi mất API hoặc CSDL); NFR-13 (không diễn giải điểm là nguyên nhân). Thời gian chờ T mặc định 5 giây (ĐỀ XUẤT, đặt ở `appsettings.json`). Quan hệ: include UC-14; actor phụ ACT-04.

---

### UC-06 — Xem dashboard

| Mục | Nội dung |
|---|---|
| ID / Tên | UC-06 / Xem dashboard |
| Mô tả ngắn | Quản lý xem các thống kê về khách hàng, tương tác, ticket và dự báo rủi ro, có bộ lọc |
| Actor chính / phụ | ACT-02 Manager (ACT-01 Admin kế thừa) / Không có |
| Độ ưu tiên | Must (riêng bộ lọc FR-40 là Should) |
| Yêu cầu liên quan | FR-20, FR-27, FR-34, FR-35, FR-36, FR-37, FR-38, FR-39, FR-40; NFR-07, NFR-13 |
| Tác nhân kích hoạt (trigger) | Quản lý chọn mục "Dashboard" |
| Tiền điều kiện | Nhân viên đã đăng nhập với vai trò Manager hoặc Admin |
| Hậu điều kiện (thành công) | Hiển thị số liệu; không đổi dữ liệu nào |
| Hậu điều kiện (thất bại) | Hiện thông báo lỗi; không hiển thị số liệu rỗng giả |
| Quy tắc nghiệp vụ | BR-06 (mức rủi ro theo ngưỡng), BR-09 (nhãn dữ liệu mô phỏng), BR-12 (`CustomerStatus` khác `ChurnLabel`), BR-13 (chỉ hiển thị, không gợi ý hành động) |

Luồng chính
1. Quản lý mở dashboard.
2. Hệ thống đọc số liệu từ các view SQL và hiển thị bốn nhóm:
   - Khách hàng: tổng khách, phân bố nhãn churn (dữ liệu mẫu), phân bố theo hợp đồng, churn và retention proxy theo nhóm tenure, mức phí hằng tháng (dữ liệu mẫu), phân khúc (FR-34, 35, 36).
   - Tương tác: số tương tác theo loại, kênh, tháng (FR-38).
   - Ticket: số Open, InProgress, Closed, theo ưu tiên, thời gian xử lý trung bình, mức hài lòng (FR-39).
   - Dự báo: phân bố Low, Medium, High và danh sách khách điểm cao (FR-37).
3. Mỗi biểu đồ ghi rõ nguồn ("dữ liệu mẫu IBM" hoặc "dữ liệu mô phỏng") và chú thích giới hạn khi cần.
4. Quản lý chọn bộ lọc (hợp đồng, loại internet, phương thức thanh toán, nhóm tenure) rồi bấm "Áp dụng".
5. Hệ thống tính lại các biểu đồ có hỗ trợ lọc và hiển thị.
6. Quản lý xem danh sách khách điểm rủi ro cao (sắp giảm dần theo điểm) và chọn một khách để mở chi tiết (UC-02).

Luồng thay thế
- 2a. Nếu một nhóm chưa có dữ liệu (ví dụ chưa chấm điểm khách nào): nhóm đó hiện "Chưa có dữ liệu", các nhóm khác vẫn hiển thị.
- 4a. Nếu bộ lọc không khớp khách nào: hệ thống hiện "Không có dữ liệu cho bộ lọc này", quay lại bước 4.
- 3a. Biểu đồ retention hiện chú thích "ước lượng từ ảnh chụp một thời điểm, không phải tỷ lệ giữ chân theo thời gian"; biểu đồ phí hằng tháng ghi "mức phí hằng tháng (dữ liệu mẫu)", không dùng chữ "doanh thu" (FR-35, FR-36).

Luồng ngoại lệ
- 2b. Nếu không kết nối được SQL Server hoặc view lỗi: hệ thống báo lỗi, không hiển thị số liệu rỗng hay số cũ.
- Nếu Agent gõ trực tiếp địa chỉ dashboard: trang "Không có quyền" (quy ước chung).

Yêu cầu đặc biệt: NFR-07 (tải ≤ 5 giây, giả định); NFR-13 (đúng nhãn nguồn, không gợi ý hành động, tách `CustomerStatus` khỏi `ChurnLabel`). **Giả định (ĐỀ XUẤT):** bộ lọc ở bước 4 áp cho nhóm Khách hàng và Dự báo; nhóm Tương tác và Ticket không lọc ở Mức 1.

---

### UC-08 — Đổi hợp đồng và dịch vụ

| Mục | Nội dung |
|---|---|
| ID / Tên | UC-08 / Đổi hợp đồng và dịch vụ |
| Mô tả ngắn | Manager hoặc Admin đổi hợp đồng, dịch vụ, thanh toán hoặc mức phí của khách; hệ thống giữ lịch sử hiệu lực ở `CustomerContracts` và không sửa dữ liệu benchmark |
| Actor chính / phụ | ACT-02 Manager (ACT-01 Admin kế thừa) / Không có |
| Độ ưu tiên | Must |
| Yêu cầu liên quan | FR-14; NFR-02, NFR-13 |
| Tác nhân kích hoạt (trigger) | Quản lý chọn "Đổi hợp đồng và dịch vụ" ở trang chi tiết khách (UC-02, bước 6d) |
| Tiền điều kiện | Nhân viên đăng nhập với vai trò Manager hoặc Admin; khách có đúng một dòng hợp đồng đang hiệu lực |
| Hậu điều kiện (thành công) | Dòng cũ có `EffectiveTo` bằng ngày hiệu lực mới; dòng mới có `EffectiveFrom` bằng ngày hiệu lực mới, `EffectiveTo` rỗng, `UpdatedByStaffID` là người thao tác; khách vẫn có đúng một dòng đang hiệu lực; `CustomerSnapshots` và `TelcoRaw` không đổi; có dòng `AuditLog` (UC-14) |
| Hậu điều kiện (thất bại) | Không đổi gì: dòng cũ vẫn đang hiệu lực, không có dòng mới |
| Quy tắc nghiệp vụ | BR-04 (đóng dòng cũ rồi thêm dòng mới, `EffectiveTo` lớn hơn `EffectiveFrom`), BR-05 (không sửa benchmark), BR-15 (giá trị dịch vụ nhất quán) |

Luồng chính
1. Quản lý mở trang chi tiết khách và chọn "Đổi hợp đồng và dịch vụ".
2. Hệ thống hiển thị biểu mẫu điền sẵn từ dòng đang hiệu lực (dịch vụ điện thoại, nhiều đường, internet, 6 dịch vụ đi kèm, hợp đồng, hóa đơn điện tử, phương thức thanh toán, mức phí hằng tháng) và ngày hiệu lực mới là giờ hiện tại (chỉ hiển thị).
3. Quản lý sửa các trường cần đổi và chọn "Lưu".
4. Hệ thống kiểm tra giá trị nằm trong danh sách cho phép, nhất quán với nhau (BR-15) và có ít nhất một trường khác dòng hiện tại.
5. Trong một giao dịch, hệ thống **đóng dòng đang hiệu lực trước** (đặt `EffectiveTo` bằng ngày hiệu lực mới), **rồi thêm dòng mới** (`EffectiveTo` rỗng, `UpdatedByStaffID` là người thao tác), ghi audit cả hai thay đổi.
6. Hệ thống báo thành công và hiển thị lại trang chi tiết với hợp đồng mới; dự báo lần sau của khách dùng dòng mới, các dự báo đã lưu giữ nguyên.

Luồng thay thế
- 3a. Nếu quản lý hủy: không đổi gì, quay lại trang chi tiết.
- 4a. Nếu không trường nào khác dòng hiện tại: hệ thống báo "Không có thay đổi", không tạo dòng mới, quay lại bước 2.
- 4b. Nếu giá trị ngoài danh sách hoặc mâu thuẫn giữa các cột (ví dụ `PhoneService` = No mà `MultipleLines` = Yes): hệ thống báo từng trường lỗi, quay lại bước 2.

Luồng ngoại lệ
- 2a. Nếu khách không có đúng một dòng đang hiệu lực (dữ liệu lỗi): hệ thống báo lỗi dữ liệu, không cho đổi; use case kết thúc thất bại.
- 5a. Nếu ngày hiệu lực mới không lớn hơn `EffectiveFrom` của dòng hiện tại (ví dụ giờ máy lệch hoặc hai lần đổi liền sát nhau): hệ thống từ chối, không đổi gì, quay lại bước 2.
- 5b. Nếu có người khác vừa đổi hợp đồng của cùng khách (CSDL từ chối vì đã có dòng đang hiệu lực mới): hệ thống báo "Dữ liệu vừa được người khác thay đổi, hãy tải lại", không đổi gì.
- 5c. Nếu lưu lỗi giữa chừng (mất kết nối SQL Server): hệ thống hủy cả hai bước, báo lỗi; khách luôn giữ đúng một dòng đang hiệu lực.

Yêu cầu đặc biệt: NFR-13 (không bao giờ ghi vào `CustomerSnapshots` hay `TelcoRaw`). Quan hệ: extend UC-02; include UC-14.

---

### UC-09 — Mở lại ticket

| Mục | Nội dung |
|---|---|
| ID / Tên | UC-09 / Mở lại ticket |
| Mô tả ngắn | Manager hoặc Admin mở lại ticket đã Closed, bắt buộc nhập lý do, và hệ thống ghi lịch sử thay đổi |
| Actor chính / phụ | ACT-02 Manager (ACT-01 Admin kế thừa) / Không có |
| Độ ưu tiên | Must |
| Yêu cầu liên quan | FR-25; NFR-02 |
| Tác nhân kích hoạt (trigger) | Quản lý chọn "Mở lại ticket" ở chi tiết ticket Closed (UC-04, bước 9b) |
| Tiền điều kiện | Nhân viên đăng nhập với vai trò Manager hoặc Admin; ticket đang ở trạng thái Closed |
| Hậu điều kiện (thành công) | Ticket có `Status = InProgress`, `ClosedAt` rỗng, điểm hài lòng rỗng, `ReopenReason` là lý do vừa nhập, `Resolution` giữ nguyên; có dòng `AuditLog` ghi trạng thái và giá trị trước và sau |
| Hậu điều kiện (thất bại) | Ticket giữ nguyên ở Closed |
| Quy tắc nghiệp vụ | BR-03 (chỉ Manager và Admin, bắt buộc lý do, về InProgress, xóa `ClosedAt` và điểm hài lòng, giữ `Resolution`), BR-02 (ràng buộc nhất quán của ticket) |

Luồng chính
1. Quản lý mở chi tiết một ticket Closed và chọn "Mở lại ticket".
2. Hệ thống hiển thị ô nhập lý do (bắt buộc, tối đa 500 ký tự) và cảnh báo: thời điểm đóng và điểm hài lòng sẽ bị xóa, kết quả giải quyết cũ được giữ lại.
3. Quản lý nhập lý do và xác nhận.
4. Hệ thống kiểm tra vai trò, ticket vẫn là Closed và lý do không rỗng.
5. Hệ thống lưu trong một lần: `Status = InProgress`, `ClosedAt` rỗng, điểm hài lòng rỗng, `ReopenReason` là lý do; ghi audit gồm trạng thái trước và sau và giá trị cũ của `ClosedAt` và điểm hài lòng.
6. Hệ thống hiển thị ticket ở trạng thái InProgress; xử lý tiếp theo UC-04 (từ bước 9).

Luồng thay thế
- 3a. Nếu quản lý hủy: không đổi gì, quay lại chi tiết ticket.
- 5a. Nếu ticket từng được mở lại trước đó: `ReopenReason` được ghi đè bằng lý do mới; các lần trước vẫn xem được trong `AuditLog`. Lần đóng kế tiếp ghi đè `Resolution`.

Luồng ngoại lệ
- 4a. Nếu ticket không còn Closed (người khác vừa mở lại): hệ thống báo "Ticket đã đổi trạng thái, hãy tải lại", không đổi gì.
- 4b. Nếu lý do rỗng hoặc dài quá 500 ký tự: hệ thống từ chối, quay lại bước 2.
- 4c. Nếu Agent gõ trực tiếp địa chỉ mở lại: trang "Không có quyền" (quy ước chung), ticket giữ nguyên.
- 5b. Nếu lưu lỗi (mất kết nối SQL Server hoặc vi phạm ràng buộc, ví dụ `ClosedAt` chưa được xóa): hệ thống báo lỗi, ticket giữ nguyên ở Closed.

Quan hệ: extend UC-04; include UC-14.

---

## Đặc tả ngắn các use case phụ

#### UC-07 — Nhập khách hàng từ CSV
- **Actor:** ACT-02 Manager (ACT-01 kế thừa). **FR:** FR-15. **BR:** BR-11, BR-15. **Quan hệ:** extend UC-02, include UC-14.
- **Tiền điều kiện:** đăng nhập Manager hoặc Admin; có tệp CSV UTF-8 theo mẫu cố định 18 cột (5 cột hồ sơ, 13 cột dịch vụ, hợp đồng, thanh toán, `MonthlyCharges`).
- **Luồng chính:** (1) quản lý chọn "Nhập CSV" ở danh sách khách; (2) hệ thống hiển thị hướng dẫn và liên kết tải tệp mẫu; (3) quản lý chọn tệp và bấm "Nhập"; (4) hệ thống kiểm tra tệp có đủ 18 cột đúng tên; (5) với từng dòng, hệ thống kiểm CustomerID chưa tồn tại (trong CSDL và trong chính tệp), giá trị hợp lệ và nhất quán, rồi lưu một dòng `Customers` và một dòng `CustomerContracts` (`EffectiveFrom` là ngày nhập, không tạo snapshot); (6) hệ thống báo "X thành công, Y thất bại" kèm danh sách dòng lỗi và lý do, ghi audit từng dòng đã lưu.
- **Ngoại lệ:** (4a) tệp sai cấu trúc hoặc không đọc được: từ chối cả tệp, không ghi gì; (5a) dòng trùng CustomerID, thiếu dữ liệu hoặc ngoài danh sách: bỏ riêng dòng đó, các dòng khác vẫn nhập; (5b) lỗi SQL ở một dòng: dòng đó không lưu và được liệt kê vào dòng lỗi. Dòng trùng trong chính tệp: dòng đầu nhận, các dòng sau bị từ chối. Khách nhập qua CSV chưa dự báo được từ CSDL (BR-14).

#### UC-10 — Cấu hình ngưỡng rủi ro
- **Actor:** ACT-02 Manager (ACT-01 kế thừa). **FR:** FR-32. **BR:** BR-06. **Quan hệ:** include UC-14.
- **Luồng chính:** (1) quản lý mở trang cấu hình ngưỡng; (2) hệ thống hiển thị hai ngưỡng Medium và High hiện tại, người và thời điểm cập nhật gần nhất; (3) quản lý nhập giá trị mới và bấm "Lưu"; (4) hệ thống kiểm tra mỗi giá trị là số thuộc [0, 1] và Medium nhỏ hơn High; (5) hệ thống lưu `RiskMediumThreshold` và `RiskHighThreshold` kèm `UpdatedByStaffID`, ghi audit, báo thành công.
- **Ngoại lệ:** (4a) giá trị không phải số, ngoài [0, 1] hoặc Medium không nhỏ hơn High: từ chối, quay lại bước 3; (5a) lưu lỗi: báo lỗi, giữ ngưỡng cũ.
- **Ghi chú (ĐỀ XUẤT):** ngưỡng mới chỉ áp cho dự báo thực hiện sau đó; mức rủi ro đã lưu trong `ChurnPredictions` giữ nguyên theo ngưỡng lúc dự báo, nên dashboard phân bố rủi ro dùng mức đã lưu.

#### UC-11 — Xem nhật ký thao tác
- **Actor:** ACT-01 Admin. **FR:** FR-07. Chỉ đọc.
- **Luồng chính:** (1) Admin mở trang nhật ký; (2) hệ thống hiển thị các dòng `AuditLog` mới nhất trước, chia trang; (3) Admin lọc theo người, bảng, khoảng ngày; (4) hệ thống hiển thị các dòng khớp; (5) Admin chọn một dòng để xem giá trị cũ và mới.
- **Ngoại lệ:** (4a) không có dòng nào khớp: hiện "Không có bản ghi"; `PasswordHash` luôn hiển thị `***`. Manager và Agent gõ trực tiếp địa chỉ: trang "Không có quyền".

#### UC-12 — Quản lý người dùng và vai trò (Could)
- **Actor:** ACT-01 Admin. **FR:** FR-08. **BR:** NFR-01 (mật khẩu băm). **Quan hệ:** include UC-14.
- **Luồng chính:** (1) Admin mở danh sách nhân viên; (2) chọn "Thêm", "Sửa", "Đặt lại mật khẩu" hoặc "Khóa/Mở khóa"; (3) hệ thống hiển thị biểu mẫu (họ tên, tên đăng nhập, thư điện tử, vai trò, mật khẩu ban đầu); (4) Admin lưu; (5) hệ thống kiểm tra, băm mật khẩu bằng `PasswordHasher`, lưu, ghi audit (`PasswordHash` che thành `***`).
- **Ngoại lệ:** (5a) tên đăng nhập trùng hoặc thiếu trường: từ chối; (5b) Admin tự khóa hoặc tự hạ vai trò của chính mình: từ chối để không mất quyền quản trị (ĐỀ XUẤT).
- **Ghi chú:** use case này nằm trong danh sách có thể cắt (kế hoạch, Mục 11.1); khi cắt thì tài khoản demo tạo bằng bộ nạp ban đầu.

#### UC-13 — Xem phiên bản mô hình (Could)
- **Actor:** ACT-02 Manager (ACT-01 kế thừa). **FR:** FR-33. Chỉ đọc.
- **Luồng chính:** (1) quản lý mở trang "Mô hình"; (2) hệ thống liệt kê các dòng `ModelVersions`: tên, phiên bản, ngày huấn luyện, ngưỡng, seed, metric chính; (3) quản lý chọn một phiên bản; (4) hệ thống hiển thị cấu hình, metric đầy đủ, mã băm dữ liệu và phiên bản thư viện.
- **Ngoại lệ:** (2a) chưa có phiên bản nào: hiện "Chưa có mô hình". Trang ghi chú: metric tính trên dữ liệu mẫu IBM, không phải hiệu năng trên dữ liệu thực.

#### UC-14 — Ghi nhật ký thao tác (tự động)
- **Actor:** không có (hệ thống, được UC-02, 03, 04, 05, 08, 09, 10, 12 include). **FR:** FR-06. **BR:** NFR-03.
- **Kích hoạt:** mỗi lần lưu thay đổi dữ liệu thuộc bảy bảng: `Customers`, `CustomerContracts`, `Interactions`, `Tickets`, `RiskConfig`, `Staff`, `ChurnPredictions`.
- **Luồng chính:** (1) hệ thống gom các thay đổi trước khi lưu; (2) hệ thống lưu dữ liệu; (3) trong cùng giao dịch, hệ thống ghi mỗi thay đổi một dòng `AuditLog`: người thao tác, hành động (Insert, Update, Delete), bảng, khóa bản ghi, giá trị cũ và mới (Update chỉ ghi cột đổi), thời điểm; `PasswordHash` luôn là `***`.
- **Ngoại lệ:** (2a) lưu dữ liệu lỗi: không có dòng audit nào; (1a) không có người đăng nhập (bộ nạp ban đầu, trang đăng nhập): không ghi audit vì `StaffID` bắt buộc. Đăng nhập và đăng xuất ghi riêng ở UC-01; ETL, mô phỏng và chấm điểm theo lô ghi thẳng CSDL và có log chạy riêng, không qua use case này.
