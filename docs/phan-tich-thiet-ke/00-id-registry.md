# Bảng ID chủ — Đề tài 18: CRM tích hợp dự báo khách hàng rời bỏ (Mức 1)

Quy ước: ID chỉ được thêm ở đây trước, rồi mới dùng ở các mục khác. Cột "BFD" dùng số hiệu PowerDesigner (D-17), "Z" là mã yêu cầu của cô trong kế hoạch v2.8 (Mục 13.3), "BR" là quy tắc nghiệp vụ.
Trạng thái: **ĐỀ XUẤT** = chờ Phúc chốt ở Bước 3, các con số đánh dấu "giả định" là giả định của đồ án, sẽ đo lại ở P7.

## 1. Actor

| ID | Tên | Ghi chú |
|---|---|---|
| ACT-01 | Admin (Quản trị viên) | Mọi quyền của Manager, thêm: xem nhật ký thao tác, quản lý người dùng, xóa dữ liệu |
| ACT-02 | Manager (Quản lý CSKH) | Mọi quyền của Agent, thêm: sửa hồ sơ, đổi hợp đồng, nhập CSV, mở lại ticket, cấu hình ngưỡng, xem dashboard |
| ACT-03 | Agent (Nhân viên CSKH) | Xem hồ sơ và rủi ro, ghi tương tác, xử lý ticket, gọi dự báo |
| ACT-04 | Dịch vụ dự báo FastAPI | Actor hệ thống bên ngoài (phụ): nhận 19 đặc trưng, trả xác suất churn |

- Quan hệ kế thừa (ĐỀ XUẤT, đúng với ma trận quyền ở Mục 7.2 kế hoạch): Admin kế thừa Manager, Manager kế thừa Agent.
- Khách hàng cuối **không** đăng nhập hệ thống nên không phải actor.

## 2. Yêu cầu chức năng (FR)

Ưu tiên theo MoSCoW. "UC" là use case chứa FR đó.

