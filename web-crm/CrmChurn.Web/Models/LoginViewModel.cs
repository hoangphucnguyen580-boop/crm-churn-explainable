// ============================================================
// File: Models/LoginViewModel.cs
// Mục đích: Dữ liệu form đăng nhập
// ============================================================
using System.ComponentModel.DataAnnotations;

namespace CrmChurn.Web.Models;

public class LoginViewModel
{
    [Required(ErrorMessage = "Nhập tên đăng nhập")]
    [Display(Name = "Tên đăng nhập")]
    public string Username { get; set; } = string.Empty;

    [Required(ErrorMessage = "Nhập mật khẩu")]
    [DataType(DataType.Password)]
    [Display(Name = "Mật khẩu")]
    public string Password { get; set; } = string.Empty;
}