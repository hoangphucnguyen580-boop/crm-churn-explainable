using CrmChurn.Web.Data;
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

// Quyền chặn ở máy chủ (R-11): Agent, Manager, Admin đều xem được
[Authorize(Roles = "Agent,Manager,Admin")]
public partial class CustomersController : Controller
{
    private const int KichThuocTrang = 20;   // NFR-06: danh sách có phân trang

    private readonly CrmDbContext _db;
    private readonly ILogger<CustomersController> _logger;

    public CustomersController(CrmDbContext db, ILogger<CustomersController> logger)
    {
        _db = db;
        _logger = logger;
    }

    // Danh sách: tìm theo CustomerID, lọc theo hợp đồng / nhóm tenure / mức rủi ro
    [HttpGet]
    public async Task<IActionResult> Index(string? q, string? contract, string? tenureGroup,
                                           string? risk, int page = 1)
    {
        q = q?.Trim();
        if (page < 1) page = 1;

        try
        {
            IQueryable<Customer> query = _db.Customers.AsNoTracking();

            // Tìm theo CustomerID (khớp một phần, không phân biệt hoa thường theo collation mặc định)
            if (!string.IsNullOrEmpty(q))
            {
                query = query.Where(c => c.CustomerId.Contains(q));
            }

            // Lọc theo hợp đồng ĐANG HIỆU LỰC (EffectiveTo = NULL) của bảng nghiệp vụ
            if (contract != null && CustomerListViewModel.CacHopDong.Contains(contract))
            {
                string hopDong = contract;
                query = query.Where(c => c.CustomerContracts
                    .Any(k => k.EffectiveTo == null && k.Contract == hopDong));
            }

            // Lọc theo nhóm tenure (tenure nằm ở snapshot)
            var nhom = NhomTenure.DanhSach.FirstOrDefault(n => n.Khoa == tenureGroup);
            if (nhom.Khoa != null)
            {
                int tu = nhom.Min;
                int den = nhom.Max;
                query = query.Where(c => c.CustomerSnapshots.Any(s => s.Tenure >= tu && s.Tenure <= den));
            }

            // Lọc theo mức rủi ro của dự báo GẦN NHẤT ("None" = chưa có dự báo)
            if (risk == "None")
            {
                query = query.Where(c => !c.ChurnPredictions.Any());
            }
            else if (risk != null && CustomerListViewModel.CacMucRuiRo.Contains(risk))
            {
                string mucRuiRo = risk;
                query = query.Where(c => c.ChurnPredictions
                    .OrderByDescending(p => p.PredictionTime)
                    .ThenByDescending(p => p.PredictionId)
                    .Select(p => p.RiskLevel)
                    .FirstOrDefault() == mucRuiRo);
            }

            int tong = await query.CountAsync();
            int tongTrang = Math.Max(1, (int)Math.Ceiling(tong / (double)KichThuocTrang));
            if (page > tongTrang) page = tongTrang;

            // Chỉ lấy đúng các cột cần hiện, một trang 20 dòng
            var dong = await query
                .OrderBy(c => c.CustomerId)
                .Skip((page - 1) * KichThuocTrang)
                .Take(KichThuocTrang)
                .Select(c => new
                {
                    c.CustomerId,
                    c.CustomerStatus,
                    Contract = c.CustomerContracts
                        .Where(k => k.EffectiveTo == null)
                        .Select(k => k.Contract)
                        .FirstOrDefault(),
                    Tenure = c.CustomerSnapshots
                        .OrderByDescending(s => s.SnapshotDate)
                        .Select(s => (int?)s.Tenure)
                        .FirstOrDefault(),
                    Risk = c.ChurnPredictions
                        .OrderByDescending(p => p.PredictionTime)
                        .ThenByDescending(p => p.PredictionId)
                        .Select(p => p.RiskLevel)
                        .FirstOrDefault()
                })
                .ToListAsync();

            var model = new CustomerListViewModel
            {
                Q = q,
                Contract = contract,
                TenureGroup = tenureGroup,
                Risk = risk,
                Page = page,
                PageSize = KichThuocTrang,
                TongSoKhach = tong,
                Items = dong.Select(d => new CustomerListItem
                {
                    CustomerId = d.CustomerId,
                    CustomerStatus = d.CustomerStatus,
                    Contract = d.Contract,
                    Tenure = d.Tenure,
                    RiskLevel = d.Risk
                }).ToList()
            };
            return View(model);
        }
        catch (Exception ex)
        {
            // Không hiện danh sách rỗng giả: báo lỗi rõ ràng, ghi log kỹ thuật
            _logger.LogError(ex, "Lỗi khi tải danh sách khách hàng");
            return View("LoiHeThong");
        }
    }