| ID | Yêu cầu (hệ thống phải…) | Ưu tiên | UC | BFD | Z / nguồn |
|---|---|---|---|---|---|
| FR-01 | cho phép nhân viên đăng nhập bằng tài khoản Staff; sai tên hoặc sai mật khẩu đều báo cùng một câu | Must | UC-01 | 1.1.1 | F-01 |
| FR-02 | cho phép đăng xuất và ghi nhận việc đăng xuất | Must | UC-01 | 1.1.1 | F-01 |
| FR-03 | kiểm quyền theo vai trò ở từng Action; vai trò không đủ quyền thấy trang "Không có quyền" | Must | UC-01 (áp cho mọi UC) | 1.1.3 | R-11, Z-08 |
| FR-04 | ghi mọi lần đăng nhập (thành công và thất bại) vào `LoginAttempts`, không lưu mật khẩu | Must | UC-01 | 1.1.6 | Z-12 |
| FR-05 | tạm khóa đăng nhập khi cùng tên đăng nhập sai liên tiếp quá ngưỡng cấu hình | Should | UC-01 | 1.1.7 | Z-12 |
| FR-06 | ghi `AuditLog` tự động khi thêm, sửa, xóa dữ liệu quan trọng, che `PasswordHash` | Must | UC-14 | 1.1.4 | Y-07, Z-04 |
| FR-07 | cho Admin xem và lọc `AuditLog` theo người, bảng, ngày | Must | UC-11 | 1.1.5 | F-12 |
| FR-08 | cho Admin quản lý tài khoản nhân viên và vai trò | Could | UC-12 | 1.1.2 | F-02 |
| FR-09 | hiển thị danh sách khách có phân trang, tìm theo CustomerID, lọc theo hợp đồng, nhóm tenure, mức rủi ro | Must | UC-02 | 1.2.1 | F-03, Z-03 |
| FR-10 | hiển thị chi tiết khách: hồ sơ, hợp đồng và dịch vụ đang hiệu lực, lịch sử tương tác, ticket, dự báo gần nhất | Must | UC-02 | 1.2.2 | F-04, Z-03 |
| FR-11 | cho Manager và Admin thêm hồ sơ khách mới | Must | UC-02 | 1.2.3 | F-05 |
| FR-12 | cho Manager và Admin sửa hồ sơ khách | Must | UC-02 | 1.2.4 | F-05 |
| FR-13 | cho Manager và Admin ngừng theo dõi khách (xóa mềm, đổi `CustomerStatus`) | Must | UC-02 | 1.2.6 | F-05 |
| FR-14 | cho Manager và Admin đổi hợp đồng và dịch vụ bằng cách đóng dòng đang hiệu lực rồi thêm dòng mới ở `CustomerContracts`, không sửa `CustomerSnapshots` | Must | UC-08 | 1.2.5 | D-19, R-14, Z-03 |
| FR-15 | cho Manager và Admin nhập khách từ CSV theo mẫu cố định, kiểm trùng CustomerID và dữ liệu thiếu, báo số dòng thành công và thất bại | Must | UC-07 | 1.2.7 | Z-03 |
| FR-16 | cho nhân viên ghi nhận tương tác (kênh, loại, mô tả, kết quả, người phụ trách) | Must | UC-03 | 1.3.1 | F-06 |
| FR-17 | cho xem và lọc lịch sử tương tác theo khách, loại, kênh, khoảng thời gian | Must | UC-03 | 1.3.2 | Z-04 |
| FR-18 | cho Manager và Admin sửa tương tác | Must | UC-03 | 1.3.3 | Z-04 |
| FR-19 | cho Admin xóa tương tác | Must | UC-03 | 1.3.4 | Z-04 |
| FR-20 | gắn nhãn "dữ liệu mô phỏng" trên tương tác và ticket có `IsSimulated = 1` | Must | UC-03, UC-04, UC-06 | — | L4, R-12 |
| FR-21 | cho nhân viên mở ticket mới (trạng thái Open) | Must | UC-04 | 1.4.2 | F-07 |
| FR-22 | cho xem danh sách ticket và lọc theo trạng thái, mức ưu tiên, nhân viên phụ trách, khách | Must | UC-04 | 1.4.3 | Z-05 |
| FR-23 | cho phân công nhân viên, đổi mức ưu tiên, chuyển trạng thái Open sang InProgress | Must | UC-04 | 1.4.4 | Z-05 |
| FR-24 | khi đóng ticket bắt buộc có kết quả giải quyết, lưu `ClosedAt`, cho ghi mức hài lòng 1 đến 5 | Must | UC-04 | 1.4.5 | D-18, Z-05 |
| FR-25 | cho Manager và Admin mở lại ticket Closed, bắt buộc nhập lý do, ghi lịch sử | Must | UC-09 | 1.4.1 | D-18, Z-05 |
| FR-26 | cho Admin xóa ticket | Should | UC-04 | 1.4.6 | F-07 |
| FR-27 | tính thời gian xử lý ticket bằng `ClosedAt` trừ `CreatedAt` | Must | UC-04, UC-06 | 1.4.5, 1.6.8 | F-07 |
| FR-28 | dự báo cho khách có sẵn: lấy đúng 19 đặc trưng từ CSDL (hợp đồng đang hiệu lực và snapshot), gọi `/predict`, nhận xác suất | Must | UC-05 | 1.5.4.1 | D-06, Z-06 |
| FR-29 | dự báo từ đặc trưng nhập tay: kiểm dữ liệu trước khi gọi API, lưu với `CustomerID` NULL và `InputJson` | Must | UC-05 | 1.5.4.1 | F-09, Z-06 |
| FR-30 | hiển thị xác suất churn, mức Low/Medium/High theo ngưỡng `RiskConfig`, phiên bản mô hình, ghi chú "chỉ hỗ trợ quyết định" | Must | UC-05 | 1.5.4.2 | R-04, R-07 |
| FR-31 | lưu kết quả vào `ChurnPredictions`; khi API chưa chạy, quá thời gian, dữ liệu sai hoặc mất SQL Server thì báo lỗi, không báo thành công khi chưa lưu được | Must | UC-05 | 1.5.4.1 | Z-06 |
| FR-32 | cho Manager và Admin xem và sửa ngưỡng Medium, High, kiểm 0 ≤ Medium < High ≤ 1 | Must | UC-10 | 1.5.4.3 | R-04, F-10 |
| FR-33 | cho Manager và Admin xem danh sách phiên bản mô hình, metric, ngưỡng | Could | UC-13 | 1.5.4.4 | F-13 |
| FR-34 | dashboard hiển thị tổng khách, phân bố nhãn churn (dữ liệu mẫu), phân bố theo hợp đồng | Must | UC-06 | 1.6.1 | Z-07 |
| FR-35 | dashboard hiển thị churn theo nhóm tenure và retention proxy, kèm chú thích giới hạn | Must | UC-06 | 1.6.2, 1.6.3 | D-05, Z-07 |
| FR-36 | dashboard hiển thị mức phí hằng tháng (dữ liệu mẫu) và phân khúc khách | Must | UC-06 | 1.6.4, 1.6.5 | M1-2, R-13 |
| FR-37 | dashboard hiển thị phân bố mức rủi ro và danh sách khách điểm cao, chỉ để xem xét, không gợi ý hành động | Must | UC-06 | 1.6.6 | Z-07, R-07 |
| FR-38 | dashboard hiển thị thống kê tương tác theo loại, kênh, thời gian | Must | UC-06 | 1.6.7 | Z-07 |
| FR-39 | dashboard hiển thị số ticket theo trạng thái, ưu tiên, thời gian xử lý trung bình, mức hài lòng | Must | UC-06 | 1.6.8 | Z-07 |
| FR-40 | cho lọc số liệu dashboard theo hợp đồng, loại internet, phương thức thanh toán, nhóm tenure | Should | UC-06 | 1.6.9 | Z-07 |

