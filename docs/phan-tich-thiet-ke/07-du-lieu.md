# 07 — Dữ liệu: ánh xạ thực thể, BFD và mô tả CSDL (Chương 2, mục 2.6)

Nguồn ID: `00-id-registry.md`. File này **không vẽ ERD hay BFD**; hai sơ đồ đó do `phan-tich-he-thong-powerdesigner` vẽ (xem `handoff-powerdesigner.md`). Ở đây chỉ có bảng ánh xạ để Chương 2 khớp với CSDL và chức năng thực tế. Số liệu dòng lấy từ kế hoạch v2.8 (Mục 11.1), chưa đo lại.

## 2.6.1 Ánh xạ thực thể với bảng

| ENT | Bảng | Khóa chính | Khóa ngoại | Ràng buộc đáng chú ý | Nguồn và số dòng |
|---|---|---|---|---|---|
| ENT-01 | Customers | CustomerID | — | `CustomerStatus` mặc định `Active` | Telco, 7.043; thêm qua Web hoặc CSV (UC-02, UC-07) |
| ENT-02 | CustomerSnapshots | SnapshotID | CustomerID | UNIQUE (CustomerID, SnapshotDate); **không sửa** (BR-05) | Telco, 7.043 |
| ENT-03 | CustomerContracts | ContractRecordID | CustomerID, UpdatedByStaffID | UNIQUE (CustomerID, EffectiveTo) bảo đảm một dòng đang hiệu lực; CHECK `EffectiveTo` lớn hơn `EffectiveFrom` | Chép từ snapshot, 7.043; đổi qua UC-08 |
| ENT-04 | Interactions | InteractionID | CustomerID, StaffID | `IsSimulated` mặc định 0 | Mô phỏng 87.662; nhập tay (UC-03) |
| ENT-05 | Tickets | TicketID | CustomerID, AssignedStaffID | CHECK `Status`, `Priority`, `Category`; `ClosedAt` và điểm hài lòng theo BR-02 | Mô phỏng 10.195; nhập tay (UC-04, UC-09) |
| ENT-06 | Staff | StaffID | RoleID | UNIQUE `Username`; `PasswordHash` bắt buộc, là chuỗi băm | Bộ nạp ban đầu: 3 tài khoản demo |
| ENT-07 | Role | RoleID | — | UNIQUE `RoleName` | 3 vai trò: Admin, Manager, Agent |
| ENT-08 | AuditLog | AuditID | StaffID | `StaffID` bắt buộc | Ghi tự động (UC-14) |
| ENT-09 | LoginAttempts | AttemptID | StaffID (có thể rỗng) | CHECK `IsSuccess` và `FailReason` khớp nhau; index (UsernameTried, AttemptedAt) | **Mới (D-25), chưa vào PDM**; ghi bởi UC-01 |
| ENT-10 | ModelVersions | ModelVersionID | — | CHECK `Threshold` thuộc [0, 1] | Script đăng ký mô hình, 1 dòng (v1) |
| ENT-11 | ChurnPredictions | PredictionID | ModelVersionID, CustomerID (có thể rỗng) | CHECK `Probability` thuộc [0, 1]; `CustomerID` rỗng thì bắt buộc `InputJson` hợp lệ | Chấm lô 7.043; Web ghi thêm (UC-05) |
| ENT-12 | RiskConfig | ConfigKey | UpdatedByStaffID | CHECK khóa ngưỡng là số thuộc [0, 1] | 2 khóa: `RiskMediumThreshold`, `RiskHighThreshold` |

Bảng staging `TelcoRaw` (bản sao nguyên văn CSV, 7.043 dòng) nằm **ngoài ERD** và không có ENT; Web không đọc bảng này (R-14).

## 2.6.2 Ma trận use case và thực thể

C = thêm, R = đọc, U = sửa, D = xóa. UC-14 ghi `AuditLog` thay cho các use case include nó, nên cột AuditLog chỉ ghi "C" ở những use case có thay đổi dữ liệu.

