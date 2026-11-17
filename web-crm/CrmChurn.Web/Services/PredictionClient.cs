using System.Diagnostics;
using System.Text;
using System.Text.Json;
using CrmChurn.Web.Models;

namespace CrmChurn.Web.Services;

public class PredictionApiException : Exception
{
    public PredictionApiException(string message, Exception? inner = null) : base(message, inner) { }
}

public class PredictionApiResult
{
    public double ChurnProbability { get; set; }
    public string ModelVersion { get; set; } = "";
    public double ApiLatencyMs { get; set; }   // latency_ms do API tự báo
    public double TongMs { get; set; }         // đo bằng Stopwatch phía Web (Z-08)
}

public class PredictionClient
{
    private readonly HttpClient _http;
    private readonly ILogger<PredictionClient> _logger;

    // HttpClient được AddHttpClient<PredictionClient> tiêm vào (đã đặt BaseAddress và Timeout ở Program.cs)
    public PredictionClient(HttpClient http, ILogger<PredictionClient> logger)
    {
        _http = http;
        _logger = logger;
    }

    public async Task<PredictionApiResult> PredictAsync(PredictFeatures dacTrung, CancellationToken huy = default)
    {
        string noiDung = JsonSerializer.Serialize(dacTrung);
        using var yeuCau = new StringContent(noiDung, Encoding.UTF8, "application/json");

        var dongHo = Stopwatch.StartNew();
        HttpResponseMessage phanHoi;
        try
        {
            phanHoi = await _http.PostAsync("predict", yeuCau, huy);
        }
        catch (OperationCanceledException ex) when (!huy.IsCancellationRequested)
        {
            // Không phải người dùng hủy => hết thời gian chờ T
            _logger.LogWarning(ex, "Gọi /predict quá thời gian chờ");
            throw new PredictionApiException(
                "Dịch vụ dự báo không phản hồi kịp (quá thời gian chờ). Hãy kiểm tra FastAPI rồi thử lại.", ex);
        }
        catch (HttpRequestException ex)
        {
            // FastAPI chưa chạy, sai cổng, bị từ chối kết nối...
            _logger.LogWarning(ex, "Không kết nối được dịch vụ dự báo");
            throw new PredictionApiException(
                "Dịch vụ dự báo chưa sẵn sàng. Hãy bật FastAPI (python ml-api\\main.py) rồi thử lại.", ex);
        }

        using (phanHoi)
        {
            string thanBai = await phanHoi.Content.ReadAsStringAsync(huy);
            dongHo.Stop();

            int maTrangThai = (int)phanHoi.StatusCode;
            if (maTrangThai == 422)
            {
                _logger.LogWarning("FastAPI từ chối dữ liệu (422): {Body}", thanBai);
                throw new PredictionApiException("Dịch vụ dự báo từ chối dữ liệu đầu vào (lỗi 422). Chưa có kết quả nào được lưu.");
            }
            if (!phanHoi.IsSuccessStatusCode)
            {
                _logger.LogError("FastAPI trả lỗi {Code}: {Body}", maTrangThai, thanBai);
                throw new PredictionApiException("Dịch vụ dự báo gặp lỗi (HTTP " + maTrangThai + "). Chưa có kết quả nào được lưu.");
            }

            try
            {
                using JsonDocument tai = JsonDocument.Parse(thanBai);
                JsonElement goc = tai.RootElement;

                double xacSuat = goc.GetProperty("churn_probability").GetDouble();
                string phienBan = goc.GetProperty("model_version").GetString() ?? "";
                double doTreApi = goc.GetProperty("latency_ms").GetDouble();

                // Xác suất ngoài [0, 1] hoặc không phải số là lỗi của mô hình, không đi tiếp
                if (double.IsNaN(xacSuat) || double.IsInfinity(xacSuat) || xacSuat < 0 || xacSuat > 1 || phienBan == "")
                {
                    throw new PredictionApiException("Dịch vụ dự báo trả kết quả không hợp lệ. Chưa có kết quả nào được lưu.");
                }

                return new PredictionApiResult
                {
                    ChurnProbability = xacSuat,
                    ModelVersion = phienBan,
                    ApiLatencyMs = doTreApi,
                    TongMs = dongHo.Elapsed.TotalMilliseconds
                };
            }
            catch (Exception ex) when (ex is JsonException || ex is KeyNotFoundException
                                       || ex is InvalidOperationException || ex is FormatException)
            {
                _logger.LogError(ex, "Không đọc được phản hồi của FastAPI: {Body}", thanBai);
                throw new PredictionApiException("Dịch vụ dự báo trả dữ liệu sai định dạng. Chưa có kết quả nào được lưu.", ex);
            }
        }
    }
}