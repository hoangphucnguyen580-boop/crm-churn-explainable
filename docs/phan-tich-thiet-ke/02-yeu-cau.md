# 02 — Yêu cầu hệ thống (Chương 2, mục 2.1)

Nguồn ID: `00-id-registry.md`. Tiêu chí nghiệm thu viết dạng Cho / Khi / Thì để suy ra test case ở P7. Chỗ ghi ĐỀ XUẤT chờ Phúc chốt.

## 2.1.1 Yêu cầu chức năng

| ID | Yêu cầu (hệ thống phải…) | Ưu tiên | UC | Tiêu chí nghiệm thu |
|---|---|---|---|---|
| FR-01 | cho phép nhân viên đăng nhập bằng tài khoản Staff; sai tên hoặc sai mật khẩu đều báo cùng một câu | Must | UC-01 | Cho tài khoản Staff đang hoạt động. Khi nhập đúng tên và mật khẩu thì vào trang chính. Khi sai tên hoặc sai mật khẩu thì báo cùng một câu "Tên đăng nhập hoặc mật khẩu không đúng" và không tạo phiên. |
| FR-02 | cho phép đăng xuất và ghi nhận việc đăng xuất | Must | UC-01 | Cho nhân viên đã đăng nhập. Khi bấm Đăng xuất thì phiên bị xóa, vào lại trang cần đăng nhập thì bị đẩy về Login, và `AuditLog` có dòng `Logout`. |
| FR-03 | kiểm quyền theo vai trò ở từng Action; vai trò không đủ quyền thấy trang "Không có quyền" | Must | UC-01 (áp cho mọi UC) | Cho Agent. Khi gõ trực tiếp URL chỉ dành cho Manager hoặc Admin (ví dụ cấu hình ngưỡng) thì thấy trang "Không có quyền", không có dữ liệu nào bị đổi. Tương tự Manager với trang chỉ Admin. |
| FR-04 | ghi mọi lần đăng nhập (thành công và thất bại) vào `LoginAttempts`, không lưu mật khẩu | Must | UC-01 | Cho một lần đăng nhập bất kỳ. Khi kết thúc thì có đúng một dòng `LoginAttempts` ghi tên thử, thời điểm, `IsSuccess`, `FailReason`; không cột nào chứa mật khẩu. |
| FR-05 | tạm khóa đăng nhập khi cùng tên đăng nhập sai liên tiếp quá ngưỡng cấu hình | Should | UC-01 | Cho một tên đăng nhập đã sai N lần liên tiếp trong M phút. Khi thử tiếp (kể cả mật khẩu đúng) thì bị từ chối với cùng câu thông báo chung và ghi `Locked`; sau M phút thử lại được. |
| FR-06 | ghi `AuditLog` tự động khi thêm, sửa, xóa dữ liệu quan trọng, che `PasswordHash` | Must | UC-14 | Cho nhân viên thêm, sửa hoặc xóa một dòng ở bảng thuộc phạm vi audit. Khi lưu thành công thì có dòng `AuditLog` đúng `StaffID`, `Action`, `TableName`, `RecordKey`, giá trị cũ và mới; `PasswordHash` chỉ hiện `***`. Khi lưu thất bại thì không có dòng audit. |
| FR-07 | cho Admin xem và lọc `AuditLog` theo người, bảng, ngày | Must | UC-11 | Cho Admin. Khi lọc theo người, bảng, ngày thì chỉ các dòng khớp hiện ra. Manager và Agent gõ URL này bị chặn. |
| FR-08 | cho Admin quản lý tài khoản nhân viên và vai trò | Could | UC-12 | Cho Admin. Khi tạo tài khoản kèm vai trò thì `PasswordHash` là chuỗi băm; tài khoản `IsActive = 0` không đăng nhập được. |
| FR-09 | hiển thị danh sách khách có phân trang, tìm theo CustomerID, lọc theo hợp đồng, nhóm tenure, mức rủi ro | Must | UC-02 | Cho 7.043 khách. Khi mở danh sách thì dữ liệu chia trang; nhập một CustomerID thì ra đúng khách đó; lọc hợp đồng Month-to-month thì mọi dòng đều đúng hợp đồng đó. |
| FR-10 | hiển thị chi tiết khách: hồ sơ, hợp đồng và dịch vụ đang hiệu lực, lịch sử tương tác, ticket, dự báo gần nhất | Must | UC-02 | Cho một khách có dữ liệu. Khi mở chi tiết thì thấy hồ sơ, dòng hợp đồng đang hiệu lực (`EffectiveTo` rỗng), tương tác, ticket và dự báo gần nhất; chưa có dự báo thì hiện "chưa có dự báo". |
| FR-11 | cho Manager và Admin thêm hồ sơ khách mới | Must | UC-02 | Cho Manager. Khi nhập CustomerID chưa tồn tại với dữ liệu hợp lệ thì có khách mới với `CustomerStatus` mặc định `Active`; CustomerID trùng thì báo lỗi; Agent bị chặn. |
| FR-12 | cho Manager và Admin sửa hồ sơ khách | Must | UC-02 | Cho Manager. Khi sửa hồ sơ thì dữ liệu đổi và `AuditLog` ghi trước và sau; CustomerID không sửa được. |
| FR-13 | cho Manager và Admin ngừng theo dõi khách (xóa mềm, đổi `CustomerStatus`) | Must | UC-02 | Cho Manager. Khi ngừng theo dõi một khách thì `CustomerStatus` đổi sang trạng thái ngừng, khách và lịch sử vẫn còn trong CSDL, có dòng audit. |
| FR-14 | cho Manager và Admin đổi hợp đồng và dịch vụ bằng cách đóng dòng đang hiệu lực rồi thêm dòng mới ở `CustomerContracts`, không sửa `CustomerSnapshots` | Must | UC-08 | Cho khách có hợp đồng đang hiệu lực. Khi Manager đổi hợp đồng thì dòng cũ có `EffectiveTo`, dòng mới có `EffectiveTo` rỗng, khách vẫn có đúng một dòng đang hiệu lực; `CustomerSnapshots` và `TelcoRaw` không đổi; ngày hiệu lực mới không lớn hơn ngày bắt đầu của dòng cũ thì bị từ chối. |
| FR-15 | cho Manager và Admin nhập khách từ CSV theo mẫu cố định, kiểm trùng CustomerID và dữ liệu thiếu, báo số dòng thành công và thất bại | Must | UC-07 | Cho file CSV đúng mẫu có 10 dòng, trong đó 1 dòng trùng CustomerID và 1 dòng thiếu cột bắt buộc. Khi nhập thì 8 dòng vào CSDL, 2 dòng bị từ chối kèm lý do, và màn hình báo "8 thành công, 2 thất bại". |
| FR-16 | cho nhân viên ghi nhận tương tác (kênh, loại, mô tả, kết quả, người phụ trách) | Must | UC-03 | Cho nhân viên. Khi chọn khách, kênh, loại và lưu thì có dòng `Interactions` với `StaffID` là người đang đăng nhập, `IsSimulated = 0`, có audit; kênh hoặc loại ngoài danh sách bị chặn. |
| FR-17 | cho xem và lọc lịch sử tương tác theo khách, loại, kênh, khoảng thời gian | Must | UC-03 | Cho khách có nhiều tương tác. Khi lọc loại Complaint và một khoảng thời gian thì chỉ hiện dòng thỏa cả hai điều kiện, sắp theo thời gian giảm dần. |
| FR-18 | cho Manager và Admin sửa tương tác | Must | UC-03 | Cho Manager. Khi sửa tương tác thì dữ liệu đổi và audit có trước và sau; Agent gọi thao tác sửa bị chặn. |
| FR-19 | cho Admin xóa tương tác | Must | UC-03 | Cho Admin. Khi xóa tương tác thì dòng bị xóa và audit lưu giá trị cũ; Manager và Agent gõ URL xóa bị chặn. |
| FR-20 | gắn nhãn "dữ liệu mô phỏng" trên tương tác và ticket có `IsSimulated = 1` | Must | UC-03, UC-04, UC-06 | Cho tương tác hoặc ticket có `IsSimulated = 1`. Khi hiển thị ở danh sách, chi tiết, dashboard thì có nhãn "dữ liệu mô phỏng"; dòng nhập tay thì không có nhãn. |
| FR-21 | cho nhân viên mở ticket mới (trạng thái Open) | Must | UC-04 | Cho nhân viên. Khi tạo ticket (khách, loại, ưu tiên) thì `Status = Open`, `CreatedAt` là giờ hiện tại, `ClosedAt` rỗng; loại hoặc ưu tiên ngoài danh sách bị chặn. |
| FR-22 | cho xem danh sách ticket và lọc theo trạng thái, mức ưu tiên, nhân viên phụ trách, khách | Must | UC-04 | Cho nhiều ticket. Khi lọc kết hợp trạng thái, ưu tiên, nhân viên, khách thì chỉ hiện ticket thỏa mọi điều kiện. |
| FR-23 | cho phân công nhân viên, đổi mức ưu tiên, chuyển trạng thái Open sang InProgress | Must | UC-04 | Cho ticket Open. Khi phân công và chuyển sang InProgress thì `Status = InProgress` và `AssignedStaffID` đúng; chuyển thẳng Open sang Closed bị từ chối. |
| FR-24 | khi đóng ticket bắt buộc có kết quả giải quyết, lưu `ClosedAt`, cho ghi mức hài lòng 1 đến 5 | Must | UC-04 | Cho ticket InProgress. Khi đóng mà thiếu kết quả giải quyết thì bị từ chối; có kết quả thì `Status = Closed`, `ClosedAt` không sớm hơn `CreatedAt`, điểm hài lòng từ 1 đến 5 hoặc để trống; điểm 0 hoặc 6 bị chặn. |
| FR-25 | cho Manager và Admin mở lại ticket Closed, bắt buộc nhập lý do, ghi lịch sử | Must | UC-09 | Cho ticket Closed. Khi Manager mở lại kèm lý do thì `Status = InProgress`, `ClosedAt` và điểm hài lòng rỗng, `ReopenReason` được lưu, có audit; thiếu lý do thì bị từ chối; Agent mở lại bị chặn. |
| FR-26 | cho Admin xóa ticket | Should | UC-04 | Cho Admin. Khi xóa ticket thì dòng bị xóa và có audit; Manager và Agent bị chặn. |
| FR-27 | tính thời gian xử lý ticket bằng `ClosedAt` trừ `CreatedAt` | Must | UC-04, UC-06 | Cho ticket Closed. Khi hiển thị thì thời gian xử lý bằng `ClosedAt` trừ `CreatedAt`; giá trị trung bình trên dashboard bằng trung bình của các ticket Closed. |
| FR-28 | dự báo cho khách có sẵn: lấy đúng 19 đặc trưng từ CSDL (hợp đồng đang hiệu lực và snapshot), gọi `/predict`, nhận xác suất | Must | UC-05 | Cho khách có snapshot. Khi chọn dự báo thì Web gửi đúng 19 đặc trưng (SeniorCitizen 0 hoặc 1, Partner và Dependents dạng Yes hoặc No) và nhận xác suất; trên 20 khách mẫu, xác suất qua Web trùng gọi trực tiếp `/predict` (chênh dưới 1e-9). Khách không có snapshot thì báo không đủ đặc trưng (BR-14). |
| FR-29 | dự báo từ đặc trưng nhập tay: kiểm dữ liệu trước khi gọi API, lưu với `CustomerID` NULL và `InputJson` | Must | UC-05 | Cho form nhập tay. Khi thiếu đặc trưng hoặc giá trị ngoài danh sách thì bị chặn trước khi gọi API; khi hợp lệ thì có dòng `ChurnPredictions` với `CustomerID` rỗng và `InputJson` là JSON hợp lệ. |
| FR-30 | hiển thị xác suất churn, mức Low/Medium/High theo ngưỡng `RiskConfig`, phiên bản mô hình, ghi chú "chỉ hỗ trợ quyết định" | Must | UC-05 | Cho kết quả dự báo. Khi hiển thị thì có xác suất, mức rủi ro, phiên bản mô hình, ghi chú hỗ trợ quyết định; xác suất đúng bằng ngưỡng Medium thì mức Medium; đổi ngưỡng trong `RiskConfig` thì mức đổi theo mà không sửa mã. |
| FR-31 | lưu kết quả vào `ChurnPredictions`; khi API chưa chạy, quá thời gian, dữ liệu sai hoặc mất SQL Server thì báo lỗi, không báo thành công khi chưa lưu được | Must | UC-05 | Cho FastAPI tắt hoặc quá thời gian. Khi dự báo thì báo dịch vụ chưa sẵn sàng và không có dòng mới. Cho SQL Server mất kết nối lúc lưu thì báo lỗi và không hiện "thành công". |
| FR-32 | cho Manager và Admin xem và sửa ngưỡng Medium, High, kiểm 0 ≤ Medium < High ≤ 1 | Must | UC-10 | Cho Manager. Khi nhập Medium không nhỏ hơn High hoặc ngoài [0, 1] thì bị từ chối; hợp lệ thì `RiskConfig` đổi kèm `UpdatedByStaffID` và audit; Agent bị chặn. |
| FR-33 | cho Manager và Admin xem danh sách phiên bản mô hình, metric, ngưỡng | Could | UC-13 | Cho Manager. Khi mở trang mô hình thì thấy phiên bản, ngày huấn luyện, ngưỡng, metric của `ModelVersions`. |
| FR-34 | dashboard hiển thị tổng khách, phân bố nhãn churn (dữ liệu mẫu), phân bố theo hợp đồng | Must | UC-06 | Cho dữ liệu Telco. Khi mở dashboard thì tổng khách là 7.043, số nhãn Yes cộng No bằng tổng, phân bố hợp đồng cộng bằng tổng, và có nhãn "dữ liệu mẫu IBM". |
| FR-35 | dashboard hiển thị churn theo nhóm tenure và retention proxy, kèm chú thích giới hạn | Must | UC-06 | Cho các nhóm tenure 0–6, 7–12, 13–24, 25–36, 37–48, 49–60, trên 60 tháng. Khi hiển thị thì tỷ lệ churn của nhóm bằng số Yes chia số khách nhóm, retention proxy bằng 1 trừ tỷ lệ churn, và có chú thích đây là ước lượng từ ảnh chụp một thời điểm. |
| FR-36 | dashboard hiển thị mức phí hằng tháng (dữ liệu mẫu) và phân khúc khách | Must | UC-06 | Cho mức phí hằng tháng. Khi hiển thị thì nhãn ghi "mức phí hằng tháng (dữ liệu mẫu)", không có chữ "doanh thu"; các nhóm phân khúc cộng bằng tổng khách. |
| FR-37 | dashboard hiển thị phân bố mức rủi ro và danh sách khách điểm cao, chỉ để xem xét, không gợi ý hành động | Must | UC-06 | Cho khách đã chấm điểm. Khi hiển thị thì Low cộng Medium cộng High bằng số khách đã chấm; danh sách khách điểm cao sắp giảm dần; không có nút hay câu gợi ý hành động. |
| FR-38 | dashboard hiển thị thống kê tương tác theo loại, kênh, thời gian | Must | UC-06 | Cho tương tác. Khi hiển thị thì số theo kênh, theo loại, theo tháng đều cộng bằng tổng; có nhãn dữ liệu mô phỏng. |
| FR-39 | dashboard hiển thị số ticket theo trạng thái, ưu tiên, thời gian xử lý trung bình, mức hài lòng | Must | UC-06 | Cho ticket. Khi hiển thị thì Open cộng InProgress cộng Closed bằng tổng ticket; thời gian xử lý trung bình tính trên ticket Closed. |
| FR-40 | cho lọc số liệu dashboard theo hợp đồng, loại internet, phương thức thanh toán, nhóm tenure | Should | UC-06 | Cho bộ lọc. Khi chọn hợp đồng Two year thì mọi biểu đồ có hỗ trợ lọc chỉ tính nhóm khách đó. |

