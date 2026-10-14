/*==============================================================*/
/* KIỂM TRA DATABASE CRM_Churn (bản P1b, sửa theo email cô 12/10) */
/*   Phần 1: đếm đối tượng (chỉ đọc, không sửa gì)              */
/*   Phần 2: test hành vi trong transaction, ROLLBACK ở cuối    */
/*   Phần 3: so số dòng từng bảng TRƯỚC và SAU rollback         */
/*                                                              */
/* Chạy được cả khi database trống lẫn khi đã nạp Telco:        */
/*   - không còn kỳ vọng "tổng dòng còn lại = 0" (chỉ đúng khi  */
/*     database trống); thay bằng so trước/sau (Y-01).          */
/*   - sau khi nạp Telco: Customers, CustomerSnapshots,         */
/*     TelcoRaw phải giữ nguyên 7043 dòng trước và sau.         */
/*                                                              */
/* Chạy SAU: 01_schema.sql, 02_staging.sql, và                  */
/*           constraints_bo_sung.sql (cho đủ 12 CHECK).         */
/* Cách chạy: mở trong SSMS, bấm Execute (F5) một lần.          */
/* Lưu ý: số tự tăng (identity) vẫn nhích sau ROLLBACK, bình    */
/* thường; code web không được gán cứng RoleID.                 */
/*==============================================================*/
USE CRM_Churn;
GO

/*--------------------------------------------------------------*/
/* PHẦN 1: ĐẾM ĐỐI TƯỢNG (chỉ đọc)                              */
/* Kết quả: 7 dòng, cột KetLuan phải là ĐẠT                     */
/*--------------------------------------------------------------*/
SELECT MucKiemTra, ThucTe, DuKien,
       CASE WHEN ThucTe = DuKien THEN N'ĐẠT' ELSE N'SAI' END AS KetLuan
FROM (
    SELECT 1 AS Stt, N'Bảng nghiệp vụ (không tính TelcoRaw)' AS MucKiemTra,
           (SELECT COUNT(*) FROM sys.tables WHERE name <> 'TelcoRaw') AS ThucTe, 11 AS DuKien
    UNION ALL
    SELECT 2, N'Bảng staging TelcoRaw (1 = đã tạo)',
           (SELECT COUNT(*) FROM sys.tables WHERE name = 'TelcoRaw'), 1
    UNION ALL
    SELECT 3, N'Khóa ngoại',  (SELECT COUNT(*) FROM sys.foreign_keys), 12
    UNION ALL
    SELECT 4, N'Default',     (SELECT COUNT(*) FROM sys.default_constraints), 7
    UNION ALL
    SELECT 5, N'Unique',      (SELECT COUNT(*) FROM sys.key_constraints WHERE type = 'UQ'), 4
    UNION ALL
    SELECT 6, N'Check (6 từ schema.sql + 6 từ constraints_bo_sung.sql)',
           (SELECT COUNT(*) FROM sys.check_constraints), 12
    UNION ALL
    SELECT 7, N'Primary key', (SELECT COUNT(*) FROM sys.key_constraints WHERE type = 'PK'), 11
) AS Dem
ORDER BY Stt;
GO

/*--------------------------------------------------------------*/
/* PHẦN 2 + 3: TEST HÀNH VI VÀ SO SỐ DÒNG TRƯỚC/SAU ROLLBACK     */
/* Mỗi test nằm trong TRY...CATCH:                              */
/*   - thêm thành công  -> ThucTe = OK                          */
/*   - bị chặn           -> ThucTe = Lỗi <mã lỗi>               */
/* Mã lỗi: 515 = NULL vào cột not null, 2627 = trùng unique,    */
/*         547 = vi phạm khóa ngoại hoặc CHECK                  */
/*--------------------------------------------------------------*/
SET NOCOUNT ON;
SET XACT_ABORT OFF;

-- Biến kiểu bảng KHÔNG bị ROLLBACK xóa, nên dùng để giữ kết quả test
DECLARE @KetQua TABLE (
    Stt     int,
    TenTest nvarchar(100),
    DuKien  nvarchar(60),
    ThucTe  nvarchar(60)
);
DECLARE @Truoc TABLE (TenBang nvarchar(30), SoDong int);
DECLARE @Sau   TABLE (TenBang nvarchar(30), SoDong int);

