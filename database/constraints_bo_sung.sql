/*==============================================================*/
/* RÀNG BUỘC BỔ SUNG (CHECK nhiều cột)                          */
/*                                                              */
/* Vì sao có file này: hộp Table Properties của PowerDesigner   */
/* (SQL Server 2017) không có tab Check, còn CHECK gắn vào một  */
/* cột sẽ bị sinh "inline" và SQL Server cấm nhắc tới cột khác  */
/* (lỗi 8141). Nên các CHECK nhiều cột viết bằng ALTER TABLE    */
/* và chạy SAU schema.sql. (Kế hoạch D-21, phương án dự phòng.) */
/*                                                              */
/* Cách chạy: mở trong SSMS, chạy SAU 01_schema.sql, TRƯỚC khi  */
/* nạp dữ liệu. Chạy lại nhiều lần được: có sẵn thì bỏ qua.     */
/* Kỳ vọng cuối file: tổng số CHECK = 12                        */
/*   (6 từ schema.sql: SatisfactionScore, Probability,          */
/*    Threshold, Status, Priority, Category  + 6 từ file này).  */
/*==============================================================*/
USE CRM_Churn;
GO

/*--------------------------------------------------------------*/
/* Y-04b: ticket đã có ClosedAt thì ClosedAt không sớm hơn      */
/*        CreatedAt                                             */
/*--------------------------------------------------------------*/
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE name = 'CK_Tickets_ClosedAt_SauCreatedAt'
                 AND parent_object_id = OBJECT_ID('dbo.Tickets'))
    ALTER TABLE dbo.Tickets ADD CONSTRAINT CK_Tickets_ClosedAt_SauCreatedAt
        CHECK (ClosedAt IS NULL OR ClosedAt >= CreatedAt);
GO

/*--------------------------------------------------------------*/
/* Y-04c: ticket Closed phải có ClosedAt; ticket chưa Closed    */
/*        (Open, InProgress) không được có ClosedAt             */
/*        => mở lại ticket phải đặt ClosedAt = NULL (D-18)      */
/*--------------------------------------------------------------*/
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE name = 'CK_Tickets_TrangThai_ClosedAt'
                 AND parent_object_id = OBJECT_ID('dbo.Tickets'))
    ALTER TABLE dbo.Tickets ADD CONSTRAINT CK_Tickets_TrangThai_ClosedAt
        CHECK ((Status = 'Closed' AND ClosedAt IS NOT NULL)
            OR (Status <> 'Closed' AND ClosedAt IS NULL));
GO

/*--------------------------------------------------------------*/
/* Điểm hài lòng chỉ có ở ticket Closed (L7 của kế hoạch)       */
/* Hệ quả: khi mở lại ticket phải xóa SatisfactionScore (NULL)  */
/*--------------------------------------------------------------*/
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE name = 'CK_Tickets_DiemHaiLong_ChiKhiClosed'
                 AND parent_object_id = OBJECT_ID('dbo.Tickets'))
    ALTER TABLE dbo.Tickets ADD CONSTRAINT CK_Tickets_DiemHaiLong_ChiKhiClosed
        CHECK (SatisfactionScore IS NULL OR Status = 'Closed');
GO

/*--------------------------------------------------------------*/
/* Y-05: dự báo nhập tay (CustomerID NULL) bắt buộc có InputJson */
/*       là JSON hợp lệ. Có kèm "InputJson IS NOT NULL" để       */
/*       ISJSON(NULL) không làm CHECK cho qua nhầm.             */
/*--------------------------------------------------------------*/
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE name = 'CK_ChurnPredictions_NhapTay_CoInputJson'
                 AND parent_object_id = OBJECT_ID('dbo.ChurnPredictions'))
    ALTER TABLE dbo.ChurnPredictions ADD CONSTRAINT CK_ChurnPredictions_NhapTay_CoInputJson
        CHECK (CustomerID IS NOT NULL
               OR (InputJson IS NOT NULL AND ISJSON(InputJson) = 1));
GO

/*--------------------------------------------------------------*/
/* CustomerContracts: ngày hết hiệu lực phải sau ngày bắt đầu   */
/*--------------------------------------------------------------*/
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE name = 'CK_CustomerContracts_NgayHieuLuc'
                 AND parent_object_id = OBJECT_ID('dbo.CustomerContracts'))
    ALTER TABLE dbo.CustomerContracts ADD CONSTRAINT CK_CustomerContracts_NgayHieuLuc
        CHECK (EffectiveTo IS NULL OR EffectiveTo > EffectiveFrom);
GO

/*--------------------------------------------------------------*/
/* Y-03c: khóa ngưỡng risk trong RiskConfig phải là số thuộc    */
/*        [0, 1]. ConfigValue là chuỗi nên dùng TRY_CAST.       */
/*        Quy ước tên khóa (CHƯA CHỐT): RiskMediumThreshold,    */
/*        RiskHighThreshold; mẫu 'Risk%Threshold' khớp cả hai.  */
/*        Thứ tự Medium < High KHÔNG kiểm ở đây, kiểm ở web.    */
/*--------------------------------------------------------------*/
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints
               WHERE name = 'CK_RiskConfig_Nguong_0_den_1'
                 AND parent_object_id = OBJECT_ID('dbo.RiskConfig'))
    ALTER TABLE dbo.RiskConfig ADD CONSTRAINT CK_RiskConfig_Nguong_0_den_1
        CHECK (ConfigKey NOT LIKE 'Risk%Threshold'
               OR (TRY_CAST(ConfigValue AS decimal(9,8)) IS NOT NULL
                   AND TRY_CAST(ConfigValue AS decimal(9,8)) BETWEEN 0 AND 1));
GO

/*--------------------------------------------------------------*/
/* Kiểm: tổng số CHECK phải là 12                               */
/*--------------------------------------------------------------*/
SELECT COUNT(*) AS TongSoCheck, 12 AS DuKien FROM sys.check_constraints;
GO