Tổng: 40 yêu cầu, trong đó Must 35, Should 3, Could 2.

## 2.1.2 Yêu cầu phi chức năng

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

## 2.1.3 Quy tắc nghiệp vụ

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

## 2.1.4 Chỗ cần Phúc chốt (phát hiện khi viết mục này)

1. **BR-14, khách thêm mới không dự báo từ CSDL được.** Bộ 19 đặc trưng cần `tenure` và `TotalCharges`, hai giá trị này chỉ nằm ở `CustomerSnapshots` (dữ liệu benchmark, không sửa, R-14). Khách thêm qua Web hoặc CSV không có snapshot. Đề xuất: khách đó chỉ dự báo qua nhập thủ công (FR-29). Các hướng khác tốn công hơn (thêm cột vào `CustomerContracts`, hoặc tính tenure từ ngày tham gia thật) và đụng thiết kế CSDL mà cô dặn không cần sửa.
2. **Mẫu CSV (FR-15).** Đề xuất 18 cột: 5 cột hồ sơ và 13 cột dịch vụ, hợp đồng, thanh toán, `MonthlyCharges` (giả định số 8 ở `00-id-registry.md`). Mỗi dòng hợp lệ tạo một dòng `Customers` và một dòng `CustomerContracts`.
3. **Quyền ngừng theo dõi và đóng ticket.** Giả định số 5 và 6 ở `00-id-registry.md`.