DECLARE @RoleID         int;
DECLARE @StaffID        int;
DECLARE @ModelVersionID int;
DECLARE @Text           nvarchar(60);
DECLARE @Time           datetime;
DECLARE @SoDong         int;
DECLARE @TelcoRaw       int;

/*-- Đếm số dòng TRƯỚC khi thử (TelcoRaw đếm bằng SQL động, vì có thể chưa tạo) --*/
SET @TelcoRaw = 0;
IF OBJECT_ID(N'dbo.TelcoRaw', N'U') IS NOT NULL
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.TelcoRaw', N'@n int OUTPUT', @n = @TelcoRaw OUTPUT;

INSERT INTO @Truoc (TenBang, SoDong)
SELECT N'AuditLog', COUNT(*) FROM AuditLog
UNION ALL SELECT N'ChurnPredictions',  COUNT(*) FROM ChurnPredictions
UNION ALL SELECT N'CustomerContracts', COUNT(*) FROM CustomerContracts
UNION ALL SELECT N'CustomerSnapshots', COUNT(*) FROM CustomerSnapshots
UNION ALL SELECT N'Customers',         COUNT(*) FROM Customers
UNION ALL SELECT N'Interactions',      COUNT(*) FROM Interactions
UNION ALL SELECT N'ModelVersions',     COUNT(*) FROM ModelVersions
UNION ALL SELECT N'RiskConfig',        COUNT(*) FROM RiskConfig
UNION ALL SELECT N'Role',              COUNT(*) FROM Role
UNION ALL SELECT N'Staff',             COUNT(*) FROM Staff
UNION ALL SELECT N'Tickets',           COUNT(*) FROM Tickets
UNION ALL SELECT N'TelcoRaw',          @TelcoRaw;

BEGIN TRANSACTION;