## 3. Yêu cầu phi chức năng (NFR)

Phân loại theo ISO/IEC 25010 (tên đặc tính theo hiểu biết của tao, đối chiếu lại khi trích dẫn). Con số "giả định" do đồ án tự đặt, đo ở P7.

| ID | Đặc tính | Yêu cầu | Cách đo |
|---|---|---|---|
| NFR-01 | Security | Mật khẩu lưu dạng băm của `PasswordHasher` (ASP.NET), không lưu thuần | Đọc cột `PasswordHash` (84 ký tự, đã đo 22/10); không có mật khẩu rõ trong DB |
| NFR-02 | Security | Mỗi Action chặn quyền ở phía máy chủ, không chỉ ẩn nút | Ba vai trò truy cập trực tiếp URL từng chức năng (Z-08) |
| NFR-03 | Security | `AuditLog` và `LoginAttempts` không chứa mật khẩu hay `PasswordHash` thật | Truy vấn tìm chuỗi mật khẩu thử; `PasswordHash` chỉ hiện `***` |
| NFR-04 | Security | Mọi trang đòi đăng nhập trừ trang đăng nhập; cookie HttpOnly, Secure, hết hạn 8 giờ; form POST có antiforgery. Mốc tham chiếu OWASP ASVS mức thấp nhất (ĐỀ XUẤT, chưa đối chiếu ASVS) | Truy cập khi chưa đăng nhập bị đẩy về Login; kiểm cờ cookie |
| NFR-05 | Performance efficiency | Web gọi `/predict` trả kết quả với p95 ≤ 500 ms (giả định) | 200 lần gọi qua HTTP thật, báo trung vị, p95, số lần, tách thời gian API và toàn yêu cầu (Z-08) |
| NFR-06 | Performance efficiency | Trang danh sách khách (7.043 bản ghi, có phân trang) tải ≤ 3 giây (giả định) | Đo trên máy demo, ghi số liệu |
| NFR-07 | Performance efficiency | Trang dashboard tải ≤ 5 giây (giả định) | Đo trên máy demo, ghi số liệu |
| NFR-08 | Reliability | Mất FastAPI, quá thời gian hoặc mất SQL Server thì báo lỗi dễ hiểu, không treo trang, không báo thành công giả | Tắt API, ngắt SQL Server rồi thử dự báo (Z-06, Z-08) |
| NFR-09 | Reliability | Toàn vẹn dữ liệu do CSDL bảo đảm: bộ kiểm hiện có 44 test, sẽ thêm test cho `LoginAttempts`, tất cả đạt sau khi dựng lại | Chạy `kiem_tra_CRM_Churn.sql` |
| NFR-10 | Flexibility | Ngưỡng rủi ro đọc từ `RiskConfig`, chuỗi kết nối ở user-secrets, tham số khóa đăng nhập ở `appsettings.json`; không hard-code | Đổi giá trị rồi chạy lại, không sửa mã |
| NFR-11 | Maintainability | Người khác chạy lại được từ đầu theo README: dựng CSDL, nạp Telco, mô phỏng, đăng ký mô hình, chấm điểm, FastAPI, Web; seed 42, ghi phiên bản thư viện | Làm theo README trên máy sạch (Z-09) |
| NFR-12 | Maintainability | Dùng .NET 9 cho prototype, ghi rõ hết hỗ trợ 10/11/2026, không triển khai công khai | Kiểm README và Chương 3, 5 (Z-10) |
| NFR-13 | Functional suitability | Số liệu hiển thị trung thực về nguồn: nhãn "dữ liệu mẫu IBM" hoặc "dữ liệu mô phỏng"; không gọi `MonthlyCharges` là doanh thu; không diễn giải dự báo là nguyên nhân | Rà từng màn hình và biểu đồ theo danh sách nhãn (R-02, R-12, R-13) |
| NFR-14 | Interaction capability | Nhãn tiếng Việt; có trạng thái rỗng, đang tải, lỗi; form báo lỗi nhập liệu rõ ràng | Rà từng màn hình; kiểm thử ca nhập sai |
| NFR-15 | Compatibility | Chạy trên hai trình duyệt phổ biến bản mới (Chrome, Edge — giả định) | Chạy kịch bản chính trên từng trình duyệt |
| NFR-16 | Security (dữ liệu) | Chỉ dùng dữ liệu công khai/mô phỏng; repo public không chứa mật khẩu, chuỗi kết nối, CSV gốc, `delivery/` | Xem `git status` trước mỗi commit; rà gói nộp (R-01, R-06, R-15) |

