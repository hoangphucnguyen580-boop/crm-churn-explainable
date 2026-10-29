# Prompt bàn giao cho `phan-tich-he-thong-powerdesigner`

Cách dùng: mở cuộc trò chuyện mới **trong Project đề tài 18** (để skill thấy file Project), dán nguyên khối bên dưới. Làm **từng lượt một việc**, bắt đầu từ việc A. Cần các file sau có trong Project: `00-id-registry.md`, `03-mo-hinh-use-case.md`, `05-activity.md`, `07-du-lieu.md`, kế hoạch v2.8, `schema.sql`, `constraints_bo_sung.sql`, `kiem_tra_CRM_Churn.sql`, các file PowerDesigner (`.bpm`, `.cdm`, `.pdm`).

---

Đọc file kế hoạch (bản v2.8) và các file trong thư mục `docs/phan-tich-thiet-ke/`. Lượt này dùng skill **phan-tich-he-thong-powerdesigner**. Câu trả lời cho 3 câu hỏi của skill:

1. Hệ thống quản lý gì, mục tiêu: CRM tích hợp dự báo khách hàng rời bỏ (đề tài 18, Thực tập ngành, Mức 1): hồ sơ khách, hợp đồng và dịch vụ, tương tác, ticket, dự báo churn, phân quyền, nhật ký thao tác.
2. Bài môn học Thực tập ngành, phương pháp có cấu trúc, PowerDesigner 16.7, DBMS trong PowerDesigner chọn SQL Server 2017 (máy chạy SQL Server 2022). Cô yêu cầu: ERD, BFD (cây chức năng) và Use Case, Activity, sơ đồ kiến trúc "phiên bản cuối, thống nhất với CSDL và chức năng thực tế" (Z-01).
3. Đã có: PHD/BFD 55 nút, CDM 11 thực thể, PDM 11 bảng, `schema.sql`. Làm tiếp: cập nhật theo yêu cầu mới của cô (bên dưới). DFD không làm.

**Quy tắc đã chốt (không đổi):** PDM là bản gốc, không sinh lại PDM từ CDM (D-21); sửa PDM rồi sinh lại `schema.sql`, xóa database, chạy lại chuỗi 00 → 04 và bộ kiểm; các CHECK nhiều cột không để trong PDM mà viết bằng `ALTER TABLE` ở `constraints_bo_sung.sql` (hộp thuộc tính bảng của PowerDesigner không có tab CHECK nhiều cột); số hiệu chức năng theo PowerDesigner (D-17); `TelcoRaw` là bảng staging ngoài ERD.

**Việc A — thêm bảng `LoginAttempts` vào CDM và PDM (D-25, Z-12).** Cột: `AttemptID` bigint identity (PK); `UsernameTried` varchar(50) not null; `AttemptedAt` datetime not null DEFAULT getdate(); `IsSuccess` bit not null; `FailReason` varchar(20) null; `StaffID` int null, khóa ngoại tới `Staff`; `ClientIp` varchar(45) null. Index trên (`UsernameTried`, `AttemptedAt`). CHECK duy nhất, nhiều cột, viết ở `constraints_bo_sung.sql`: `(IsSuccess = 1 AND FailReason IS NULL) OR (IsSuccess = 0 AND FailReason IN ('UnknownUser','WrongPassword','Inactive','Locked'))`. Không lưu mật khẩu ở bảng này. Sau khi sửa, báo số đối tượng kỳ vọng của database: 12 bảng nghiệp vụ, 13 khóa ngoại, 8 DEFAULT, 4 UNIQUE, 12 khóa chính, 13 CHECK. Liệt kê chính xác các file phải sửa theo: `kiem_tra_CRM_Churn.sql` (Phần 1 các con số, thêm test cho bảng mới, thêm bảng vào so số dòng trước và sau ROLLBACK), `config.json` (`check_constraints` 12 → 13), `check_connection.py`, README gói SQL (11 → 12 bảng). Cập nhật CDM thêm thực thể và Association cho đúng.

**Việc B — BFD cuối.** Thêm hai nút **ở cuối nhánh 1.1** (để PowerDesigner không đánh số lại các nút cũ): 1.1.6 "Ghi nhật ký đăng nhập" và 1.1.7 "Giới hạn số lần đăng nhập sai". Sau khi thêm phải kiểm lại số hiệu của mọi nút cũ có giữ nguyên không. Ghi trạng thái từng chức năng lá theo bảng ở `07-du-lieu.md` mục 2.6.3 (xong, xong phần nền, chưa làm, tùy chọn) bằng cách thể hiện phù hợp với PowerDesigner (màu hoặc ghi chú). Chú ý: **không nút nào thuộc Mức 2**, đừng gạch nút nào (D-26). Hai nút "Xoá" (1.3.4, 1.4.6): để Phúc quyết đổi chữ hay giữ.

**Việc C — vẽ lại sơ đồ UML trong PowerDesigner (nếu bản 16.7 làm được; nếu không thì nói rõ và giữ bản PlantUML):** Use Case tổng thể (4 actor, Admin kế thừa Manager, Manager kế thừa Agent; 14 use case; include, extend) từ `03-mo-hinh-use-case.md`; 2 Activity Diagram (xử lý ticket, dự báo churn) và 1 State Diagram (vòng đời ticket) từ `05-activity.md`. Sơ đồ kiến trúc và sơ đồ tuần tự `/predict` giữ bản PlantUML trong `diagrams/` (hỏi Phúc nếu muốn đổi).

**Việc D — từ điển dữ liệu:** bảng từng cột của 12 bảng (xuất từ PDM); bảng 21 cột IBM Telco (nhóm, vai trò, xử lý; lấy từ hướng dẫn của cô Mục 2.2); bảng dữ liệu mô phỏng `Interactions`, `Tickets` (lấy từ `simulation_config.json`).

**Việc E — xuất ảnh ERD (CDM và PDM) bản cuối.**

Dừng ở cổng sau **mỗi việc** chờ mình duyệt. Bắt đầu bằng việc A. Nếu cần lệch kế hoạch thì nêu lý do trước. Số liệu nào chưa kiểm thì ghi rõ chưa kiểm.