    // Chi tiết một khách (FR-10)
    [HttpGet]
    public async Task<IActionResult> Details(string id)
    {
        try
        {
            var khach = await _db.Customers.AsNoTracking().FirstOrDefaultAsync(c => c.CustomerId == id);
            if (khach == null)
            {
                TempData["ThongBao"] = "Không tìm thấy khách hàng " + id + ".";
                return RedirectToAction(nameof(Index));
            }

            // Hợp đồng đang hiệu lực: phải đúng MỘT dòng (BR-04); khác 1 thì View báo dữ liệu lỗi
            var cacHopDong = await _db.CustomerContracts.AsNoTracking()
                .Where(k => k.CustomerId == id && k.EffectiveTo == null)
                .ToListAsync();

            int? tenure = await _db.CustomerSnapshots.AsNoTracking()
                .Where(s => s.CustomerId == id)
                .OrderByDescending(s => s.SnapshotDate)
                .Select(s => (int?)s.Tenure)
                .FirstOrDefaultAsync();

            // Dự báo gần nhất; chưa có thì null (View hiện "Chưa có dự báo")
            var duBao = await _db.ChurnPredictions.AsNoTracking()
                .Where(p => p.CustomerId == id)
                .OrderByDescending(p => p.PredictionTime)
                .ThenByDescending(p => p.PredictionId)
                .Select(p => new PredictionRow
                {
                    PredictionTime = p.PredictionTime,
                    Probability = p.Probability,
                    RiskLevel = p.RiskLevel,
                    ModelName = p.ModelVersion.ModelName,
                    ModelVersion = p.ModelVersion.Version
                })
                .FirstOrDefaultAsync();

            // 10 tương tác gần nhất. Chọn đúng cột cần, KHÔNG nạp cả entity Staff (có PasswordHash)
            int tongTuongTac = await _db.Interactions.CountAsync(i => i.CustomerId == id);
            var tuongTac = await _db.Interactions.AsNoTracking()
                .Where(i => i.CustomerId == id)
                .OrderByDescending(i => i.InteractionDate)
                .Take(10)
                .Select(i => new InteractionRow
                {
                    InteractionDate = i.InteractionDate,
                    Channel = i.Channel,
                    InteractionType = i.InteractionType,
                    Description = i.Description,
                    Result = i.Result,
                    StaffName = i.Staff != null ? i.Staff.FullName : null,
                    IsSimulated = i.IsSimulated
                })
                .ToListAsync();

            int tongTicket = await _db.Tickets.CountAsync(t => t.CustomerId == id);
            var tickets = await _db.Tickets.AsNoTracking()
                .Where(t => t.CustomerId == id)
                .OrderByDescending(t => t.CreatedAt)
                .Take(10)
                .Select(t => new TicketRow
                {
                    TicketId = t.TicketId,
                    CreatedAt = t.CreatedAt,
                    ClosedAt = t.ClosedAt,
                    Category = t.Category,
                    Priority = t.Priority,
                    Status = t.Status,
                    SatisfactionScore = t.SatisfactionScore,
                    AssignedName = t.AssignedStaff != null ? t.AssignedStaff.FullName : null,
                    IsSimulated = t.IsSimulated
                })
                .ToListAsync();

            var model = new CustomerDetailViewModel
            {
                Customer = khach,
                Tenure = tenure,
                SoDongHopDongHieuLuc = cacHopDong.Count,
                HopDong = cacHopDong.Count == 1 ? cacHopDong[0] : null,
                DuBaoGanNhat = duBao,
                TuongTac = tuongTac,
                TongTuongTac = tongTuongTac,
                Tickets = tickets,
                TongTicket = tongTicket
            };
            return View(model);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi tải chi tiết khách hàng {CustomerId}", id);
            return View("LoiHeThong");
        }
    }
}