using System;
using System.Collections.Generic;
using CrmChurn.Web.Models;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Data;

public partial class CrmDbContext : DbContext
{
    public CrmDbContext(DbContextOptions<CrmDbContext> options)
        : base(options)
    {
    }

    public virtual DbSet<AuditLog> AuditLogs { get; set; }

    public virtual DbSet<ChurnPrediction> ChurnPredictions { get; set; }

    public virtual DbSet<Customer> Customers { get; set; }

    public virtual DbSet<CustomerContract> CustomerContracts { get; set; }

    public virtual DbSet<CustomerSnapshot> CustomerSnapshots { get; set; }

    public virtual DbSet<Interaction> Interactions { get; set; }

    public virtual DbSet<ModelVersion> ModelVersions { get; set; }

    public virtual DbSet<RiskConfig> RiskConfigs { get; set; }

    public virtual DbSet<Role> Roles { get; set; }

    public virtual DbSet<Staff> Staff { get; set; }

    public virtual DbSet<Ticket> Tickets { get; set; }

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<AuditLog>(entity =>
        {
            entity.HasKey(e => e.AuditId).HasName("PK_AUDITLOG");

            entity.ToTable("AuditLog");

            entity.HasIndex(e => e.StaffId, "THUC_HIEN_FK");

            entity.Property(e => e.AuditId).HasColumnName("AuditID");
            entity.Property(e => e.Action)
                .HasMaxLength(10)
                .IsUnicode(false);
            entity.Property(e => e.OccurredAt)
                .HasDefaultValueSql("(getdate())")
                .HasColumnType("datetime");
            entity.Property(e => e.RecordKey)
                .HasMaxLength(50)
                .IsUnicode(false);
            entity.Property(e => e.StaffId).HasColumnName("StaffID");
            entity.Property(e => e.TableName)
                .HasMaxLength(50)
                .IsUnicode(false);

            entity.HasOne(d => d.Staff).WithMany(p => p.AuditLogs)
                .HasForeignKey(d => d.StaffId)
                .OnDelete(DeleteBehavior.ClientSetNull)
                .HasConstraintName("FK_AUDITLOG_THUC_HIEN_STAFF");
        });

        modelBuilder.Entity<ChurnPrediction>(entity =>
        {
            entity.HasKey(e => e.PredictionId).HasName("PK_CHURNPREDICTIONS");

            entity.HasIndex(e => e.ModelVersionId, "SINH_RA_FK");

            entity.HasIndex(e => e.CustomerId, "_UOC_CHAM_FK");

            entity.Property(e => e.PredictionId).HasColumnName("PredictionID");
            entity.Property(e => e.CustomerId)
                .HasMaxLength(20)
                .IsUnicode(false)
                .HasColumnName("CustomerID");
            entity.Property(e => e.ModelVersionId).HasColumnName("ModelVersionID");
            entity.Property(e => e.PredictionTime)
                .HasDefaultValueSql("(getdate())")
                .HasColumnType("datetime");
            entity.Property(e => e.Probability).HasColumnType("decimal(9, 8)");
            entity.Property(e => e.RiskLevel)
                .HasMaxLength(10)
                .IsUnicode(false);

            entity.HasOne(d => d.Customer).WithMany(p => p.ChurnPredictions)
                .HasForeignKey(d => d.CustomerId)
                .HasConstraintName("FK_CHURNPRE__UOC_CHAM_CUSTOMER");

            entity.HasOne(d => d.ModelVersion).WithMany(p => p.ChurnPredictions)
                .HasForeignKey(d => d.ModelVersionId)
                .OnDelete(DeleteBehavior.ClientSetNull)
                .HasConstraintName("FK_CHURNPRE_SINH_RA_MODELVER");
        });

        modelBuilder.Entity<Customer>(entity =>
        {
            entity.HasKey(e => e.CustomerId).HasName("PK_CUSTOMERS");

            entity.Property(e => e.CustomerId)
                .HasMaxLength(20)
                .IsUnicode(false)
                .HasColumnName("CustomerID");
            entity.Property(e => e.CreatedAt)
                .HasDefaultValueSql("(getdate())")
                .HasColumnType("datetime");
            entity.Property(e => e.CustomerStatus)
                .HasMaxLength(20)
                .IsUnicode(false)
                .HasDefaultValue("Active");
            entity.Property(e => e.EstimatedJoinDate).HasColumnType("datetime");
            entity.Property(e => e.Gender)
                .HasMaxLength(10)
                .IsUnicode(false);
        });

