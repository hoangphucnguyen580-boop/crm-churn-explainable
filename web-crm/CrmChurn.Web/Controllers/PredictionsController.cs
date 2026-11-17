using System.Globalization;
using System.Text.Json;
using CrmChurn.Web.Data;
using CrmChurn.Web.Models;
using CrmChurn.Web.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

// Cả ba vai trò được dự báo (ma trận quyền, UC-05)
[Authorize(Roles = "Agent,Manager,Admin")]
public class PredictionsController : Controller
{
    private const string LoiLuu = "Kết quả chưa được lưu, không có dự báo nào bị ghi. Hãy thử lại sau.";

    private readonly CrmDbContext _db;
    private readonly PredictionClient _client;
    private readonly ILogger<PredictionsController> _logger;

    public PredictionsController(CrmDbContext db, PredictionClient client, ILogger<PredictionsController> logger)
    {
        _db = db;
        _client = client;
        _logger = logger;
    }

    // Lỗi mà câu báo đã sẵn sàng đưa cho người dùng
    private sealed class LoiDuBaoException : Exception
    {
        public LoiDuBaoException(string message) : base(message) { }
    }

    // ---------------------------------------------------------------
    // Trang đầu: chọn khách + 10 dự báo gần nhất
    // ---------------------------------------------------------------
    [HttpGet]
    public async Task<IActionResult> Index()
    {
        try
        {
            var model = new PredictionIndexViewModel
            {
                GanDay = await _db.ChurnPredictions.AsNoTracking()
                    .OrderByDescending(p => p.PredictionTime)
                    .ThenByDescending(p => p.PredictionId)
                    .Take(10)
                    .Select(p => new PredictionHistoryRow
                    {
                        PredictionId = p.PredictionId,
                        CustomerId = p.CustomerId,
                        PredictionTime = p.PredictionTime,
                        Probability = p.Probability,
                        RiskLevel = p.RiskLevel,
                        ModelVersion = p.ModelVersion.Version
                    })
                    .ToListAsync()
            };
            return View(model);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi tải trang dự báo");
            return View("LoiHeThong");
        }
    }

    // ---------------------------------------------------------------
    // Khách có sẵn (FR-28). POST vì có gọi API và ghi database.
    // ---------------------------------------------------------------
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Existing(string? customerId)
    {
        string ma = (customerId ?? "").Trim();
        if (ma == "")
        {
            TempData["ThongBao"] = "Nhập mã khách cần dự báo.";
            return RedirectToAction(nameof(Index));
        }

        string? maThat = null;
        try
        {
            // Mã đúng như trong database (SQL Server không phân biệt hoa thường)
            maThat = await _db.Customers.AsNoTracking()
                .Where(c => c.CustomerId == ma)
                .Select(c => c.CustomerId)
                .FirstOrDefaultAsync();
            if (maThat == null)
            {
                TempData["ThongBao"] = "Không tìm thấy khách hàng " + ma + ".";
                return RedirectToAction(nameof(Index));
            }

            PredictFeatures dacTrung = await LayDacTrungTuDbAsync(maThat);
            long maDuBao = await ChayDuBaoAsync(maThat, dacTrung, HttpContext.RequestAborted);
            return RedirectToAction(nameof(Result), new { id = maDuBao });
        }
        catch (LoiDuBaoException ex)
        {
            // Lỗi nghiệp vụ: báo lỗi ở trang chi tiết khách (nếu có) để nhân viên thấy ngay
            TempData["ThongBao"] = ex.Message;
            if (maThat != null) return RedirectToAction("Details", "Customers", new { id = maThat });
            return RedirectToAction(nameof(Index));
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi bất ngờ khi dự báo khách {CustomerId}", ma);
            TempData["ThongBao"] = "Hệ thống gặp sự cố khi dự báo, chưa có kết quả nào được lưu.";
            return RedirectToAction(nameof(Index));
        }
    }

