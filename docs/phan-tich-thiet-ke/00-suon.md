# Sườn phần Phân tích – Thiết kế (P1c, Z-01) — đề tài 18

## 1. Hướng chọn và lý do

- **Hướng kết hợp.** Cô yêu cầu Use Case và Activity Diagram (hướng đối tượng) nhưng cũng yêu cầu BFD, CDM/PDM (cấu trúc kiểu PowerDesigner). Đề có code web và CSDL quan hệ nên kết hợp là phương án an toàn.
- **Không làm Class Diagram.** Cô không yêu cầu; ERD 12 bảng đã làm vai trò mô hình dữ liệu. Làm thêm Class Diagram là thêm một nguồn sự thật phải giữ khớp với ERD.
- **Biến thể B** (có code): thêm mục cài đặt và demo, nhưng mục đó viết sau khi Web xong (P5, P6).
- Sườn này nằm **trong Chương 2** của khung báo cáo cô giao (Mục 9.1 kế hoạch). Chương 1 và các chương còn lại do `bao-cao-do-an` viết sau.

## 2. Sườn và việc cần làm từng mục

| # | File | Chương 2 của cô | Cần làm gì | Khi nào |
|---|---|---|---|---|
| 2 | `02-yeu-cau.md` | 2.1 Yêu cầu chức năng/phi chức năng | Bảng FR, NFR, BR từ `00-id-registry.md`, thêm tiêu chí nghiệm thu dạng Cho/Khi/Thì cho FR Must | Lượt kế |
| 3 | `03-mo-hinh-use-case.md` | 2.2 Use Case tổng thể | Actor, danh sách 14 UC, use case diagram 3 vai trò (mã nguồn PlantUML kèm mô tả chữ), include/extend | Lượt kế |
| 4 | `04-dac-ta-use-case.md` | 2.3 Đặc tả Use Case | 6 UC chính theo template (tiền điều kiện, luồng chính, luồng thay thế bám số bước, hậu điều kiện, BR liên quan); UC phụ viết ngắn | 2 đến 3 lượt |
| 5 | `05-activity.md` | 2.4 Activity Diagram | Activity cho xử lý ticket và cho dự báo churn (có nhánh lỗi API, lỗi lưu CSDL) | 1 lượt |
| 6 | `06-kien-truc.md` | 2.5 Kiến trúc | Sơ đồ ASP.NET Core MVC – SQL Server – FastAPI – mô hình ML, phân rã module web, luồng gọi `/predict` | 1 lượt |
| 7 | `07-du-lieu.md` | 2.6 BFD, CDM/PDM, mô tả CSDL | Chỉ bảng ánh xạ ENT ↔ bảng và trạng thái 44 chức năng lá; **không vẽ ERD/BFD ở đây**, giao `phan-tich-he-thong-powerdesigner` | Sau mục 4 |
| 8 | `08-kiem-thu.md` | Chương 4, kiểm thử | Chiến lược, test case, ma trận FR → UC → TC | **Sau khi Web xong (P7)**, chưa viết bây giờ |
| 9 | `09-cai-dat-demo.md` | Chương 3 và 4 | Ánh xạ UC → Controller/View, ảnh chạy thật | Sau P5, P6 |
| — | `traceability.md` | Phụ lục | Ma trận FR → UC → TC, cập nhật sau mỗi nhóm mục | Mỗi lượt |
| — | handoff prompt | — | Prompt đưa cho `phan-tich-he-thong-powerdesigner` (vẽ sơ đồ) và `bao-cao-do-an` (định dạng) | Cuối P1c lượt 1 |

## 3. Mục tùy chọn

| Mục | Bật? | Lý do |
|---|---|---|
| Business rules | **Bật** (đã có BR-01 đến BR-13) | Đề có nhiều quy tắc ticket, hợp đồng, rủi ro |
| Yêu cầu bảo mật | **Bật** (NFR-01 đến NFR-04, NFR-16) | Đề web có tài khoản và phân quyền, cô nhấn mạnh |
| State Diagram vòng đời ticket | **Bật** (Phúc chốt Bước 3, 26/10) | BR-01 đến BR-03 là vòng đời trạng thái rõ; thêm một hình nhỏ ở `05-activity.md` |
| DFD | Tắt | Cô không nhắc (D-09 để tùy chọn) |
| Quy trình phát triển, quản lý dự án, phân công | Tắt | Cô không yêu cầu; đồ án cá nhân |

## 4. Thứ tự viết

`02` → `03` → `04` (UC-01 đến UC-06) → `05` → `06` → `07` → handoff sang PowerDesigner. `08` và `09` chờ P5 đến P7.

## 5. Đã chốt ở Bước 3 (Phúc, 26/10/2026)

1. UC phụ (UC-07 đến UC-13) đặc tả ngắn; riêng **UC-08 (đổi hợp đồng) và UC-09 (mở lại ticket) đặc tả đầy đủ** vì mang quy tắc nghiệp vụ.
2. Có thêm **State Diagram vòng đời ticket**.
3. Use case diagram dùng **kế thừa actor**: Admin kế thừa Manager, Manager kế thừa Agent.