## 4. Quy tắc nghiệp vụ (BR)

| ID | Quy tắc | Nguồn |
|---|---|---|
| BR-01 | Ticket đi theo luồng Open → InProgress → Closed | D-18 |
| BR-02 | Ticket Closed phải có `ClosedAt` và kết quả giải quyết; chưa Closed thì `ClosedAt` rỗng; `ClosedAt` không sớm hơn `CreatedAt`; điểm hài lòng (1 đến 5) chỉ có ở ticket Closed | Y-04, L7 |
| BR-03 | Mở lại ticket: chỉ Manager và Admin; bắt buộc nhập lý do; ticket về InProgress, xóa `ClosedAt` và điểm hài lòng, giữ `Resolution`; ghi `AuditLog` | D-18 |
| BR-04 | Mỗi khách có đúng một dòng hợp đồng đang hiệu lực (`EffectiveTo` NULL); đổi hợp đồng là đóng dòng cũ rồi thêm dòng mới; `EffectiveTo` lớn hơn `EffectiveFrom` | D-19 |
| BR-05 | Không sửa `TelcoRaw` và `CustomerSnapshots` (dữ liệu benchmark IBM) | R-14 |
| BR-06 | Mức rủi ro: High nếu xác suất ≥ `RiskHighThreshold`; Medium nếu ≥ `RiskMediumThreshold`; còn lại Low; 0 ≤ Medium < High ≤ 1 | D-13 |
| BR-07 | Dự báo nhập tay: `CustomerID` rỗng thì bắt buộc có `InputJson` hợp lệ | Y-05 |
| BR-08 | Dự báo dùng đúng 19 đặc trưng Telco; không dùng `customerID`, `Churn`, dữ liệu CRM mô phỏng | D-04 |
| BR-09 | Tương tác và ticket mô phỏng có `IsSimulated = 1`, không dùng để huấn luyện hay đánh giá mô hình Mức 1 | L3, L4 |
| BR-10 | Đăng nhập sai báo một câu chung; tạm khóa khi cùng tên đăng nhập sai N lần trong M phút. Mặc định N = 5, M = 15 (ĐỀ XUẤT) | Z-12, D-25 |
| BR-11 | Nhập CSV theo mẫu cố định; CustomerID trùng hoặc dòng thiếu dữ liệu bị từ chối riêng từng dòng; báo X dòng thành công, Y dòng thất bại | Z-03 |
| BR-12 | `CustomerStatus` (trạng thái CRM) khác `ChurnLabel` (nhãn dữ liệu mẫu); không dùng cái này thay cái kia | D-22, R-12 |
| BR-13 | Điểm dự báo chỉ hỗ trợ nhân viên chăm sóc, không tự động hóa quyết định bất lợi cho khách hàng | R-07 |
| BR-14 | Khách thêm mới qua Web hoặc CSV chưa có `CustomerSnapshots`, tức chưa có `tenure` và `TotalCharges`, nên **không dự báo từ CSDL được**; khách đó chỉ dự báo qua nhập thủ công (ĐỀ XUẤT, chờ Phúc chốt) | Phát hiện khi viết 02 |
| BR-15 | Giá trị dịch vụ phải nhất quán như dữ liệu Telco: `PhoneService` = No thì `MultipleLines` = "No phone service"; `InternetService` = No thì 6 cột dịch vụ internet (`OnlineSecurity` đến `StreamingMovies`) = "No internet service"; ngược lại thì không được dùng hai giá trị đó (ĐỀ XUẤT; FastAPI chưa kiểm, web kiểm trước khi lưu hoặc gọi API) | Phát hiện khi viết UC-08 (ghi ở D3: chưa kiểm tính nhất quán giữa các cột) |