    // ---------------------------------------------------------------
    // Nhập thủ công (FR-29)
    // ---------------------------------------------------------------
    [HttpGet]
    public IActionResult Manual()
    {
        return View(new PredictionManualModel());
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Manual(PredictionManualModel model)
    {
        // Kiểm TRƯỚC khi gọi API: sai thì báo từng trường và KHÔNG gọi API (UC-05, 3a)
        // Gọi hàm kiểm ở dòng riêng để biến dacTrung còn dùng được ở phía dưới
        // (biến out khai báo trong dòng foreach thì chỉ sống trong foreach)
        var dsLoi = model.KiemTraNghiepVu(out PredictFeatures? dacTrung);
        foreach (var (truong, noiDung) in dsLoi)
        {
            ModelState.AddModelError(truong, noiDung);
        }
        if (!ModelState.IsValid || dacTrung == null) return View(model);

        try
        {
            // CustomerID = null: dòng lưu có InputJson hợp lệ (BR-07)
            long maDuBao = await ChayDuBaoAsync(null, dacTrung, HttpContext.RequestAborted);
            return RedirectToAction(nameof(Result), new { id = maDuBao });
        }
        catch (LoiDuBaoException ex)
        {
            ModelState.AddModelError(string.Empty, ex.Message);
            return View(model);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi bất ngờ khi dự báo nhập thủ công");
            ModelState.AddModelError(string.Empty, "Hệ thống gặp sự cố khi dự báo, chưa có kết quả nào được lưu.");
            return View(model);
        }
    }

    // ---------------------------------------------------------------
    // Kết quả: ĐỌC LẠI dòng vừa lưu từ database (bằng chứng đã lưu thật)
    // ---------------------------------------------------------------
    [HttpGet]
    public async Task<IActionResult> Result(long id)
    {
        try
        {
            var dong = await _db.ChurnPredictions.AsNoTracking()
                .Where(p => p.PredictionId == id)
                .Select(p => new
                {
                    p.PredictionId,
                    p.CustomerId,
                    p.PredictionTime,
                    p.Probability,
                    p.RiskLevel,
                    p.InputJson,
                    ModelName = p.ModelVersion.ModelName,
                    Phien = p.ModelVersion.Version
                })
                .FirstOrDefaultAsync();

            if (dong == null)
            {
                TempData["ThongBao"] = "Không tìm thấy kết quả dự báo này.";
                return RedirectToAction(nameof(Index));
            }

            var model = new PredictionResultViewModel
            {
                PredictionId = dong.PredictionId,
                CustomerId = dong.CustomerId,
                PredictionTime = dong.PredictionTime,
                Probability = dong.Probability,
                RiskLevel = dong.RiskLevel,
                ModelName = dong.ModelName,
                ModelVersion = dong.Phien,
                DacTrung = NhatKyHienThi.DocJson(dong.InputJson) ?? new List<AuditValueRow>(),
                ApiMs = TempData["ApiMs"] as string,
                TongMs = TempData["TongMs"] as string
            };
            return View(model);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi tải kết quả dự báo {PredictionId}", id);
            return View("LoiHeThong");
        }
    }

    // ---------------------------------------------------------------
    // Lõi chung của hai cách dự báo. Trả về PredictionID đã LƯU; mọi lỗi nghiệp vụ ném LoiDuBaoException.
    // ---------------------------------------------------------------
    private async Task<long> ChayDuBaoAsync(string? customerId, PredictFeatures dacTrung, CancellationToken huy)
    {
        // Bước 1: đọc và kiểm ngưỡng TRƯỚC (hỏng thì khỏi tốn một lần gọi API) (UC-05, 6a)
        var cacDong = await _db.RiskConfigs.AsNoTracking()
            .Where(c => c.ConfigKey == NguongRuiRo.KhoaTrungBinh || c.ConfigKey == NguongRuiRo.KhoaCao)
            .ToListAsync();
        string? chuTb = cacDong.FirstOrDefault(c => c.ConfigKey == NguongRuiRo.KhoaTrungBinh)?.ConfigValue;
        string? chuCao = cacDong.FirstOrDefault(c => c.ConfigKey == NguongRuiRo.KhoaCao)?.ConfigValue;
        string? loiNguong = NguongRuiRo.DocHaiNguong(chuTb, chuCao, out decimal nguongTb, out decimal nguongCao);
        if (loiNguong != null) throw new LoiDuBaoException(loiNguong);

        // Bước 2: gọi FastAPI (chờ tối đa T giây, cấu hình ở appsettings.json)
        PredictionApiResult ketQua;
        try
        {
            ketQua = await _client.PredictAsync(dacTrung, huy);
        }
        catch (PredictionApiException ex)
        {
            throw new LoiDuBaoException(ex.Message);
        }

        // Bước 3: tra ModelVersionID theo Version (KHÔNG gán cứng, identity đã nhích)
        int? maMoHinh = await _db.ModelVersions.AsNoTracking()
            .Where(m => m.Version == ketQua.ModelVersion)
            .OrderByDescending(m => m.ModelVersionId)
            .Select(m => (int?)m.ModelVersionId)
            .FirstOrDefaultAsync();
        if (maMoHinh == null)
        {
            throw new LoiDuBaoException("Phiên bản mô hình \"" + ketQua.ModelVersion
                + "\" chưa được đăng ký trong cơ sở dữ liệu (chạy etl\\register_model.py). Chưa có kết quả nào được lưu.");
        }

        // Bước 4: làm tròn 8 chữ số như cột decimal(9,8) (giống score_batch.py) rồi gán mức theo ngưỡng
        decimal xacSuat = Math.Round((decimal)ketQua.ChurnProbability, 8);
        string mucRuiRo = NguongRuiRo.GanMuc(xacSuat, nguongTb, nguongCao);

        // Bước 5: lưu. Audit tự ghi trong cùng giao dịch (ChurnPrediction thuộc AuditedTypes).
        var dong = new ChurnPrediction
        {
            ModelVersionId = maMoHinh.Value,
            CustomerId = customerId,
            PredictionTime = DateTime.Now,
            Probability = xacSuat,
            RiskLevel = mucRuiRo,
            InputJson = JsonSerializer.Serialize(dacTrung)
        };
        _db.ChurnPredictions.Add(dong);
        try
        {
            await _db.SaveChangesAsync();
        }
        catch (Exception ex)
        {
            // Mất SQL Server hoặc vi phạm ràng buộc: bỏ dòng đang chờ, báo "chưa lưu", KHÔNG báo thành công (FR-31)
            _db.ChangeTracker.Clear();
            _logger.LogError(ex, "Không lưu được ChurnPredictions");
            throw new LoiDuBaoException(LoiLuu);
        }

        // Hai số đo cho báo cáo (Z-08); đọc ở trang Result rồi tự hết
        TempData["ApiMs"] = ketQua.ApiLatencyMs.ToString("0.00", CultureInfo.InvariantCulture);
        TempData["TongMs"] = ketQua.TongMs.ToString("0.00", CultureInfo.InvariantCulture);
        return dong.PredictionId;
    }

    // ---------------------------------------------------------------
    // Đọc 19 đặc trưng từ database (G1b): Customers + CustomerContracts đang hiệu lực + CustomerSnapshots
    // ---------------------------------------------------------------
    private async Task<PredictFeatures> LayDacTrungTuDbAsync(string customerId)
    {
        var khach = await _db.Customers.AsNoTracking().FirstAsync(c => c.CustomerId == customerId);

        // BR-14: khách thêm qua Web/CSV chưa có snapshot, tức chưa có tenure và TotalCharges (UC-05, 2a)
        var snapshot = await _db.CustomerSnapshots.AsNoTracking()
            .Where(s => s.CustomerId == customerId)
            .OrderByDescending(s => s.SnapshotDate)
            .FirstOrDefaultAsync();
        if (snapshot == null)
        {
            throw new LoiDuBaoException(
                "Khách chưa đủ dữ liệu để dự báo từ CSDL (thiếu số tháng sử dụng và tổng phí). Hãy dùng \"Nhập thủ công\".");
        }

        // BR-04: phải đúng MỘT dòng hợp đồng đang hiệu lực (UC-05, 2b)
        var cacHopDong = await _db.CustomerContracts.AsNoTracking()
            .Where(k => k.CustomerId == customerId && k.EffectiveTo == null)
            .ToListAsync();
        if (cacHopDong.Count != 1)
        {
            throw new LoiDuBaoException("Dữ liệu lỗi: khách có " + cacHopDong.Count
                + " dòng hợp đồng đang hiệu lực (phải đúng 1), không dự báo được.");
        }
        var hopDong = cacHopDong[0];

        if (khach.Gender == null || khach.Partner == null || khach.Dependents == null)
        {
            throw new LoiDuBaoException(
                "Hồ sơ khách thiếu giới tính, bạn đời hoặc người phụ thuộc nên không dự báo từ CSDL được. Hãy dùng \"Nhập thủ công\".");
        }

        return new PredictFeatures
        {
            SeniorCitizen = khach.SeniorCitizen ? 1 : 0,
            Tenure = snapshot.Tenure,
            MonthlyCharges = hopDong.MonthlyCharges,      // lấy từ hợp đồng đang hiệu lực (G1b)
            TotalCharges = snapshot.TotalCharges,         // null được phép, API điền trung vị
            Gender = khach.Gender,
            Partner = khach.Partner.Value ? "Yes" : "No", // bit -> chữ, API không nhận bit
            Dependents = khach.Dependents.Value ? "Yes" : "No",
            PhoneService = hopDong.PhoneService,
            MultipleLines = hopDong.MultipleLines,
            InternetService = hopDong.InternetService,
            OnlineSecurity = hopDong.OnlineSecurity,
            OnlineBackup = hopDong.OnlineBackup,
            DeviceProtection = hopDong.DeviceProtection,
            TechSupport = hopDong.TechSupport,
            StreamingTv = hopDong.StreamingTv,
            StreamingMovies = hopDong.StreamingMovies,
            Contract = hopDong.Contract,
            PaperlessBilling = hopDong.PaperlessBilling,
            PaymentMethod = hopDong.PaymentMethod
        };
    }
}