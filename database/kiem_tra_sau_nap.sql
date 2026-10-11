/*==============================================================*/
/* XEM KẾT QUẢ SAU KHI NẠP TELCO (chỉ đọc, không sửa gì)        */
/* Cách chạy: mở trong SSMS, ô database chọn CRM_Churn, F5.     */
/* Kết quả: 4 lưới xếp dọc (kéo thanh cuộn của khung Results).  */
/*==============================================================*/
USE CRM_Churn;
GO

-- Lưới 1: số dòng từng bảng đã có dữ liệu (kỳ vọng 7043 / 7043 / 7043)
SELECT N'TelcoRaw' AS Bang, COUNT(*) AS SoDong FROM TelcoRaw
UNION ALL SELECT N'Customers',         COUNT(*) FROM Customers
UNION ALL SELECT N'CustomerSnapshots', COUNT(*) FROM CustomerSnapshots;

-- Lưới 2: nhãn Churn (kỳ vọng Yes 1869, No 5174, TotalCharges NULL = 11)
SELECT ChurnLabel,
       COUNT(*) AS SoKhach,
       SUM(CASE WHEN TotalCharges IS NULL THEN 1 ELSE 0 END) AS TotalChargesNull
FROM CustomerSnapshots
GROUP BY ChurnLabel;

-- Lưới 3: xem thử 5 khách đầu (EstimatedJoinDate là ngày ước lượng, không phải ngày thật)
SELECT TOP 5 CustomerID, Gender, SeniorCitizen, Partner, Dependents,
       EstimatedJoinDate, CustomerStatus, CreatedAt
FROM Customers
ORDER BY CustomerID;

-- Lưới 4: TelcoRaw giữ nguyên văn; 11 ô TotalCharges là MỘT DẤU CÁCH.
-- Kỳ vọng: Dai_KhongTinhDauCachCuoi = 0 (LEN bỏ qua dấu cách cuối), Dai_TinhCaDauCach = 1
SELECT TOP 3 customerID, tenure, TotalCharges, LEN(TotalCharges) AS Dai_KhongTinhDauCachCuoi,
       DATALENGTH(TotalCharges) AS Dai_TinhCaDauCach
FROM TelcoRaw
WHERE LTRIM(RTRIM(TotalCharges)) = '';
GO