## 5. Use case (UC)

"Chính" = đặc tả đầy đủ (cô yêu cầu 6 use case, Z-01). "Phụ" = extend hoặc include của use case chính, đặc tả ngắn.

| ID | Tên | Loại | Actor chính | Actor phụ | FR | Quan hệ |
|---|---|---|---|---|---|---|
| UC-01 | Đăng nhập | Chính | ACT-03 (cả ACT-01, ACT-02 kế thừa) | — | FR-01 đến FR-05 | |
| UC-02 | Quản lý khách hàng | Chính | ACT-03 (xem), ACT-02, ACT-01 | — | FR-09 đến FR-13 | include UC-14; extend bởi UC-07, UC-08 |
| UC-03 | Quản lý tương tác | Chính | ACT-03 | — | FR-16 đến FR-20 | include UC-14 |
| UC-04 | Xử lý ticket | Chính | ACT-03 | — | FR-21 đến FR-24, FR-26, FR-27 | include UC-14; extend bởi UC-09 |
| UC-05 | Dự báo churn | Chính | ACT-03 | ACT-04 | FR-28 đến FR-31 | include UC-14 (ghi `ChurnPredictions`) |
| UC-06 | Xem dashboard | Chính | ACT-02 (ACT-01) | — | FR-34 đến FR-40 | |
| UC-07 | Nhập khách hàng từ CSV | Phụ | ACT-02 | — | FR-15 | extend UC-02 |
| UC-08 | Đổi hợp đồng và dịch vụ | Phụ | ACT-02 | — | FR-14 | extend UC-02 |
| UC-09 | Mở lại ticket | Phụ | ACT-02 | — | FR-25 | extend UC-04 |
| UC-10 | Cấu hình ngưỡng rủi ro | Phụ | ACT-02 | — | FR-32 | include UC-14 |
| UC-11 | Xem nhật ký thao tác | Phụ | ACT-01 | — | FR-07 | |
| UC-12 | Quản lý người dùng và vai trò | Phụ (Could) | ACT-01 | — | FR-08 | include UC-14 |
| UC-13 | Xem phiên bản mô hình | Phụ (Could) | ACT-02 | — | FR-33 | |
| UC-14 | Ghi nhật ký thao tác (tự động) | Phụ (được include) | — | — | FR-06 | Do UC-02, 03, 04, 05, 08, 09, 10, 12 include |

