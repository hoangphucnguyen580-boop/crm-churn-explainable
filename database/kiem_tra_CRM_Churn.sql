/*==============================================================*/
/* KIỂM TRA DATABASE CRM_Churn                                  */
/*   Phần 1: đếm đối tượng (chỉ đọc, không sửa gì)              */
/*   Phần 2: test hành vi trong transaction, ROLLBACK ở cuối    */
/*           -> chạy xong không để lại dòng dữ liệu nào         */
/* Cách chạy: mở file trong SSMS, bấm Execute (F5) một lần.     */
/*==============================================================*/
USE CRM_Churn;
GO

/*--------------------------------------------------------------*/
/* PHẦN 1: ĐẾM ĐỐI TƯỢNG (chỉ đọc)                              */
/* Kết quả: 5 dòng, cột ThucTe phải bằng cột DuKien              */
/*--------------------------------------------------------------*/
SELECT N'Bảng'       AS MucKiemTra, COUNT(*) AS ThucTe, 10 AS DuKien FROM sys.tables
UNION ALL
SELECT N'Khóa ngoại',               COUNT(*),           10          FROM sys.foreign_keys
UNION ALL
SELECT N'Default',                  COUNT(*),            7          FROM sys.default_constraints
UNION ALL
SELECT N'Unique',                   COUNT(*),            2          FROM sys.key_constraints WHERE type = 'UQ'
UNION ALL
SELECT N'Check',                    COUNT(*),            1          FROM sys.check_constraints;
GO

/*--------------------------------------------------------------*/
/* PHẦN 2: TEST HÀNH VI                                         */
/* Mỗi test nằm trong TRY...CATCH:                              */
/*   - thêm thành công  -> ThucTe = OK                          */
/*   - bị chặn           -> ThucTe = Lỗi <mã lỗi>               */
/* Mã lỗi: 515 = NULL vào cột not null, 2627 = trùng unique,    */
/*         547 = vi phạm khóa ngoại hoặc CHECK                  */
/*--------------------------------------------------------------*/
SET NOCOUNT ON;

-- Biến kiểu bảng KHÔNG bị ROLLBACK xóa, nên dùng để giữ kết quả test
DECLARE @KetQua TABLE (
    Stt     int,
    TenTest nvarchar(100),
    DuKien  nvarchar(60),
    ThucTe  nvarchar(60)
);

DECLARE @RoleID         int;
DECLARE @StaffID        int;
DECLARE @ModelVersionID int;
DECLARE @Text           nvarchar(60);
DECLARE @Time           datetime;

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

-- Test 10: Tickets không điền SatisfactionScore (NULL) và IsSimulated -> IsSimulated phải ra 0
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status)
    VALUES ('ZZ-0001', GETDATE(), 'Billing', 'Low', 'Open');
    SELECT @Text = CAST(IsSimulated AS nvarchar(5)) FROM Tickets WHERE CustomerID = 'ZZ-0001';
    INSERT INTO @KetQua VALUES (10, N'Tickets: điểm NULL + IsSimulated tự điền', N'0', @Text);
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (10, N'Tickets: điểm NULL + IsSimulated tự điền', N'0', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 11: Tickets điểm 6 phải bị chặn (CHECK 1 đến 5)
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status, SatisfactionScore)
    VALUES ('ZZ-0001', GETDATE(), 'Billing', 'Low', 'Closed', 6);
    INSERT INTO @KetQua VALUES (11, N'Tickets: điểm 6', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (11, N'Tickets: điểm 6', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 12: Tickets điểm 0 phải bị chặn (CHECK 1 đến 5)
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status, SatisfactionScore)
    VALUES ('ZZ-0001', GETDATE(), 'Billing', 'Low', 'Closed', 0);
    INSERT INTO @KetQua VALUES (12, N'Tickets: điểm 0', N'Lỗi 547', N'Không báo lỗi');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (12, N'Tickets: điểm 0', N'Lỗi 547', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 13: Tickets điểm 5 phải được chấp nhận
BEGIN TRY
    INSERT INTO Tickets (CustomerID, CreatedAt, Category, Priority, Status, SatisfactionScore)
    VALUES ('ZZ-0001', GETDATE(), 'Billing', 'Low', 'Closed', 5);
    INSERT INTO @KetQua VALUES (13, N'Tickets: điểm 5', N'OK', N'OK');
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (13, N'Tickets: điểm 5', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
END CATCH;

-- Test 14 và 15: ChurnPredictions với CustomerID NULL (dự báo nhập tay) + PredictionTime tự điền
BEGIN TRY
    INSERT INTO ModelVersions (ModelName, Version, TrainDate, Threshold)
    VALUES ('ZZ_Model', 'v0', GETDATE(), 0.5);
    SELECT @ModelVersionID = ModelVersionID FROM ModelVersions WHERE ModelName = 'ZZ_Model';

    INSERT INTO ChurnPredictions (ModelVersionID, CustomerID, Probability, RiskLevel)
    VALUES (@ModelVersionID, NULL, 0.5, 'Medium');
    SELECT @Time = PredictionTime FROM ChurnPredictions WHERE ModelVersionID = @ModelVersionID;

    INSERT INTO @KetQua VALUES (14, N'ChurnPredictions: CustomerID NULL', N'OK', N'OK');
    INSERT INTO @KetQua VALUES (15, N'ChurnPredictions.PredictionTime tự điền giờ', N'Giờ hiện tại',
        CASE WHEN ABS(DATEDIFF(SECOND, @Time, GETDATE())) <= 60 THEN N'Giờ hiện tại' ELSE N'Sai giờ' END);
END TRY
BEGIN CATCH
    INSERT INTO @KetQua VALUES (14, N'ChurnPredictions: CustomerID NULL', N'OK', N'Lỗi ' + CAST(ERROR_NUMBER() AS nvarchar(10)));
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

-- Hủy toàn bộ dữ liệu thử ở trên
ROLLBACK TRANSACTION;

/*--------------------------------------------------------------*/
/* KẾT QUẢ: cột KetLuan phải là ĐẠT ở cả 17 dòng                */
/*--------------------------------------------------------------*/
SELECT Stt, TenTest, DuKien, ThucTe,
       CASE WHEN DuKien = ThucTe THEN N'ĐẠT' ELSE N'SAI' END AS KetLuan
FROM @KetQua
ORDER BY Stt;

-- Kiểm tra ROLLBACK sạch: tổng số dòng còn lại trong 9 bảng phải bằng 0
SELECT (SELECT COUNT(*) FROM Role)
     + (SELECT COUNT(*) FROM Staff)
     + (SELECT COUNT(*) FROM Customers)
     + (SELECT COUNT(*) FROM Interactions)
     + (SELECT COUNT(*) FROM Tickets)
     + (SELECT COUNT(*) FROM ModelVersions)
     + (SELECT COUNT(*) FROM ChurnPredictions)
     + (SELECT COUNT(*) FROM RiskConfig)
     + (SELECT COUNT(*) FROM AuditLog) AS TongSoDongConLai;
GO
