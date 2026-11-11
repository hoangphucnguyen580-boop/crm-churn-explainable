using System.Text;
using System.Text.RegularExpressions;
using CrmChurn.Web.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace CrmChurn.Web.Controllers;

// Cùng class với CustomersController (partial): dùng chung _db, _logger, LayStaffId()
public partial class CustomersController
{
    private const string LoiKetNoiCsv = "Không kết nối được cơ sở dữ liệu, chưa có dòng nào được nhập. Hãy thử lại sau.";

    // Một dòng CSV sau khi đọc và kiểm
    private sealed class DongDaKiem
    {
        public int SoDong;
        public string CustomerId = "";
        public bool SeniorCitizen;
        public bool Partner;
        public bool Dependents;
        public decimal MucPhi;
        public CustomerCreateViewModel Model = new CustomerCreateViewModel();
        public List<string> Loi = new List<string>();
    }

    // ---------------------------------------------------------------
    // GET: trang nhập CSV
    // ---------------------------------------------------------------
    [Authorize(Roles = "Manager,Admin")]
    [HttpGet]
    public IActionResult Import()
    {
        return View(new CsvImportPageViewModel());
    }

    // ---------------------------------------------------------------
    // GET: tải tệp mẫu (UTF-8 có BOM để Excel đọc đúng; dấu phẩy; mức phí viết 29.85)
    // ---------------------------------------------------------------
    [Authorize(Roles = "Manager,Admin")]
    [HttpGet]
    public IActionResult ImportTemplate()
    {
        string tieuDe = string.Join(",", CsvImportConfig.CacCot);
        string dongMau = "MAU-0001,Female,0,Yes,No,Yes,No,DSL,No,Yes,No,No,No,No,Month-to-month,Yes,Electronic check,29.85";
        string noiDung = tieuDe + "\r\n" + dongMau + "\r\n";

        var utf8CoBom = new UTF8Encoding(true);
        byte[] phanDau = utf8CoBom.GetPreamble();
        byte[] phanThan = utf8CoBom.GetBytes(noiDung);
        byte[] tatCa = phanDau.Concat(phanThan).ToArray();
        return File(tatCa, "text/csv", "mau_nhap_khach_hang.csv");
    }

