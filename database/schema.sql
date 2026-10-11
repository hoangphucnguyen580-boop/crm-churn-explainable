/*==============================================================*/
/* DBMS name:      Microsoft SQL Server 2017                    */
/* Created on:     10/10/2026 10:23:18 CH                       */
/*==============================================================*/

/*==============================================================*/
/* Table: AuditLog                                              */
/*==============================================================*/
create table AuditLog (
   AuditID              bigint               identity,
   StaffID              int                  not null,
   Action               varchar(10)          not null,
   TableName            varchar(50)          not null,
   RecordKey            varchar(50)          not null,
   OldValues            nvarchar(max)        null,
   NewValues            nvarchar(max)        null,
   OccurredAt           datetime             not null default getdate(),
   constraint PK_AUDITLOG primary key (AuditID)
)
go

/*==============================================================*/
/* Index: THUC_HIEN_FK                                          */
/*==============================================================*/




create nonclustered index THUC_HIEN_FK on AuditLog (StaffID ASC)
go

/*==============================================================*/
/* Table: ChurnPredictions                                      */
/*==============================================================*/
create table ChurnPredictions (
   PredictionID         bigint               identity,
   ModelVersionID       int                  not null,
   CustomerID           varchar(20)          null,
   PredictionTime       datetime             not null default getdate(),
   Probability          decimal(9,8)         not null,
   RiskLevel            varchar(10)          not null,
   InputJson            nvarchar(max)        null,
   TopFactorsJson       nvarchar(max)        null,
   constraint PK_CHURNPREDICTIONS primary key (PredictionID)
)
go

/*==============================================================*/
/* Index: _UOC_CHAM_FK                                          */
/*==============================================================*/




create nonclustered index _UOC_CHAM_FK on ChurnPredictions (CustomerID ASC)
go

/*==============================================================*/
/* Index: SINH_RA_FK                                            */
/*==============================================================*/




create nonclustered index SINH_RA_FK on ChurnPredictions (ModelVersionID ASC)
go

/*==============================================================*/
/* Table: CustomerSnapshots                                     */
/*==============================================================*/
create table CustomerSnapshots (
   SnapshotID           bigint               identity,
   CustomerID           varchar(20)          not null,
   SnapshotDate         datetime             not null,
   Tenure               int                  not null,
   PhoneService         varchar(30)          not null,
   MultipleLines        varchar(30)          not null,
   InternetService      varchar(30)          not null,
   OnlineSecurity       varchar(30)          not null,
   OnlineBackup         varchar(30)          not null,
   DeviceProtection     varchar(30)          not null,
   TechSupport          varchar(30)          not null,
   StreamingTV          varchar(30)          not null,
   StreamingMovies      varchar(30)          not null,
   Contract             varchar(30)          not null,
   PaperlessBilling     varchar(10)          not null,
   PaymentMethod        varchar(50)          not null,
   MonthlyCharges       decimal(8,2)         not null,
   TotalCharges         decimal(10,2)        null,
   ChurnLabel           varchar(10)          null,
   constraint PK_CUSTOMERSNAPSHOTS primary key (SnapshotID)
)
go

/*==============================================================*/
/* Index: CO1_FK                                                */
/*==============================================================*/




create nonclustered index CO1_FK on CustomerSnapshots (CustomerID ASC)
go

/*==============================================================*/
/* Table: Customers                                             */
/*==============================================================*/
create table Customers (
   CustomerID           varchar(20)          not null,
   Gender               varchar(10)          null,
   SeniorCitizen        bit                  not null,
   Partner              bit                  null,
   Dependents           bit                  null,
   EstimatedJoinDate    datetime             null,
   CustomerStatus       varchar(20)          not null default 'Active',
   CreatedAt            datetime             not null default getdate(),
   constraint PK_CUSTOMERS primary key (CustomerID)
)
go

/*==============================================================*/
/* Table: Interactions                                          */
/*==============================================================*/
create table Interactions (
   InteractionID        bigint               identity,
   StaffID              int                  null,
   CustomerID           varchar(20)          not null,
   InteractionDate      datetime             not null,
   Channel              varchar(20)          not null,
   InteractionType      varchar(30)          not null,
   Description          nvarchar(1000)       null,
   Result               varchar(30)          null,
   IsSimulated          bit                  not null default 0,
   constraint PK_INTERACTIONS primary key (InteractionID)
)
go

/*==============================================================*/
/* Index: PHU_TRACH_FK                                          */
/*==============================================================*/




create nonclustered index PHU_TRACH_FK on Interactions (StaffID ASC)
go

/*==============================================================*/
/* Index: CO_FK                                                 */
/*==============================================================*/




create nonclustered index CO_FK on Interactions (CustomerID ASC)
go

