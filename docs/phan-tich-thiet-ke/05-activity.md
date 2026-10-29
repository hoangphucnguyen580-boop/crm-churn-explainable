# 05 — Sơ đồ hoạt động và trạng thái (Chương 2, mục 2.4)

Nguồn ID: `00-id-registry.md`. Sơ đồ nguồn PlantUML nằm ở `diagrams/*.puml`, ảnh render ở `diagrams/*.png` (đã kiểm cú pháp bằng PlantUML 1.2024.7). Lượt sau giao `phan-tich-he-thong-powerdesigner` vẽ lại trong PowerDesigner. Bước trong sơ đồ bám theo luồng chính và ngoại lệ ở `04-dac-ta-use-case.md`.

## 2.4.1 Activity Diagram — xử lý ticket (UC-04, UC-09)

![Activity xử lý ticket](diagrams/act-ticket.png)

Hai làn: Nhân viên và Hệ thống. Luồng đi từ mở ticket (Open), phân công (InProgress), đóng (Closed), rồi tùy chọn mở lại.

| Nhánh trong sơ đồ | Điều kiện | Kết quả | Bước use case | Căn cứ |
|---|---|---|---|---|
| Mở ticket không hợp lệ | Thiếu khách, loại hoặc ưu tiên; giá trị ngoài danh sách | Báo từng trường lỗi, quay lại nhập | UC-04, 4a | FR-21 |
| Đóng ticket không hợp lệ | Thiếu kết quả giải quyết; điểm ngoài 1 đến 5; `ClosedAt` sớm hơn `CreatedAt` | Từ chối, ticket giữ nguyên, quay lại bước đóng | UC-04, 10a, 10b, 10c | FR-24, BR-02 |
| Mở lại bị từ chối | Vai trò không đủ quyền, hoặc lý do rỗng hoặc quá dài | Ticket giữ nguyên Closed | UC-09, 4b, 4c | FR-25, BR-03 |
| Mở lại thành công | Manager hoặc Admin, có lý do | Về InProgress, xóa `ClosedAt` và điểm hài lòng, ghi `ReopenReason`; xử lý tiếp như UC-04 | UC-09, 5 | FR-25, BR-03 |

Sơ đồ chưa vẽ ca "chuyển sai thứ tự" (Open thẳng sang Closed, UC-04 bước 8a); ca này thể hiện ở sơ đồ trạng thái (mục 2.4.3).

<details><summary>Mã nguồn PlantUML</summary>

```plantuml
@startuml
' Activity: xử lý ticket (UC-04) và mở lại (UC-09)
title Xử lý ticket (UC-04) và mở lại ticket (UC-09)
skinparam shadowing false
|Nhân viên|
start
repeat
  :Nhập khách, loại, mức ưu tiên;
  |Hệ thống|
  :Kiểm tra giá trị;
backward:Báo lỗi từng trường;
repeat while (Hợp lệ?) is (không) not (có)
:Tạo ticket (Status = Open,\nCreatedAt = giờ hiện tại);
:Ghi AuditLog;
|Nhân viên|
:Chọn ticket Open, phân công người phụ trách,\nđổi ưu tiên nếu cần, chuyển InProgress;
|Hệ thống|
:Lưu Status = InProgress, AssignedStaffID;
:Ghi AuditLog;
|Nhân viên|
repeat
  :Chọn "Đóng ticket", nhập kết quả giải quyết\n(điểm hài lòng 1 đến 5 nếu có);
  |Hệ thống|
  :Kiểm tra: kết quả không rỗng,\nđiểm 1 đến 5, ClosedAt không sớm hơn CreatedAt;
backward:Báo lỗi, ticket giữ nguyên;
repeat while (Hợp lệ?) is (không) not (có)
:Lưu Status = Closed, ClosedAt,\nResolution, SatisfactionScore;
:Ghi AuditLog;
|Nhân viên|
if (Cần mở lại?\n(chỉ Manager hoặc Admin)) then (có)
  :Nhập lý do mở lại;
  |Hệ thống|
  if (Vai trò đủ quyền\nvà lý do hợp lệ?) then (có)
    :Status = InProgress, xóa ClosedAt\nvà điểm hài lòng, lưu ReopenReason;
    :Ghi AuditLog;
    :Ticket quay lại xử lý như UC-04;
  else (không)
    :Từ chối, ticket giữ nguyên Closed;
  endif
else (không)
endif
stop
@enduml
```

</details>

## 2.4.2 Activity Diagram — dự báo churn (UC-05)

![Activity dự báo churn](diagrams/act-du-bao.png)

Bốn làn: Nhân viên, Web CRM, FastAPI, SQL Server. Có hai cách vào (khách có sẵn, nhập thủ công) gặp nhau ở bước gọi `/predict`.

