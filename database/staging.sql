/*==============================================================*/
/* STAGING: bảng đổ tạm TelcoRaw                                */
/*                                                              */
/* - Chứa đúng 21 cột của file CSV gốc, mọi cột đều là chuỗi,   */
/*   để lưu NGUYÊN VĂN dữ liệu trước khi làm sạch               */
/*   (ví dụ TotalCharges của 11 khách còn là một dấu cách).     */
/* - KHÔNG vẽ trong PDM, nên ERD vẫn là 10 bảng nghiệp vụ.      */
/* - Chạy được nhiều lần: đã có bảng thì không làm gì.          */
/*                                                              */
/* Cách chạy: mở trong SSMS, ô database chọn CRM_Churn, F5.     */
/*==============================================================*/
USE CRM_Churn;
GO

IF OBJECT_ID(N'dbo.TelcoRaw', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.TelcoRaw (
        customerID        varchar(60) NOT NULL,
        gender            varchar(60) NOT NULL,
        SeniorCitizen     varchar(60) NOT NULL,
        Partner           varchar(60) NOT NULL,
        Dependents        varchar(60) NOT NULL,
        tenure            varchar(60) NOT NULL,
        PhoneService      varchar(60) NOT NULL,
        MultipleLines     varchar(60) NOT NULL,
        InternetService   varchar(60) NOT NULL,
        OnlineSecurity    varchar(60) NOT NULL,
        OnlineBackup      varchar(60) NOT NULL,
        DeviceProtection  varchar(60) NOT NULL,
        TechSupport       varchar(60) NOT NULL,
        StreamingTV       varchar(60) NOT NULL,
        StreamingMovies   varchar(60) NOT NULL,
        Contract          varchar(60) NOT NULL,
        PaperlessBilling  varchar(60) NOT NULL,
        PaymentMethod     varchar(60) NOT NULL,
        MonthlyCharges    varchar(60) NOT NULL,
        TotalCharges      varchar(60) NOT NULL,
        Churn             varchar(60) NOT NULL
    );
    PRINT N'Đã tạo bảng TelcoRaw.';
END
ELSE
    PRINT N'Bảng TelcoRaw đã có, không làm gì.';
GO