-- Test 1: Role thêm hợp lệ (RoleID tự sinh bằng identity)
BEGIN TRY
    INSERT INTO Role (RoleName) VALUES ('ZZ_Test');
    SELECT @RoleID = RoleID FROM Role WHERE RoleName = 'ZZ_Test';
    INSERT INTO @KetQua VALUES (1, N'Role: thêm hợp lệ', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (1, N'Role: thêm hợp lệ', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 2: Role trùng RoleName phải bị chặn (unique)
BEGIN TRY
    INSERT INTO Role (RoleName) VALUES ('ZZ_Test');
    INSERT INTO @KetQua VALUES (2, N'Role: trùng RoleName', N'Lỗi 2627', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (2, N'Role: trùng RoleName', N'Lỗi 2627', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 3: Staff thêm hợp lệ
BEGIN TRY
    INSERT INTO Staff (RoleID, FullName, Username, PasswordHash, IsActive)
    VALUES (@RoleID, N'Nhân viên thử', 'zz_user', 'hash_gia', 1);
    SELECT @StaffID = StaffID FROM Staff WHERE Username = 'zz_user';
    INSERT INTO @KetQua VALUES (3, N'Staff: thêm hợp lệ', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (3, N'Staff: thêm hợp lệ', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 4: Staff thiếu PasswordHash phải bị chặn (not null)
BEGIN TRY
    INSERT INTO Staff (RoleID, FullName, Username, PasswordHash, IsActive)
    VALUES (@RoleID, N'Nhân viên thiếu mật khẩu', 'zz_user2', NULL, 1);
    INSERT INTO @KetQua VALUES (4, N'Staff: PasswordHash NULL', N'Lỗi 515', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (4, N'Staff: PasswordHash NULL', N'Lỗi 515', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 5: Staff trùng Username phải bị chặn (unique)
BEGIN TRY
    INSERT INTO Staff (RoleID, FullName, Username, PasswordHash, IsActive)
    VALUES (@RoleID, N'Nhân viên trùng tên đăng nhập', 'zz_user', 'hash_gia_2', 1);
    INSERT INTO @KetQua VALUES (5, N'Staff: trùng Username', N'Lỗi 2627', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (5, N'Staff: trùng Username', N'Lỗi 2627', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 6 và 7: Customers chỉ điền cột bắt buộc -> hai default phải tự điền
BEGIN TRY
    INSERT INTO Customers (CustomerID, SeniorCitizen) VALUES ('ZZ-0001', 0);
    SELECT @Text = CustomerStatus, @Time = CreatedAt FROM Customers WHERE CustomerID = 'ZZ-0001';
    INSERT INTO @KetQua VALUES (6, N'Customers.CustomerStatus tự điền', N'Active', @Text);
    INSERT INTO @KetQua VALUES (7, N'Customers.CreatedAt tự điền giờ',  N'Giờ hiện tại',
        CASE WHEN ABS(DATEDIFF(SECOND, @Time, GETDATE())) <= 60 THEN N'Giờ hiện tại' ELSE N'Sai giờ' END);
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (6, N'Customers: thêm chỉ với cột bắt buộc', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 8: Interactions không điền IsSimulated -> phải ra 0
BEGIN TRY
    INSERT INTO Interactions (CustomerID, InteractionDate, Channel, InteractionType)
    VALUES ('ZZ-0001', GETDATE(), 'Phone', 'Inquiry');
    SELECT @Text = CAST(IsSimulated AS nvarchar(5)) FROM Interactions WHERE CustomerID = 'ZZ-0001';
    INSERT INTO @KetQua VALUES (8, N'Interactions.IsSimulated tự điền', N'0', @Text);
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (8, N'Interactions.IsSimulated tự điền', N'0', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 9: Interactions cho khách không tồn tại phải bị chặn (khóa ngoại)
BEGIN TRY
    INSERT INTO Interactions (CustomerID, InteractionDate, Channel, InteractionType)
    VALUES ('KHONG-CO', GETDATE(), 'Phone', 'Inquiry');
    INSERT INTO @KetQua VALUES (9, N'Interactions: khách không tồn tại', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (9, N'Interactions: khách không tồn tại', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 10: Tickets Open, không điền SatisfactionScore (NULL) và IsSimulated -> IsSimulated phải ra 0
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status)
    VALUES ('ZZ-0001', GETDATE(), 'Billing', 'Low', 'Open');
    SELECT @Text = CAST(IsSimulated AS nvarchar(5)) FROM Tickets WHERE CustomerID = 'ZZ-0001';
    INSERT INTO @KetQua VALUES (10, N'Tickets: điểm NULL + IsSimulated tự điền', N'0', @Text);
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (10, N'Tickets: điểm NULL + IsSimulated tự điền', N'0', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 11: Tickets điểm 6 phải bị chặn (CHECK 1 đến 5). Ticket Closed hợp lệ về thời gian để chỉ còn điểm là lỗi.
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, ClosedAt, Category, Priority, Status, SatisfactionScore)
    VALUES ('ZZ-0001', DATEADD(HOUR, -2, GETDATE()), GETDATE(), 'Billing', 'Low', 'Closed', 6);
    INSERT INTO @KetQua VALUES (11, N'Tickets: điểm 6', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (11, N'Tickets: điểm 6', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 12: Tickets điểm 0 phải bị chặn (CHECK 1 đến 5)
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, ClosedAt, Category, Priority, Status, SatisfactionScore)
    VALUES ('ZZ-0001', DATEADD(HOUR, -2, GETDATE()), GETDATE(), 'Billing', 'Low', 'Closed', 0);
    INSERT INTO @KetQua VALUES (12, N'Tickets: điểm 0', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (12, N'Tickets: điểm 0', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 13: Tickets điểm 5 (ticket Closed hợp lệ) phải được chấp nhận
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, ClosedAt, Category, Priority, Status, SatisfactionScore)
    VALUES ('ZZ-0001', DATEADD(HOUR, -2, GETDATE()), GETDATE(), 'Billing', 'Low', 'Closed', 5);
    INSERT INTO @KetQua VALUES (13, N'Tickets: điểm 5', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (13, N'Tickets: điểm 5', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 14 và 15: ChurnPredictions với CustomerID NULL (dự báo nhập tay) KÈM InputJson hợp lệ + PredictionTime tự điền
-- (từ Y-05, dự báo nhập tay thiếu InputJson bị chặn; xem test 35 và 36)
BEGIN TRY
    INSERT INTO ModelVersions (ModelName, Version, TrainDate, Threshold)
    VALUES ('ZZ_Model', 'v0', GETDATE(), 0.5);
    SELECT @ModelVersionID = ModelVersionID FROM ModelVersions WHERE ModelName = 'ZZ_Model';

    INSERT INTO ChurnPredictions (ModelVersionID, CustomerID, Probability, RiskLevel, InputJson)
    VALUES (@ModelVersionID, NULL, 0.5, 'Medium', N'{"tenure": 5, "Contract": "Month-to-month"}');
    SELECT @Time = PredictionTime FROM ChurnPredictions WHERE ModelVersionID = @ModelVersionID;

    INSERT INTO @KetQua VALUES (14, N'ChurnPredictions: CustomerID NULL kèm InputJson', N'OK', N'OK');
    INSERT INTO @KetQua VALUES (15, N'ChurnPredictions.PredictionTime tự điền giờ', N'Giờ hiện tại',
        CASE WHEN ABS(DATEDIFF(SECOND, @Time, GETDATE())) <= 60 THEN N'Giờ hiện tại' ELSE N'Sai giờ' END);
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (14, N'ChurnPredictions: CustomerID NULL kèm InputJson', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 16: RiskConfig.UpdatedAt tự điền giờ
BEGIN TRY
    INSERT INTO RiskConfig (ConfigKey, ConfigValue) VALUES ('ZZ_Key', '0.5');
    SELECT @Time = UpdatedAt FROM RiskConfig WHERE ConfigKey = 'ZZ_Key';
    INSERT INTO @KetQua VALUES (16, N'RiskConfig.UpdatedAt tự điền giờ', N'Giờ hiện tại',
        CASE WHEN ABS(DATEDIFF(SECOND, @Time, GETDATE())) <= 60 THEN N'Giờ hiện tại' ELSE N'Sai giờ' END);
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (16, N'RiskConfig.UpdatedAt tự điền giờ', N'Giờ hiện tại', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 17: AuditLog.OccurredAt tự điền giờ
BEGIN TRY
    INSERT INTO AuditLog (StaffID, Action, TableName, RecordKey)
    VALUES (@StaffID, 'Insert', 'Customers', 'ZZ-0001');
    SELECT @Time = OccurredAt FROM AuditLog WHERE RecordKey = 'ZZ-0001';
    INSERT INTO @KetQua VALUES (17, N'AuditLog.OccurredAt tự điền giờ', N'Giờ hiện tại',
        CASE WHEN ABS(DATEDIFF(SECOND, @Time, GETDATE())) <= 60 THEN N'Giờ hiện tại' ELSE N'Sai giờ' END);
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (17, N'AuditLog.OccurredAt tự điền giờ', N'Giờ hiện tại', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

/*==============================================================*/
/* TEST MỚI (Y-02 đến Y-05, D-18, D-19)                         */
/*==============================================================*/

-- Test 18: CustomerSnapshots thêm hợp lệ
BEGIN TRY
    INSERT INTO CustomerSnapshots
        (CustomerID, SnapshotDate, Tenure, PhoneService, MultipleLines, InternetService,
         OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies,
         Contract, PaperlessBilling, PaymentMethod, MonthlyCharges)
    VALUES ('ZZ-0001', '20260930', 5, 'Yes', 'No', 'DSL',
            'No', 'No', 'No', 'No', 'No', 'No',
            'Month-to-month', 'Yes', 'Mailed check', 29.85);
    INSERT INTO @KetQua VALUES (18, N'CustomerSnapshots: thêm hợp lệ', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (18, N'CustomerSnapshots: thêm hợp lệ', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 19 (Y-02): cùng khách, cùng SnapshotDate phải bị chặn (unique)
BEGIN TRY
    INSERT INTO CustomerSnapshots
        (CustomerID, SnapshotDate, Tenure, PhoneService, MultipleLines, InternetService,
         OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies,
         Contract, PaperlessBilling, PaymentMethod, MonthlyCharges)
    VALUES ('ZZ-0001', '20260930', 6, 'Yes', 'No', 'DSL',
            'No', 'No', 'No', 'No', 'No', 'No',
            'Month-to-month', 'Yes', 'Mailed check', 30.00);
    INSERT INTO @KetQua VALUES (19, N'CustomerSnapshots: trùng khách + SnapshotDate', N'Lỗi 2627', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (19, N'CustomerSnapshots: trùng khách + SnapshotDate', N'Lỗi 2627', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 20 (Y-03a): Probability 1,5 phải bị chặn
BEGIN TRY
    INSERT INTO ChurnPredictions (ModelVersionID, CustomerID, Probability, RiskLevel)
    VALUES (@ModelVersionID, 'ZZ-0001', 1.5, 'High');
    INSERT INTO @KetQua VALUES (20, N'ChurnPredictions: Probability 1,5', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (20, N'ChurnPredictions: Probability 1,5', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 21 (Y-03a): Probability âm phải bị chặn
BEGIN TRY
    INSERT INTO ChurnPredictions (ModelVersionID, CustomerID, Probability, RiskLevel)
    VALUES (@ModelVersionID, 'ZZ-0001', -0.1, 'Low');
    INSERT INTO @KetQua VALUES (21, N'ChurnPredictions: Probability âm', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (21, N'ChurnPredictions: Probability âm', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 22 (Y-03a): Probability đúng bằng 1 (biên) phải được chấp nhận
BEGIN TRY
    INSERT INTO ChurnPredictions (ModelVersionID, CustomerID, Probability, RiskLevel)
    VALUES (@ModelVersionID, 'ZZ-0001', 1, 'High');
    INSERT INTO @KetQua VALUES (22, N'ChurnPredictions: Probability = 1', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (22, N'ChurnPredictions: Probability = 1', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 23 (Y-03b): ModelVersions.Threshold 1,5 phải bị chặn
BEGIN TRY
    INSERT INTO ModelVersions (ModelName, Version, TrainDate, Threshold)
    VALUES ('ZZ_Model2', 'v0', GETDATE(), 1.5);
    INSERT INTO @KetQua VALUES (23, N'ModelVersions: Threshold 1,5', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (23, N'ModelVersions: Threshold 1,5', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 24 (Y-04a): Tickets.Status ngoài danh sách phải bị chặn
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status)
    VALUES ('ZZ-0001', GETDATE(), 'Billing', 'Low', 'Pending');
    INSERT INTO @KetQua VALUES (24, N'Tickets: Status = Pending', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (24, N'Tickets: Status = Pending', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 25 (Y-04a): Tickets.Priority ngoài danh sách phải bị chặn
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status)
    VALUES ('ZZ-0001', GETDATE(), 'Billing', 'Urgent', 'Open');
    INSERT INTO @KetQua VALUES (25, N'Tickets: Priority = Urgent', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (25, N'Tickets: Priority = Urgent', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 26 (Y-04d): Tickets.Category ngoài danh sách phải bị chặn
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status)
    VALUES ('ZZ-0001', GETDATE(), 'Other', 'Low', 'Open');
    INSERT INTO @KetQua VALUES (26, N'Tickets: Category = Other', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (26, N'Tickets: Category = Other', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 27 (Y-04b): ClosedAt sớm hơn CreatedAt phải bị chặn
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, ClosedAt, Category, Priority, Status)
    VALUES ('ZZ-0001', DATEADD(HOUR, -2, GETDATE()), DATEADD(HOUR, -3, GETDATE()), 'Billing', 'Low', 'Closed');
    INSERT INTO @KetQua VALUES (27, N'Tickets: ClosedAt < CreatedAt', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (27, N'Tickets: ClosedAt < CreatedAt', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 28 (Y-04c): ticket Closed thiếu ClosedAt phải bị chặn
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status)
    VALUES ('ZZ-0001', GETDATE(), 'Billing', 'Low', 'Closed');
    INSERT INTO @KetQua VALUES (28, N'Tickets: Closed thiếu ClosedAt', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (28, N'Tickets: Closed thiếu ClosedAt', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 29 (Y-04c): ticket Open mà có ClosedAt phải bị chặn
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, ClosedAt, Category, Priority, Status)
    VALUES ('ZZ-0001', DATEADD(HOUR, -2, GETDATE()), GETDATE(), 'Billing', 'Low', 'Open');
    INSERT INTO @KetQua VALUES (29, N'Tickets: Open có ClosedAt', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (29, N'Tickets: Open có ClosedAt', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 30 (L7): ticket Open mà có điểm hài lòng phải bị chặn
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status, SatisfactionScore)
    VALUES ('ZZ-0001', GETDATE(), 'Billing', 'Low', 'Open', 3);
    INSERT INTO @KetQua VALUES (30, N'Tickets: Open có SatisfactionScore', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (30, N'Tickets: Open có SatisfactionScore', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 31: ticket InProgress hợp lệ (không ClosedAt) phải được chấp nhận
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status)
    VALUES ('ZZ-0001', GETDATE(), 'Technical', 'Medium', 'InProgress');
    INSERT INTO @KetQua VALUES (31, N'Tickets: InProgress hợp lệ', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (31, N'Tickets: InProgress hợp lệ', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 32: ticket Closed hợp lệ (có ClosedAt, có điểm). Đánh dấu bằng Resolution 'ZZ-dong' để test 33, 34 tìm lại.
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, ClosedAt, Category, Priority, Status, Resolution, SatisfactionScore)
    VALUES ('ZZ-0001', DATEADD(HOUR, -2, GETDATE()), GETDATE(), 'Service', 'High', 'Closed', N'ZZ-dong', 4);
    INSERT INTO @KetQua VALUES (32, N'Tickets: Closed hợp lệ', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (32, N'Tickets: Closed hợp lệ', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 33 (D-18): mở lại ticket mà KHÔNG xóa ClosedAt và điểm phải bị chặn
BEGIN TRY
    UPDATE Tickets SET Status = 'InProgress' WHERE Resolution = N'ZZ-dong';
    INSERT INTO @KetQua VALUES (33, N'Tickets: mở lại mà giữ ClosedAt và điểm', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (33, N'Tickets: mở lại mà giữ ClosedAt và điểm', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 34 (D-18): mở lại đúng cách (về InProgress, xóa ClosedAt và điểm, ghi lý do) phải được chấp nhận
BEGIN TRY
    UPDATE Tickets
       SET Status = 'InProgress', ClosedAt = NULL, SatisfactionScore = NULL,
           ReopenReason = N'Khách báo lỗi lại'
     WHERE Resolution = N'ZZ-dong';
    SET @SoDong = @@ROWCOUNT;
    INSERT INTO @KetQua VALUES (34, N'Tickets: mở lại đúng cách', N'OK',
        CASE WHEN @SoDong = 1 THEN N'OK' ELSE N'Cập nhật ' + CAST(@SoDong AS nvarchar(10)) + N' dòng' END);
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (34, N'Tickets: mở lại đúng cách', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 35 (Y-05): dự báo nhập tay (CustomerID NULL) thiếu InputJson phải bị chặn
BEGIN TRY
    INSERT INTO ChurnPredictions (ModelVersionID, CustomerID, Probability, RiskLevel, InputJson)
    VALUES (@ModelVersionID, NULL, 0.5, 'Medium', NULL);
    INSERT INTO @KetQua VALUES (35, N'ChurnPredictions: CustomerID NULL, InputJson NULL', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (35, N'ChurnPredictions: CustomerID NULL, InputJson NULL', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 36 (Y-05): dự báo nhập tay có InputJson nhưng không phải JSON phải bị chặn
BEGIN TRY
    INSERT INTO ChurnPredictions (ModelVersionID, CustomerID, Probability, RiskLevel, InputJson)
    VALUES (@ModelVersionID, NULL, 0.5, 'Medium', N'day khong phai json');
    INSERT INTO @KetQua VALUES (36, N'ChurnPredictions: CustomerID NULL, InputJson không phải JSON', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (36, N'ChurnPredictions: CustomerID NULL, InputJson không phải JSON', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 37 (D-19): CustomerContracts thêm dòng đang hiệu lực (EffectiveTo NULL)
BEGIN TRY
    INSERT INTO CustomerContracts
        (CustomerID, EffectiveFrom, EffectiveTo, PhoneService, MultipleLines, InternetService,
         OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies,
         Contract, PaperlessBilling, PaymentMethod, MonthlyCharges)
    VALUES ('ZZ-0001', '20260930', NULL, 'Yes', 'No', 'DSL',
            'No', 'No', 'No', 'No', 'No', 'No',
            'Month-to-month', 'Yes', 'Mailed check', 29.85);
    INSERT INTO @KetQua VALUES (37, N'CustomerContracts: thêm dòng đang hiệu lực', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (37, N'CustomerContracts: thêm dòng đang hiệu lực', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 38 (D-19): dòng đang hiệu lực thứ hai của cùng khách phải bị chặn (unique CustomerID + EffectiveTo, NULL tính là bằng nhau)
BEGIN TRY
    INSERT INTO CustomerContracts
        (CustomerID, EffectiveFrom, EffectiveTo, PhoneService, MultipleLines, InternetService,
         OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies,
         Contract, PaperlessBilling, PaymentMethod, MonthlyCharges)
    VALUES ('ZZ-0001', '20261001', NULL, 'Yes', 'No', 'DSL',
            'No', 'No', 'No', 'No', 'No', 'No',
            'One year', 'Yes', 'Mailed check', 25.00);
    INSERT INTO @KetQua VALUES (38, N'CustomerContracts: hai dòng cùng đang hiệu lực', N'Lỗi 2627', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (38, N'CustomerContracts: hai dòng cùng đang hiệu lực', N'Lỗi 2627', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 39: EffectiveTo không lớn hơn EffectiveFrom phải bị chặn
BEGIN TRY
    INSERT INTO CustomerContracts
        (CustomerID, EffectiveFrom, EffectiveTo, PhoneService, MultipleLines, InternetService,
         OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies,
         Contract, PaperlessBilling, PaymentMethod, MonthlyCharges)
    VALUES ('ZZ-0001', '20260801', '20260801', 'Yes', 'No', 'DSL',
            'No', 'No', 'No', 'No', 'No', 'No',
            'Month-to-month', 'Yes', 'Mailed check', 29.85);
    INSERT INTO @KetQua VALUES (39, N'CustomerContracts: EffectiveTo = EffectiveFrom', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (39, N'CustomerContracts: EffectiveTo = EffectiveFrom', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 40 (D-19): quy trình đổi hợp đồng đúng thứ tự: ĐÓNG dòng cũ trước, rồi THÊM dòng mới đang hiệu lực
BEGIN TRY
    UPDATE CustomerContracts SET EffectiveTo = '20261001'
     WHERE CustomerID = 'ZZ-0001' AND EffectiveTo IS NULL;
    SET @SoDong = @@ROWCOUNT;
    INSERT INTO CustomerContracts
        (CustomerID, EffectiveFrom, EffectiveTo, PhoneService, MultipleLines, InternetService,
         OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies,
         Contract, PaperlessBilling, PaymentMethod, MonthlyCharges)
    VALUES ('ZZ-0001', '20261001', NULL, 'Yes', 'No', 'DSL',
            'No', 'No', 'No', 'No', 'No', 'No',
            'One year', 'Yes', 'Mailed check', 25.00);
    INSERT INTO @KetQua VALUES (40, N'CustomerContracts: đóng dòng cũ rồi thêm dòng mới', N'OK',
        CASE WHEN @SoDong = 1 THEN N'OK' ELSE N'Đóng ' + CAST(@SoDong AS nvarchar(10)) + N' dòng' END);
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (40, N'CustomerContracts: đóng dòng cũ rồi thêm dòng mới', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 41 (Y-03c): khóa ngưỡng có giá trị 1,5 phải bị chặn
BEGIN TRY
    INSERT INTO RiskConfig (ConfigKey, ConfigValue) VALUES ('RiskZZTestThreshold', '1.5');
    INSERT INTO @KetQua VALUES (41, N'RiskConfig: ngưỡng 1,5', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (41, N'RiskConfig: ngưỡng 1,5', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 42 (Y-03c): khóa ngưỡng có giá trị chữ phải bị chặn (kiểm TRY_CAST trả NULL thì CHECK không cho qua)
BEGIN TRY
    INSERT INTO RiskConfig (ConfigKey, ConfigValue) VALUES ('RiskZZTestThreshold', 'abc');
    INSERT INTO @KetQua VALUES (42, N'RiskConfig: ngưỡng là chữ', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (42, N'RiskConfig: ngưỡng là chữ', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 43 (Y-03c): khóa ngưỡng có giá trị 0,4 phải được chấp nhận
BEGIN TRY
    INSERT INTO RiskConfig (ConfigKey, ConfigValue) VALUES ('RiskZZTestThreshold', '0.4');
    INSERT INTO @KetQua VALUES (43, N'RiskConfig: ngưỡng 0,4', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (43, N'RiskConfig: ngưỡng 0,4', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 44: khóa KHÔNG phải ngưỡng thì giá trị chữ vẫn được (luật chỉ áp cho khóa Risk...Threshold)
BEGIN TRY
    INSERT INTO RiskConfig (ConfigKey, ConfigValue) VALUES ('ZZ_KhongPhaiNguong', 'abc');
    INSERT INTO @KetQua VALUES (44, N'RiskConfig: khóa không phải ngưỡng, giá trị chữ', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (44, N'RiskConfig: khóa không phải ngưỡng, giá trị chữ', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Hủy toàn bộ dữ liệu thử ở trên
ROLLBACK TRANSACTION;

/*-- Đếm số dòng SAU rollback --*/
SET @TelcoRaw = 0;
IF OBJECT_ID(N'dbo.TelcoRaw', N'U') IS NOT NULL
    EXEC sp_executesql N'SELECT @n = COUNT(*) FROM dbo.TelcoRaw', N'@n int OUTPUT', @n = @TelcoRaw OUTPUT;

INSERT INTO @Sau (TenBang, SoDong)
SELECT N'AuditLog', COUNT(*) FROM AuditLog
UNION ALL SELECT N'ChurnPredictions',  COUNT(*) FROM ChurnPredictions
UNION ALL SELECT N'CustomerContracts', COUNT(*) FROM CustomerContracts
UNION ALL SELECT N'CustomerSnapshots', COUNT(*) FROM CustomerSnapshots
UNION ALL SELECT N'Customers',         COUNT(*) FROM Customers
UNION ALL SELECT N'Interactions',      COUNT(*) FROM Interactions
UNION ALL SELECT N'ModelVersions',     COUNT(*) FROM ModelVersions
UNION ALL SELECT N'RiskConfig',        COUNT(*) FROM RiskConfig
UNION ALL SELECT N'Role',              COUNT(*) FROM Role
UNION ALL SELECT N'Staff',             COUNT(*) FROM Staff
UNION ALL SELECT N'Tickets',           COUNT(*) FROM Tickets
UNION ALL SELECT N'TelcoRaw',          @TelcoRaw;

/*--------------------------------------------------------------*/
/* KẾT QUẢ LƯỚI 1: cột KetLuan phải là ĐẠT ở cả 44 dòng         */
/*--------------------------------------------------------------*/
SELECT Stt, TenTest, DuKien, ThucTe,
       CASE WHEN DuKien = ThucTe THEN N'ĐẠT' ELSE N'SAI' END AS KetLuan
FROM @KetQua
ORDER BY Stt;

/*--------------------------------------------------------------*/
/* KẾT QUẢ LƯỚI 2 (Y-01): số dòng từng bảng trước và sau        */
/* ROLLBACK phải bằng nhau ở cả 12 dòng (11 bảng + TelcoRaw)    */
/*--------------------------------------------------------------*/
SELECT t.TenBang, t.SoDong AS SoDongTruoc, s.SoDong AS SoDongSau,
       CASE WHEN t.SoDong = s.SoDong THEN N'ĐẠT' ELSE N'SAI' END AS KetLuan
FROM @Truoc t
JOIN @Sau   s ON s.TenBang = t.TenBang
ORDER BY t.TenBang;
GO