| Nhánh lỗi trong sơ đồ | Điều kiện | Kết quả | Bước use case | Căn cứ |
|---|---|---|---|---|
| Khách chưa đủ dữ liệu | Không có snapshot, hoặc không có đúng một hợp đồng đang hiệu lực | Báo dùng Nhập thủ công, không gọi API | UC-05, 2a, 2b | BR-14, FR-28 |
| Dữ liệu nhập tay không hợp lệ | Thiếu trường, ngoài danh sách, số âm, mâu thuẫn giữa các cột | Báo từng trường lỗi, **không gọi API** | UC-05, 3a | FR-29, BR-15 |
| API không sẵn sàng | FastAPI chưa chạy, quá thời gian T, trả 422 hoặc 500 | Báo lỗi, không ghi `ChurnPredictions` | UC-05, 4a, 5a | FR-31, NFR-08 |
| Ngưỡng không hợp lệ | `RiskConfig` thiếu khóa hoặc Medium không nhỏ hơn High | Báo lỗi cấu hình, không ghi | UC-05, 6a | BR-06 |
| Lưu thất bại | Mất kết nối SQL Server khi lưu | Báo "kết quả chưa được lưu", **không báo thành công** | UC-05, 7a | FR-31 |

<details><summary>Mã nguồn PlantUML</summary>

```plantuml
@startuml
' Activity: dự báo churn (UC-05), có nhánh lỗi API và lỗi lưu CSDL
title Dự báo churn (UC-05)
skinparam shadowing false
|Nhân viên|
start
:Chọn "Dự báo churn";
if (Cách dự báo?) then (khách có sẵn)
  |Web CRM|
  :Đọc 19 đặc trưng từ CSDL\n(hồ sơ, hợp đồng hiệu lực, snapshot);
  if (Có snapshot và đúng một\nhợp đồng hiệu lực?) then (không)
    :Báo "chưa đủ dữ liệu, dùng Nhập thủ công"\n(BR-14);
    stop
  endif
else (nhập thủ công)
  |Nhân viên|
  :Nhập 19 đặc trưng;
  |Web CRM|
  if (Dữ liệu hợp lệ\n(danh sách giá trị, BR-15)?) then (không)
    :Báo lỗi từng trường, không gọi API;
    stop
  endif
endif
|Web CRM|
:Gửi 19 đặc trưng tới /predict\n(chờ tối đa T giây);
|FastAPI|
:Kiểm tra đầu vào,\ntính xác suất churn;
|Web CRM|
if (API trả kết quả hợp lệ\ntrong T giây?) then (không)
  :Báo "dịch vụ dự báo chưa sẵn sàng\nhoặc lỗi", không ghi gì;
  stop
endif
:Đọc ngưỡng từ RiskConfig,\ngán mức Low, Medium hoặc High;
if (Ngưỡng hợp lệ\n(Medium < High)?) then (không)
  :Báo lỗi cấu hình, không ghi gì;
  stop
endif
|SQL Server|
:Lưu ChurnPredictions (kèm InputJson),\nghi AuditLog;
|Web CRM|
if (Lưu thành công?) then (không)
  :Báo "kết quả chưa được lưu",\nkhông báo thành công;
  stop
endif
|Nhân viên|
:Xem xác suất, mức rủi ro,\nphiên bản mô hình;
stop
@enduml
```

</details>

## 2.4.3 State Diagram — vòng đời ticket (BR-01 đến BR-03)

![Vòng đời ticket](diagrams/state-ticket.png)

| Chuyển trạng thái | Ai làm được | Điều kiện | Kết quả | Căn cứ |
|---|---|---|---|---|
| (bắt đầu) → Open | Agent, Manager, Admin | Khách, loại, ưu tiên hợp lệ | `CreatedAt` là giờ hiện tại, `ClosedAt` rỗng | FR-21 |
| Open → InProgress | Agent, Manager, Admin | Có người phụ trách | `Status = InProgress`, `AssignedStaffID` | FR-23, BR-01 |
| InProgress → Closed | Agent, Manager, Admin | Có kết quả giải quyết | `ClosedAt` gán bởi hệ thống, điểm hài lòng 1 đến 5 hoặc rỗng | FR-24, BR-02 |
| Closed → InProgress | Manager, Admin | Có lý do | Xóa `ClosedAt` và điểm hài lòng, ghi `ReopenReason`, giữ `Resolution` | FR-25, BR-03 |
| Open, InProgress, Closed → (xóa) | Admin | Xác nhận | Xóa dòng, audit lưu giá trị cũ | FR-26 |

Không cho phép: Open thẳng sang Closed; Closed về Open. Trạng thái này khớp với ràng buộc CSDL: ticket Closed phải có `ClosedAt`, ticket chưa Closed không được có `ClosedAt` hay điểm hài lòng (BR-02), nên các chuyển sai bị CSDL chặn lần nữa ở tầng dưới.

<details><summary>Mã nguồn PlantUML</summary>

```plantuml
@startuml
' State: vòng đời ticket (BR-01 đến BR-03)
title Vòng đời ticket
skinparam shadowing false
[*] --> Open : Mở ticket
Open --> InProgress : Phân công, chuyển InProgress
InProgress --> Closed : Đóng ticket\n[có kết quả giải quyết;\nClosedAt = giờ hiện tại]
Closed --> InProgress : Mở lại (Manager, Admin)\n[có lý do; xóa ClosedAt và điểm hài lòng]
Open --> [*] : Xóa (Admin)
InProgress --> [*] : Xóa (Admin)
Closed --> [*] : Xóa (Admin)
note right of Open
  Không được đóng thẳng
  Open sang Closed
end note
@enduml
```

</details>