        modelBuilder.Entity<CustomerContract>(entity =>
        {
            entity.HasKey(e => e.ContractRecordId).HasName("PK_CUSTOMERCONTRACTS");

            entity.HasIndex(e => new { e.CustomerId, e.EffectiveTo }, "AK_DANG_HIEU_LUC_CUSTOMER").IsUnique();

            entity.Property(e => e.ContractRecordId).HasColumnName("ContractRecordID");
            entity.Property(e => e.Contract)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.CustomerId)
                .HasMaxLength(20)
                .IsUnicode(false)
                .HasColumnName("CustomerID");
            entity.Property(e => e.DeviceProtection)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.EffectiveFrom).HasColumnType("datetime");
            entity.Property(e => e.EffectiveTo).HasColumnType("datetime");
            entity.Property(e => e.InternetService)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.MonthlyCharges).HasColumnType("decimal(8, 2)");
            entity.Property(e => e.MultipleLines)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.OnlineBackup)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.OnlineSecurity)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.PaperlessBilling)
                .HasMaxLength(10)
                .IsUnicode(false);
            entity.Property(e => e.PaymentMethod)
                .HasMaxLength(50)
                .IsUnicode(false);
            entity.Property(e => e.PhoneService)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.StreamingMovies)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.StreamingTv)
                .HasMaxLength(30)
                .IsUnicode(false)
                .HasColumnName("StreamingTV");
            entity.Property(e => e.TechSupport)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.UpdatedByStaffId).HasColumnName("UpdatedByStaffID");

            entity.HasOne(d => d.Customer).WithMany(p => p.CustomerContracts)
                .HasForeignKey(d => d.CustomerId)
                .OnDelete(DeleteBehavior.ClientSetNull)
                .HasConstraintName("FK_CUSTOMER_CO_HOP_DO_CUSTOMER");

            entity.HasOne(d => d.UpdatedByStaff).WithMany(p => p.CustomerContracts)
                .HasForeignKey(d => d.UpdatedByStaffId)
                .HasConstraintName("FK_CUSTOMER_CAP_NHAT__STAFF");
        });

        modelBuilder.Entity<CustomerSnapshot>(entity =>
        {
            entity.HasKey(e => e.SnapshotId).HasName("PK_CUSTOMERSNAPSHOTS");

            entity.HasIndex(e => new { e.CustomerId, e.SnapshotDate }, "AK_SNAPSHOT_THEO_NGAY_CUSTOMER").IsUnique();

            entity.HasIndex(e => e.CustomerId, "CO1_FK");

            entity.Property(e => e.SnapshotId).HasColumnName("SnapshotID");
            entity.Property(e => e.ChurnLabel)
                .HasMaxLength(10)
                .IsUnicode(false);
            entity.Property(e => e.Contract)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.CustomerId)
                .HasMaxLength(20)
                .IsUnicode(false)
                .HasColumnName("CustomerID");
            entity.Property(e => e.DeviceProtection)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.InternetService)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.MonthlyCharges).HasColumnType("decimal(8, 2)");
            entity.Property(e => e.MultipleLines)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.OnlineBackup)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.OnlineSecurity)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.PaperlessBilling)
                .HasMaxLength(10)
                .IsUnicode(false);
            entity.Property(e => e.PaymentMethod)
                .HasMaxLength(50)
                .IsUnicode(false);
            entity.Property(e => e.PhoneService)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.SnapshotDate).HasColumnType("datetime");
            entity.Property(e => e.StreamingMovies)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.StreamingTv)
                .HasMaxLength(30)
                .IsUnicode(false)
                .HasColumnName("StreamingTV");
            entity.Property(e => e.TechSupport)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.TotalCharges).HasColumnType("decimal(10, 2)");

            entity.HasOne(d => d.Customer).WithMany(p => p.CustomerSnapshots)
                .HasForeignKey(d => d.CustomerId)
                .OnDelete(DeleteBehavior.ClientSetNull)
                .HasConstraintName("FK_CUSTOMER_CO1_CUSTOMER");
        });

        modelBuilder.Entity<Interaction>(entity =>
        {
            entity.HasKey(e => e.InteractionId).HasName("PK_INTERACTIONS");

            entity.HasIndex(e => e.CustomerId, "CO_FK");

            entity.HasIndex(e => e.StaffId, "PHU_TRACH_FK");

            entity.Property(e => e.InteractionId).HasColumnName("InteractionID");
            entity.Property(e => e.Channel)
                .HasMaxLength(20)
                .IsUnicode(false);
            entity.Property(e => e.CustomerId)
                .HasMaxLength(20)
                .IsUnicode(false)
                .HasColumnName("CustomerID");
            entity.Property(e => e.Description).HasMaxLength(1000);
            entity.Property(e => e.InteractionDate).HasColumnType("datetime");
            entity.Property(e => e.InteractionType)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.Result)
                .HasMaxLength(30)
                .IsUnicode(false);
            entity.Property(e => e.StaffId).HasColumnName("StaffID");

            entity.HasOne(d => d.Customer).WithMany(p => p.Interactions)
                .HasForeignKey(d => d.CustomerId)
                .OnDelete(DeleteBehavior.ClientSetNull)
                .HasConstraintName("FK_INTERACT_CO_CUSTOMER");

            entity.HasOne(d => d.Staff).WithMany(p => p.Interactions)
                .HasForeignKey(d => d.StaffId)
                .HasConstraintName("FK_INTERACT_PHU_TRACH_STAFF");
        });

        modelBuilder.Entity<ModelVersion>(entity =>
        {
            entity.HasKey(e => e.ModelVersionId).HasName("PK_MODELVERSIONS");

            entity.Property(e => e.ModelVersionId).HasColumnName("ModelVersionID");
            entity.Property(e => e.DatasetHash)
                .HasMaxLength(64)
                .IsUnicode(false);
            entity.Property(e => e.LibVersions)
                .HasMaxLength(500)
                .IsUnicode(false);
            entity.Property(e => e.ModelName)
                .HasMaxLength(50)
                .IsUnicode(false);
            entity.Property(e => e.Threshold).HasColumnType("decimal(5, 4)");
            entity.Property(e => e.TrainDate).HasColumnType("datetime");
            entity.Property(e => e.Version)
                .HasMaxLength(20)
                .IsUnicode(false);
        });

        modelBuilder.Entity<RiskConfig>(entity =>
        {
            entity.HasKey(e => e.ConfigKey).HasName("PK_RISKCONFIG");

            entity.ToTable("RiskConfig");

            entity.HasIndex(e => e.UpdatedByStaffId, "CAP_NHAT_FK");

            entity.Property(e => e.ConfigKey)
                .HasMaxLength(50)
                .IsUnicode(false);
            entity.Property(e => e.ConfigValue)
                .HasMaxLength(100)
                .IsUnicode(false);
            entity.Property(e => e.UpdatedAt)
                .HasDefaultValueSql("(getdate())")
                .HasColumnType("datetime");
            entity.Property(e => e.UpdatedByStaffId).HasColumnName("UpdatedByStaffID");

            entity.HasOne(d => d.UpdatedByStaff).WithMany(p => p.RiskConfigs)
                .HasForeignKey(d => d.UpdatedByStaffId)
                .HasConstraintName("FK_RISKCONF_CAP_NHAT_STAFF");
        });

        modelBuilder.Entity<Role>(entity =>
        {
            entity.HasKey(e => e.RoleId).HasName("PK_ROLE");

            entity.ToTable("Role");

            entity.HasIndex(e => e.RoleName, "AK_ROLENAME_ROLE").IsUnique();

            entity.Property(e => e.RoleId).HasColumnName("RoleID");
            entity.Property(e => e.RoleName)
                .HasMaxLength(30)
                .IsUnicode(false);
        });

        modelBuilder.Entity<Staff>(entity =>
        {
            entity.HasKey(e => e.StaffId).HasName("PK_STAFF");

            entity.HasIndex(e => e.Username, "AK_USERNAME_STAFF").IsUnique();

            entity.HasIndex(e => e.RoleId, "GAN_CHO_FK");

            entity.Property(e => e.StaffId).HasColumnName("StaffID");
            entity.Property(e => e.Email)
                .HasMaxLength(100)
                .IsUnicode(false);
            entity.Property(e => e.FullName).HasMaxLength(100);
            entity.Property(e => e.PasswordHash)
                .HasMaxLength(255)
                .IsUnicode(false);
            entity.Property(e => e.RoleId).HasColumnName("RoleID");
            entity.Property(e => e.Username)
                .HasMaxLength(50)
                .IsUnicode(false);

            entity.HasOne(d => d.Role).WithMany(p => p.Staff)
                .HasForeignKey(d => d.RoleId)
                .OnDelete(DeleteBehavior.ClientSetNull)
                .HasConstraintName("FK_STAFF_GAN_CHO_ROLE");
        });

        modelBuilder.Entity<Ticket>(entity =>
        {
            entity.HasKey(e => e.TicketId).HasName("PK_TICKETS");

            entity.HasIndex(e => e.CustomerId, "MO_FK");

            entity.HasIndex(e => e.AssignedStaffId, "XU_LY_FK");

            entity.Property(e => e.TicketId).HasColumnName("TicketID");
            entity.Property(e => e.AssignedStaffId).HasColumnName("AssignedStaffID");
            entity.Property(e => e.Category)
                .HasMaxLength(50)
                .IsUnicode(false);
            entity.Property(e => e.ClosedAt).HasColumnType("datetime");
            entity.Property(e => e.CreatedAt).HasColumnType("datetime");
            entity.Property(e => e.CustomerId)
                .HasMaxLength(20)
                .IsUnicode(false)
                .HasColumnName("CustomerID");
            entity.Property(e => e.Priority)
                .HasMaxLength(10)
                .IsUnicode(false);
            entity.Property(e => e.ReopenReason).HasMaxLength(500);
            entity.Property(e => e.Resolution).HasMaxLength(1000);
            entity.Property(e => e.Status)
                .HasMaxLength(20)
                .IsUnicode(false);

            entity.HasOne(d => d.AssignedStaff).WithMany(p => p.Tickets)
                .HasForeignKey(d => d.AssignedStaffId)
                .HasConstraintName("FK_TICKETS_XU_LY_STAFF");

            entity.HasOne(d => d.Customer).WithMany(p => p.Tickets)
                .HasForeignKey(d => d.CustomerId)
                .OnDelete(DeleteBehavior.ClientSetNull)
                .HasConstraintName("FK_TICKETS_MO_CUSTOMER");
        });

        OnModelCreatingPartial(modelBuilder);
    }

    partial void OnModelCreatingPartial(ModelBuilder modelBuilder);
}