    // ---------------------------------------------------------------
    // POST: nhận tệp, kiểm, lưu từng dòng, báo kết quả
    // ---------------------------------------------------------------
    [Authorize(Roles = "Manager,Admin")]
    [HttpPost]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Import(IFormFile? tep)
    {
        var trang = new CsvImportPageViewModel();

        // ----- Bước 1: kiểm tệp (rỗng, quá lớn, sai đuôi) -----
        if (tep == null || tep.Length == 0)
        {
            trang.ThongBaoLoi = "Hãy chọn một tệp CSV có nội dung.";
            return View(trang);
        }
        if (tep.Length > CsvImportConfig.MaxBytes)
        {
            trang.ThongBaoLoi = "Tệp lớn hơn " + (CsvImportConfig.MaxBytes / 1024) + " KB. Hãy chia nhỏ tệp rồi nhập lại.";
            return View(trang);
        }
        // Chỉ dùng tên tệp để kiểm đuôi, không dùng để lưu hay đường dẫn (tài liệu Microsoft cảnh báo)
        if (!Path.GetExtension(tep.FileName).Equals(".csv", StringComparison.OrdinalIgnoreCase))
        {
            trang.ThongBaoLoi = "Chỉ nhận tệp có đuôi .csv.";
            return View(trang);
        }

        // ----- Bước 2: đọc toàn bộ tệp (UTF-8, tự nhận BOM) -----
        string noiDung;
        try
        {
            using (var docTep = new StreamReader(tep.OpenReadStream(), Encoding.UTF8, true))
            {
                noiDung = await docTep.ReadToEndAsync();
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Không đọc được tệp CSV");
            trang.ThongBaoLoi = "Không đọc được tệp. Hãy kiểm tra tệp rồi thử lại.";
            return View(trang);
        }

        // ----- Bước 3: tách ô theo dấu phẩy hoặc chấm phẩy (đoán từ dòng tiêu đề) -----
        char phanCach = DoanDauPhanCach(noiDung);
        bool ngoacChuaDong;
        List<List<string>> cacDong = DocCsv(noiDung, phanCach, out ngoacChuaDong);
        if (ngoacChuaDong)
        {
            trang.ThongBaoLoi = "Tệp sai cấu trúc: có dấu ngoặc kép mở nhưng không đóng. Không có dòng nào được nhập.";
            return View(trang);
        }
        if (cacDong.Count == 0 || LaDongTrong(cacDong[0]))
        {
            trang.ThongBaoLoi = "Tệp không có dòng tiêu đề. Hãy dùng tệp mẫu.";
            return View(trang);
        }

        // ----- Bước 4: kiểm dòng tiêu đề: đủ 18 cột đúng tên (thứ tự cột tùy ý) -----
        var viTri = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        List<string> tieuDe = cacDong[0];
        bool tieuDeTrung = false;
        for (int i = 0; i < tieuDe.Count; i++)
        {
            string ten = tieuDe[i].Trim().TrimStart('\uFEFF');
            if (!viTri.TryAdd(ten, i)) tieuDeTrung = true;
        }
        List<string> thieuCot = CsvImportConfig.CacCot.Where(c => !viTri.ContainsKey(c)).ToList();
        if (tieuDeTrung || thieuCot.Count > 0 || tieuDe.Count != CsvImportConfig.CacCot.Length)
        {
            string thongBao = "Dòng tiêu đề không đúng mẫu: cần đúng " + CsvImportConfig.CacCot.Length
                              + " cột, tên như tệp mẫu, không trùng, không thừa.";
            if (thieuCot.Count > 0) thongBao += " Thiếu cột: " + string.Join(", ", thieuCot) + ".";
            trang.ThongBaoLoi = thongBao + " Không có dòng nào được nhập.";
            return View(trang);
        }

        // ----- Bước 5: đếm dòng dữ liệu, kiểm giới hạn số dòng -----
        int tongDong = 0;
        for (int i = 1; i < cacDong.Count; i++)
        {
            if (!LaDongTrong(cacDong[i])) tongDong++;
        }
        if (tongDong == 0)
        {
            trang.ThongBaoLoi = "Tệp chỉ có dòng tiêu đề, không có dữ liệu.";
            return View(trang);
        }
        if (tongDong > CsvImportConfig.MaxRows)
        {
            trang.ThongBaoLoi = "Tệp có " + tongDong + " dòng, vượt giới hạn " + CsvImportConfig.MaxRows
                                + " dòng mỗi lần. Hãy chia nhỏ tệp. Không có dòng nào được nhập.";
            return View(trang);
        }

        // ----- Bước 6: kiểm từng dòng (chưa đụng database) -----
        var ketQua = new CsvImportResult { TongDong = tongDong };
        var cacUngVien = new List<DongDaKiem>();
        for (int i = 1; i < cacDong.Count; i++)
        {
            if (LaDongTrong(cacDong[i])) continue;

            // Số dòng trong tệp = vị trí + 1 (dòng tiêu đề là dòng 1)
            DongDaKiem dong = KiemTraMotDong(i + 1, cacDong[i], viTri);
            if (dong.Loi.Count > 0)
            {
                ketQua.Loi.Add(new CsvImportError
                {
                    Dong = dong.SoDong,
                    CustomerId = dong.CustomerId,
                    LyDo = string.Join(" ", dong.Loi)
                });
            }
            else
            {
                cacUngVien.Add(dong);
            }
        }

        // ----- Bước 7: một câu truy vấn lấy các mã đã có trong database -----
        HashSet<string> maDaCo;
        try
        {
            List<string> cacMa = cacUngVien.Select(d => d.CustomerId).ToList();
            List<string> maTrongDb = await _db.Customers.AsNoTracking()
                .Where(c => cacMa.Contains(c.CustomerId))
                .Select(c => c.CustomerId)
                .ToListAsync();
            // SQL Server mặc định không phân biệt hoa thường nên so sánh cũng không phân biệt
            maDaCo = new HashSet<string>(maTrongDb, StringComparer.OrdinalIgnoreCase);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Lỗi khi kiểm mã khách trùng lúc nhập CSV");
            trang.ThongBaoLoi = LoiKetNoiCsv;
            return View(trang);
        }

        // ----- Bước 8: loại dòng trùng mã (với database, và trong chính tệp: dòng đầu nhận, dòng sau bị từ chối) -----
        var cacCanLuu = new List<DongDaKiem>();
        var maDaNhan = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        foreach (DongDaKiem ungVien in cacUngVien)
        {
            if (maDaCo.Contains(ungVien.CustomerId))
            {
                ketQua.Loi.Add(new CsvImportError
                {
                    Dong = ungVien.SoDong,
                    CustomerId = ungVien.CustomerId,
                    LyDo = "Mã khách đã tồn tại trong hệ thống."
                });
                continue;
            }

            int dongDau;
            if (maDaNhan.TryGetValue(ungVien.CustomerId, out dongDau))
            {
                ketQua.Loi.Add(new CsvImportError
                {
                    Dong = ungVien.SoDong,
                    CustomerId = ungVien.CustomerId,
                    LyDo = "Trùng mã với dòng " + dongDau + " trong cùng tệp."
                });
                continue;
            }

            maDaNhan[ungVien.CustomerId] = ungVien.SoDong;
            cacCanLuu.Add(ungVien);
        }

        // ----- Bước 9: lưu từng dòng. Dòng nào lỗi thì bỏ riêng dòng đó, các dòng khác vẫn nhập -----
        int loiLienTiep = 0;
        bool daDung = false;
        foreach (DongDaKiem canLuu in cacCanLuu)
        {
            if (daDung)
            {
                ketQua.ChuaXuLy++;
                continue;
            }

            try
            {
                await LuuMotKhachAsync(canLuu);
                ketQua.ThanhCong++;
                loiLienTiep = 0;
            }
            catch (Exception ex)
            {
                // Bỏ hết thứ EF đang theo dõi, nếu không lần SaveChanges sau sẽ thử lưu lại dòng hỏng này
                _db.ChangeTracker.Clear();
                _logger.LogError(ex, "Lỗi khi lưu khách {CustomerId} từ dòng {SoDong} của tệp CSV", canLuu.CustomerId, canLuu.SoDong);
                ketQua.Loi.Add(new CsvImportError
                {
                    Dong = canLuu.SoDong,
                    CustomerId = canLuu.CustomerId,
                    LyDo = "Lỗi khi lưu vào cơ sở dữ liệu, dòng này không được nhập."
                });
                loiLienTiep++;
                if (loiLienTiep >= CsvImportConfig.MaxConsecutiveSaveFailures) daDung = true;
            }
        }

        ketQua.Loi = ketQua.Loi.OrderBy(l => l.Dong).ToList();
        trang.KetQua = ketQua;
        if (daDung)
        {
            trang.ThongBaoLoi = "Lưu lỗi liên tiếp " + CsvImportConfig.MaxConsecutiveSaveFailures
                                + " lần nên đã dừng. Các dòng còn lại chưa được xử lý, hãy thử lại sau.";
        }
        return View(trang);
    }

    // ---------------------------------------------------------------
    // Lưu một khách: Customers + CustomerContracts đang hiệu lực, cùng MỘT lần SaveChangesAsync
    // (giống Create; audit tự ghi qua CrmDbContext.Audit.cs)
    // ---------------------------------------------------------------
    private async Task LuuMotKhachAsync(DongDaKiem d)
    {
        var khach = new Customer
        {
            CustomerId = d.CustomerId,
            Gender = d.Model.Gender,
            SeniorCitizen = d.SeniorCitizen,
            Partner = d.Partner,
            Dependents = d.Dependents,
            CustomerStatus = DanhMucTelco.TrangThaiHoatDong
            // EstimatedJoinDate để NULL: chỉ khách IBM mới có ngày ước lượng
        };
        khach.CustomerContracts.Add(new CustomerContract
        {
            EffectiveFrom = DateTime.Now,
            UpdatedByStaffId = LayStaffId(),
            PhoneService = d.Model.PhoneService!,
            MultipleLines = d.Model.MultipleLines!,
            InternetService = d.Model.InternetService!,
            OnlineSecurity = d.Model.OnlineSecurity!,
            OnlineBackup = d.Model.OnlineBackup!,
            DeviceProtection = d.Model.DeviceProtection!,
            TechSupport = d.Model.TechSupport!,
            StreamingTv = d.Model.StreamingTv!,
            StreamingMovies = d.Model.StreamingMovies!,
            Contract = d.Model.Contract!,
            PaperlessBilling = d.Model.PaperlessBilling!,
            PaymentMethod = d.Model.PaymentMethod!,
            MonthlyCharges = d.MucPhi
        });
        _db.Customers.Add(khach);
        await _db.SaveChangesAsync();

        // Lưu xong thì bỏ theo dõi để 1.000 dòng không làm ChangeTracker phình to và chậm dần
        _db.ChangeTracker.Clear();
    }

    // ---------------------------------------------------------------
    // Kiểm một dòng: đủ giá trị, mã khách đúng dạng, SeniorCitizen 0/1, Partner/Dependents Yes/No,
    // rồi dùng lại bộ kiểm của form thêm khách (danh sách giá trị, BR-15, mức phí)
    // ---------------------------------------------------------------
    private static DongDaKiem KiemTraMotDong(int soDong, List<string> o, Dictionary<string, int> viTri)
    {
        var dong = new DongDaKiem { SoDong = soDong };

        // Đọc mã khách trước để dòng lỗi vẫn hiện được mã (nếu có)
        int viTriMa = viTri["CustomerID"];
        if (viTriMa < o.Count) dong.CustomerId = o[viTriMa].Trim();

        if (o.Count != CsvImportConfig.CacCot.Length)
        {
            dong.Loi.Add("Dòng có " + o.Count + " cột, cần đúng " + CsvImportConfig.CacCot.Length
                         + " cột (mức phí kiểu 29,85 phải bỏ trong ngoặc kép nếu tệp dùng dấu phẩy).");
            return dong;
        }

        // Thiếu giá trị ở cột nào
        var thieu = new List<string>();
        foreach (string ten in CsvImportConfig.CacCot)
        {
            if (LayO(o, viTri, ten) == "") thieu.Add(ten);
        }
        if (thieu.Count > 0)
        {
            dong.Loi.Add("Thiếu giá trị ở cột: " + string.Join(", ", thieu) + ".");
            return dong;
        }

        // Mã khách: tối đa 20 ký tự, chỉ chữ, số, gạch ngang (giống form thêm khách)
        if (dong.CustomerId.Length > 20)
        {
            dong.Loi.Add("CustomerID dài quá 20 ký tự.");
        }
        else if (!Regex.IsMatch(dong.CustomerId, @"^[A-Za-z0-9\-]+$"))
        {
            dong.Loi.Add("CustomerID chỉ gồm chữ, số và dấu gạch ngang (không có dấu cách).");
        }

        // SeniorCitizen giữ 0/1 như Telco
        string senior = LayO(o, viTri, "SeniorCitizen");
        if (senior != "0" && senior != "1") dong.Loi.Add("SeniorCitizen phải là 0 hoặc 1.");
        else dong.SeniorCitizen = senior == "1";

        // Partner, Dependents là Yes/No
        string partner = LayO(o, viTri, "Partner");
        if (partner != "Yes" && partner != "No") dong.Loi.Add("Partner phải là Yes hoặc No.");
        else dong.Partner = partner == "Yes";

        string dependents = LayO(o, viTri, "Dependents");
        if (dependents != "Yes" && dependents != "No") dong.Loi.Add("Dependents phải là Yes hoặc No.");
        else dong.Dependents = dependents == "Yes";

        // Đổ vào model của form thêm khách rồi dùng lại bộ kiểm (danh sách giá trị, BR-15, mức phí)
        dong.Model.CustomerId = dong.CustomerId;
        dong.Model.Gender = LayO(o, viTri, "Gender");
        dong.Model.PhoneService = LayO(o, viTri, "PhoneService");
        dong.Model.MultipleLines = LayO(o, viTri, "MultipleLines");
        dong.Model.InternetService = LayO(o, viTri, "InternetService");
        dong.Model.OnlineSecurity = LayO(o, viTri, "OnlineSecurity");
        dong.Model.OnlineBackup = LayO(o, viTri, "OnlineBackup");
        dong.Model.DeviceProtection = LayO(o, viTri, "DeviceProtection");
        dong.Model.TechSupport = LayO(o, viTri, "TechSupport");
        dong.Model.StreamingTv = LayO(o, viTri, "StreamingTV");
        dong.Model.StreamingMovies = LayO(o, viTri, "StreamingMovies");
        dong.Model.Contract = LayO(o, viTri, "Contract");
        dong.Model.PaperlessBilling = LayO(o, viTri, "PaperlessBilling");
        dong.Model.PaymentMethod = LayO(o, viTri, "PaymentMethod");
        dong.Model.MonthlyChargesText = LayO(o, viTri, "MonthlyCharges");

        decimal mucPhi;
        List<(string Truong, string NoiDung)> dsLoi = dong.Model.KiemTraNghiepVu(out mucPhi);
        foreach (var (truong, noiDung) in dsLoi)
        {
            dong.Loi.Add(TenCot(truong) + ": " + noiDung);
        }
        dong.MucPhi = mucPhi;
        return dong;
    }

    // Lấy giá trị một ô theo tên cột (đã cắt khoảng trắng)
    private static string LayO(List<string> o, Dictionary<string, int> viTri, string tenCot)
    {
        int vt = viTri[tenCot];
        return vt < o.Count ? o[vt].Trim() : "";
    }

    // Đổi tên thuộc tính của model về tên cột trong tệp để lời báo dễ hiểu
    private static string TenCot(string tenThuocTinh)
    {
        if (tenThuocTinh == "StreamingTv") return "StreamingTV";
        if (tenThuocTinh == "MonthlyChargesText") return "MonthlyCharges";
        return tenThuocTinh;
    }

    private static bool LaDongTrong(List<string> o)
    {
        return o.All(x => string.IsNullOrWhiteSpace(x));
    }

    // Đoán dấu phân cách từ dòng đầu: nhiều chấm phẩy hơn dấu phẩy thì dùng chấm phẩy
    // (Excel tiếng Việt thường lưu CSV bằng chấm phẩy)
    private static char DoanDauPhanCach(string noiDung)
    {
        int viTriXuongDong = noiDung.IndexOfAny(new[] { '\r', '\n' });
        string dongDau = viTriXuongDong < 0 ? noiDung : noiDung.Substring(0, viTriXuongDong);
        int soPhay = dongDau.Count(c => c == ',');
        int soChamPhay = dongDau.Count(c => c == ';');
        return soChamPhay > soPhay ? ';' : ',';
    }

    // Bộ đọc CSV: hiểu ô bọc ngoặc kép, "" là một dấu ngoặc kép, ô có thể chứa dấu phân cách.
    // Trả về danh sách dòng, mỗi dòng là danh sách ô. Dòng trống vẫn được giữ để số dòng khớp với tệp.
    private static List<List<string>> DocCsv(string text, char phanCach, out bool ngoacChuaDong)
    {
        var cacDong = new List<List<string>>();
        var dongHienTai = new List<string>();
        var oHienTai = new StringBuilder();
        bool trongNgoacKep = false;
        int i = 0;

        while (i < text.Length)
        {
            char c = text[i];

            if (trongNgoacKep)
            {
                if (c == '"')
                {
                    // "" trong ô nghĩa là một dấu ngoặc kép thật
                    if (i + 1 < text.Length && text[i + 1] == '"')
                    {
                        oHienTai.Append('"');
                        i += 2;
                        continue;
                    }
                    trongNgoacKep = false;
                    i++;
                    continue;
                }
                oHienTai.Append(c);
                i++;
                continue;
            }

            if (c == '"')
            {
                trongNgoacKep = true;
                i++;
                continue;
            }
            if (c == phanCach)
            {
                dongHienTai.Add(oHienTai.ToString());
                oHienTai.Clear();
                i++;
                continue;
            }
            if (c == '\r' || c == '\n')
            {
                // \r\n tính là MỘT lần xuống dòng
                if (c == '\r' && i + 1 < text.Length && text[i + 1] == '\n') i++;
                i++;
                dongHienTai.Add(oHienTai.ToString());
                oHienTai.Clear();
                cacDong.Add(dongHienTai);
                dongHienTai = new List<string>();
                continue;
            }

            oHienTai.Append(c);
            i++;
        }

        // Dòng cuối không có ký tự xuống dòng
        if (oHienTai.Length > 0 || dongHienTai.Count > 0)
        {
            dongHienTai.Add(oHienTai.ToString());
            cacDong.Add(dongHienTai);
        }

        ngoacChuaDong = trongNgoacKep;
        return cacDong;
    }
}