/*==============================================================*/
/* Table: ModelVersions                                         */
/*==============================================================*/
create table ModelVersions (
   ModelVersionID       int                  identity,
   ModelName            varchar(50)          not null,
   Version              varchar(20)          not null,
   TrainDate            datetime             not null,
   Threshold            decimal(5,4)         not null,
   MetricsJson          nvarchar(max)        null,
   Seed                 int                  null,
   ConfigJson           nvarchar(max)        null,
   DatasetHash          varchar(64)          null,
   LibVersions          varchar(500)         null,
   constraint PK_MODELVERSIONS primary key (ModelVersionID)
)
go

/*==============================================================*/
/* Table: RiskConfig                                            */
/*==============================================================*/
create table RiskConfig (
   ConfigKey            varchar(50)          not null,
   UpdatedByStaffID     int                  null,
   ConfigValue          varchar(100)         not null,
   UpdatedAt            datetime             not null default getdate(),
   constraint PK_RISKCONFIG primary key (ConfigKey)
)
go

/*==============================================================*/
/* Index: CAP_NHAT_FK                                           */
/*==============================================================*/




create nonclustered index CAP_NHAT_FK on RiskConfig (UpdatedByStaffID ASC)
go

/*==============================================================*/
/* Table: Role                                                  */
/*==============================================================*/
create table Role (
   RoleID               int                  identity,
   RoleName             varchar(30)          not null,
   constraint PK_ROLE primary key (RoleID),
   constraint AK_ROLENAME_ROLE unique (RoleName)
)
go

/*==============================================================*/
/* Table: Staff                                                 */
/*==============================================================*/
create table Staff (
   StaffID              int                  identity,
   RoleID               int                  not null,
   FullName             nvarchar(100)        not null,
   Email                varchar(100)         null,
   Username             varchar(50)          not null,
   PasswordHash         varchar(255)         not null,
   IsActive             bit                  not null,
   constraint PK_STAFF primary key (StaffID),
   constraint AK_USERNAME_STAFF unique (Username)
)
go

/*==============================================================*/
/* Index: GAN_CHO_FK                                            */
/*==============================================================*/




create nonclustered index GAN_CHO_FK on Staff (RoleID ASC)
go

/*==============================================================*/
/* Table: Tickets                                               */
/*==============================================================*/
create table Tickets (
   TicketID             bigint               identity,
   AssignedStaffID      int                  null,
   CustomerID           varchar(20)          not null,
   CreatedAt            datetime             not null,
   ClosedAt             datetime             null,
   Category             varchar(50)          not null,
   Priority             varchar(10)          not null,
   Status               varchar(20)          not null,
   Resolution           nvarchar(1000)       null,
   SatisfactionScore    smallint             null 
      constraint CKC_SATISFACTIONSCORE_TICKETS check (SatisfactionScore is null or (SatisfactionScore between 1 and 5)),
   IsSimulated          bit                  not null default 0,
   constraint PK_TICKETS primary key (TicketID)
)
go

/*==============================================================*/
/* Index: XU_LY_FK                                              */
/*==============================================================*/




create nonclustered index XU_LY_FK on Tickets (AssignedStaffID ASC)
go

/*==============================================================*/
/* Index: MO_FK                                                 */
/*==============================================================*/




create nonclustered index MO_FK on Tickets (CustomerID ASC)
go

alter table AuditLog
   add constraint FK_AUDITLOG_THUC_HIEN_STAFF foreign key (StaffID)
      references Staff (StaffID)
go

alter table ChurnPredictions
   add constraint FK_CHURNPRE_SINH_RA_MODELVER foreign key (ModelVersionID)
      references ModelVersions (ModelVersionID)
go

alter table ChurnPredictions
   add constraint FK_CHURNPRE__UOC_CHAM_CUSTOMER foreign key (CustomerID)
      references Customers (CustomerID)
go

alter table CustomerSnapshots
   add constraint FK_CUSTOMER_CO1_CUSTOMER foreign key (CustomerID)
      references Customers (CustomerID)
go

alter table Interactions
   add constraint FK_INTERACT_CO_CUSTOMER foreign key (CustomerID)
      references Customers (CustomerID)
go

alter table Interactions
   add constraint FK_INTERACT_PHU_TRACH_STAFF foreign key (StaffID)
      references Staff (StaffID)
go

alter table RiskConfig
   add constraint FK_RISKCONF_CAP_NHAT_STAFF foreign key (UpdatedByStaffID)
      references Staff (StaffID)
go

alter table Staff
   add constraint FK_STAFF_GAN_CHO_ROLE foreign key (RoleID)
      references Role (RoleID)
go

alter table Tickets
   add constraint FK_TICKETS_MO_CUSTOMER foreign key (CustomerID)
      references Customers (CustomerID)
go

alter table Tickets
   add constraint FK_TICKETS_XU_LY_STAFF foreign key (AssignedStaffID)
      references Staff (StaffID)
go