| UC | 01 Customers | 02 Snapshots | 03 Contracts | 04 Interactions | 05 Tickets | 06 Staff | 07 Role | 08 AuditLog | 09 LoginAttempts | 10 ModelVersions | 11 Predictions | 12 RiskConfig |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| UC-01 Đăng nhập | | | | | | R | R | C | C | | | |
| UC-02 Quản lý khách hàng | CRU | R | C, R | R | R | | | C | | | R | |
| UC-03 Quản lý tương tác | R | | | CRUD | | R | | C | | | | |
| UC-04 Xử lý ticket | R | | | | CRUD | R | | C | | | | |
| UC-05 Dự báo churn | R | R | R | | | | | C | | R | C | R |
| UC-06 Xem dashboard | R | R | R | R | R | | | | | | R | R |
| UC-07 Nhập khách từ CSV | C | | C | | | | | C | | | | |
| UC-08 Đổi hợp đồng | | | U, C | | | | | C | | | | |
| UC-09 Mở lại ticket | | | | | U | | | C | | | | |
| UC-10 Cấu hình ngưỡng | | | | | | | | C | | | | RU |
| UC-11 Xem nhật ký | | | | | | R | | R | | | | |
| UC-12 Quản lý người dùng | | | | | | CRU | R | C | | | | |
| UC-13 Xem phiên bản mô hình | | | | | | | | | | R | | |
| UC-14 Ghi nhật ký | | | | | | | | C | | | | |

Kiểm: mọi bảng đều có ít nhất một use case ghi hoặc đọc; `Customers`, `CustomerSnapshots`, `TelcoRaw` không bị use case nào sửa trong luồng Web ngoài `Customers` (BR-05).

## 2.6.3 Trạng thái các chức năng của BFD (tính đến 27/10/2026)

BFD hiện có 55 nút = 1 gốc + 6 nhánh + 4 nhóm con của nhánh 1.5 + **44 chức năng lá**; sau khi thêm 1.1.6 và 1.1.7 là 57 nút và 46 lá. Không nút nào thuộc Mức 2 (D-26). Số hiệu theo PowerDesigner (D-17).

| Số PD | Chức năng | Use case | Trạng thái |
|---|---|---|---|
| 1.1.1 | Đăng nhập | UC-01 | Xong |
| 1.1.2 | Quản lý người dùng | UC-12 | Tùy chọn, chưa làm |
| 1.1.3 | Kiểm soát quyền theo vai trò | mọi UC (FR-03) | Xong phần nền; chưa áp lên Action nghiệp vụ |
| 1.1.4 | Ghi nhật ký thao tác | UC-14 | Xong phần cơ chế; chưa ghi trên chức năng thật |
| 1.1.5 | Xem nhật ký thao tác | UC-11 | Chưa làm |
| 1.1.6 | Ghi nhật ký đăng nhập (**mới**) | UC-01 | Chưa làm |
| 1.1.7 | Giới hạn số lần đăng nhập sai (**mới**) | UC-01 | Chưa làm |
| 1.2.1 đến 1.2.4, 1.2.6 | Tìm và lọc, xem chi tiết, thêm, sửa, ngừng theo dõi | UC-02 | Chưa làm |
| 1.2.5 | Cập nhật hợp đồng và dịch vụ | UC-08 | Chưa làm |
| 1.2.7 | Nhập khách từ CSV | UC-07 | Chưa làm (bắt buộc theo cô) |
| 1.3.1 đến 1.3.4 | Ghi nhận, xem và lọc, sửa, xóa tương tác | UC-03 | Chưa làm |
| 1.4.1 | Mở lại ticket | UC-09 | Chưa làm |
| 1.4.2 đến 1.4.6 | Mở, xem danh sách, cập nhật, đóng, xóa ticket | UC-04 | Chưa làm |
| 1.5.1.1 đến 1.5.1.3 | Nạp Telco, sinh dữ liệu mô phỏng, kiểm tra chất lượng | — (Python) | Xong |
| 1.5.2.1 đến 1.5.2.4 | Huấn luyện, chọn mô hình và ngưỡng, đánh giá, phân tích lỗi | — (Python) | Xong |
| 1.5.3.1, 1.5.3.2 | Đóng gói API, chấm điểm theo lô | — (Python) | Xong |
| 1.5.4.1, 1.5.4.2 | Dự báo một khách, xem điểm rủi ro | UC-05 | Chưa làm trên Web (API và dữ liệu đã có) |
| 1.5.4.3 | Cấu hình ngưỡng rủi ro | UC-10 | Chưa làm trên Web |
| 1.5.4.4 | Xem phiên bản mô hình | UC-13 | Tùy chọn, chưa làm |
| 1.6.1 đến 1.6.9 | Dashboard | UC-06 | Chưa làm |

