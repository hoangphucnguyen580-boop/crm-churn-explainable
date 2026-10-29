# Ma trận truy vết FR → UC → TC

Cột TC để trống: test case viết ở P7 (`08-kiem-thu.md`), sau khi Web xong. Ma trận này cập nhật mỗi lượt.

| FR | Ưu tiên | UC | BFD | TC |
|---|---|---|---|---|
| FR-01 | Must | UC-01 | 1.1.1 | chờ P7 |
| FR-02 | Must | UC-01 | 1.1.1 | chờ P7 |
| FR-03 | Must | UC-01 (áp cho mọi UC) | 1.1.3 | chờ P7 |
| FR-04 | Must | UC-01 | 1.1.6 | chờ P7 |
| FR-05 | Should | UC-01 | 1.1.7 | chờ P7 |
| FR-06 | Must | UC-14 | 1.1.4 | chờ P7 |
| FR-07 | Must | UC-11 | 1.1.5 | chờ P7 |
| FR-08 | Could | UC-12 | 1.1.2 | chờ P7 |
| FR-09 | Must | UC-02 | 1.2.1 | chờ P7 |
| FR-10 | Must | UC-02 | 1.2.2 | chờ P7 |
| FR-11 | Must | UC-02 | 1.2.3 | chờ P7 |
| FR-12 | Must | UC-02 | 1.2.4 | chờ P7 |
| FR-13 | Must | UC-02 | 1.2.6 | chờ P7 |
| FR-14 | Must | UC-08 | 1.2.5 | chờ P7 |
| FR-15 | Must | UC-07 | 1.2.7 | chờ P7 |
| FR-16 | Must | UC-03 | 1.3.1 | chờ P7 |
| FR-17 | Must | UC-03 | 1.3.2 | chờ P7 |
| FR-18 | Must | UC-03 | 1.3.3 | chờ P7 |
| FR-19 | Must | UC-03 | 1.3.4 | chờ P7 |
| FR-20 | Must | UC-03, UC-04, UC-06 | — | chờ P7 |
| FR-21 | Must | UC-04 | 1.4.2 | chờ P7 |
| FR-22 | Must | UC-04 | 1.4.3 | chờ P7 |
| FR-23 | Must | UC-04 | 1.4.4 | chờ P7 |
| FR-24 | Must | UC-04 | 1.4.5 | chờ P7 |
| FR-25 | Must | UC-09 | 1.4.1 | chờ P7 |
| FR-26 | Should | UC-04 | 1.4.6 | chờ P7 |
| FR-27 | Must | UC-04, UC-06 | 1.4.5, 1.6.8 | chờ P7 |
| FR-28 | Must | UC-05 | 1.5.4.1 | chờ P7 |
| FR-29 | Must | UC-05 | 1.5.4.1 | chờ P7 |
| FR-30 | Must | UC-05 | 1.5.4.2 | chờ P7 |
| FR-31 | Must | UC-05 | 1.5.4.1 | chờ P7 |
| FR-32 | Must | UC-10 | 1.5.4.3 | chờ P7 |
| FR-33 | Could | UC-13 | 1.5.4.4 | chờ P7 |
| FR-34 | Must | UC-06 | 1.6.1 | chờ P7 |
| FR-35 | Must | UC-06 | 1.6.2, 1.6.3 | chờ P7 |
| FR-36 | Must | UC-06 | 1.6.4, 1.6.5 | chờ P7 |
| FR-37 | Must | UC-06 | 1.6.6 | chờ P7 |
| FR-38 | Must | UC-06 | 1.6.7 | chờ P7 |
| FR-39 | Must | UC-06 | 1.6.8 | chờ P7 |
| FR-40 | Should | UC-06 | 1.6.9 | chờ P7 |

## Theo use case

| UC | Tên | Loại | FR | Đặc tả | TC |
|---|---|---|---|---|---|
| UC-01 | Đăng nhập | Chính | FR-01 đến FR-05 | đầy đủ (xong) | chờ P7 |
| UC-02 | Quản lý khách hàng | Chính | FR-09 đến FR-13 | đầy đủ (xong) | chờ P7 |
| UC-03 | Quản lý tương tác | Chính | FR-16 đến FR-20 | đầy đủ (xong) | chờ P7 |
| UC-04 | Xử lý ticket | Chính | FR-21 đến FR-24, FR-26, FR-27 | đầy đủ (xong) | chờ P7 |
| UC-05 | Dự báo churn | Chính | FR-28 đến FR-31 | đầy đủ (xong) | chờ P7 |
| UC-06 | Xem dashboard | Chính | FR-34 đến FR-40 | đầy đủ (xong) | chờ P7 |
| UC-07 | Nhập khách hàng từ CSV | Phụ | FR-15 | ngắn (xong) | chờ P7 |
| UC-08 | Đổi hợp đồng và dịch vụ | Phụ | FR-14 | đầy đủ (xong) | chờ P7 |
| UC-09 | Mở lại ticket | Phụ | FR-25 | đầy đủ (xong) | chờ P7 |
| UC-10 | Cấu hình ngưỡng rủi ro | Phụ | FR-32 | ngắn (xong) | chờ P7 |
| UC-11 | Xem nhật ký thao tác | Phụ | FR-07 | ngắn (xong) | chờ P7 |
| UC-12 | Quản lý người dùng và vai trò | Phụ (Could) | FR-08 | ngắn (xong) | chờ P7 |
| UC-13 | Xem phiên bản mô hình | Phụ (Could) | FR-33 | ngắn (xong) | chờ P7 |
| UC-14 | Ghi nhật ký thao tác (tự động) | Phụ (được include) | FR-06 | ngắn (xong) | chờ P7 |