## 6. Thực thể (ENT) — khớp ERD 12 bảng nghiệp vụ

`TelcoRaw` là bảng staging, nằm ngoài ERD nên không có ENT. `LoginAttempts` là bảng mới theo D-25, chưa vào PDM.

| ID | Bảng | Ghi chú |
|---|---|---|
| ENT-01 | Customers | Hồ sơ khách (7.043 dòng từ Telco) |
| ENT-02 | CustomerSnapshots | Ảnh chụp benchmark IBM, không sửa |
| ENT-03 | CustomerContracts | Hợp đồng và dịch vụ nghiệp vụ, có lịch sử hiệu lực |
| ENT-04 | Interactions | Lịch sử tương tác |
| ENT-05 | Tickets | Yêu cầu hỗ trợ |
| ENT-06 | Staff | Nhân viên, kiêm tài khoản đăng nhập |
| ENT-07 | Role | Vai trò |
| ENT-08 | AuditLog | Nhật ký thao tác tự động |
| ENT-09 | LoginAttempts | Nhật ký đăng nhập (mới, D-25) |
| ENT-10 | ModelVersions | Phiên bản mô hình |
| ENT-11 | ChurnPredictions | Kết quả dự báo |
| ENT-12 | RiskConfig | Ngưỡng rủi ro và cấu hình |

## 7. Giả định đang dùng (sẽ ghi vào bài)

1. Quan hệ kế thừa Admin ⊃ Manager ⊃ Agent đúng với ma trận quyền hiện tại (Mục 7.2 kế hoạch).
2. Các con số NFR-05 đến NFR-07, NFR-15 là giả định của đồ án, không phải yêu cầu của cô.
3. N = 5 lần và M = 15 phút ở BR-10 là mặc định chờ Phúc chốt (D-25).
4. FR-26 (xóa ticket) để Should vì cô không nhắc việc xóa ticket; BFD vẫn có nút 1.4.6.
5. "Ngừng theo dõi" khách (xóa mềm) coi là thao tác sửa (Update) nên Manager làm được; không có xóa cứng khách hàng. Ma trận quyền ở Mục 7.2 kế hoạch ghi Manager "CRU" cho nhóm này nên tao hiểu vậy.
6. Agent được đóng ticket (đóng là cập nhật); chỉ mở lại và xóa là quyền cao hơn.
7. Ticket phải đi tuần tự Open → InProgress → Closed, không đóng thẳng từ Open (BR-01 hiểu chặt).
8. File CSV mẫu cố định gồm 18 cột: 5 cột hồ sơ khách (CustomerID, Gender, SeniorCitizen, Partner, Dependents) và 13 cột dịch vụ, hợp đồng, thanh toán, `MonthlyCharges`; mỗi dòng hợp lệ tạo một dòng `Customers` và một dòng `CustomerContracts` (EffectiveFrom = ngày nhập), không tạo snapshot.