**Tổng 44 chức năng lá hiện có:** 10 xong trọn vẹn, 2 xong phần cơ chế (1.1.3, 1.1.4), 30 chưa làm và bắt buộc, 2 tùy chọn. Báo cáo viết "đã triển khai X trên 46", không viết "toàn bộ 55 chức năng" (Z-02).

## 2.6.4 Mô tả CSDL tóm tắt

Bốn nhóm bảng:

- **Khách hàng và dịch vụ:** Customers, CustomerSnapshots (benchmark IBM, không sửa), CustomerContracts (nghiệp vụ, có lịch sử hiệu lực).
- **Chăm sóc khách hàng:** Interactions, Tickets.
- **Người dùng và kiểm toán:** Role, Staff, AuditLog, LoginAttempts.
- **Dự báo:** ModelVersions, ChurnPredictions, RiskConfig.

Số đối tượng CSDL đã chạy thật (bộ kiểm 44/44 đạt): 11 bảng nghiệp vụ, 12 khóa ngoại, 7 DEFAULT, 4 UNIQUE, 11 khóa chính, 12 CHECK. Sau khi thêm `LoginAttempts` (D-25, một CHECK nhiều cột): 12 bảng, 13 khóa ngoại, 8 DEFAULT, 4 UNIQUE, 12 khóa chính, 13 CHECK. Các CHECK nhiều cột nằm ở `constraints_bo_sung.sql` vì hộp thuộc tính bảng của PowerDesigner không có tab CHECK nhiều cột (D-21).

Dữ liệu có hai nguồn cần ghi rõ trong báo cáo: **IBM Telco** là dữ liệu mẫu (không phải dữ liệu CRM vận hành, `EstimatedJoinDate` chỉ là ngày ước lượng, `CustomerStatus = Active` do script gán), và **Interactions, Tickets mô phỏng** (`IsSimulated = 1`, sinh bằng seed 42, không đọc nhãn Churn, không dùng để huấn luyện).

## 2.6.5 Việc còn thiếu của mục này

| Việc | Ai làm | Ghi chú |
|---|---|---|
| Vẽ ERD (CDM, PDM) bản cuối, thêm `LoginAttempts` | `phan-tich-he-thong-powerdesigner` | D-21: sửa PDM, sinh lại `schema.sql` |
| Vẽ BFD bản cuối, thêm 1.1.6 và 1.1.7 **ở cuối nhánh 1.1**, ghi trạng thái từng nút | `phan-tich-he-thong-powerdesigner` | Thêm ở cuối để PowerDesigner không đánh số lại nút cũ |
| Từ điển dữ liệu: bảng 21 cột IBM Telco và bảng dữ liệu mô phỏng | `phan-tich-he-thong-powerdesigner` hoặc `bao-cao-do-an` | Hướng dẫn của cô (Mục 13.1) bắt buộc có trong báo cáo; chưa làm |
| Từ điển từng cột của 12 bảng | `phan-tich-he-thong-powerdesigner` | Xuất từ PDM |
