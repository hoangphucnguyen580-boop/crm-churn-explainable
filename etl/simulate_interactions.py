"""
Sinh dữ liệu MÔ PHỎNG cho bảng Interactions và Tickets (đề tài 18, Mức 1).

Vì sao có script này: IBM Telco KHÔNG có lịch sử tương tác và ticket, nên CRM phải
có dữ liệu mô phỏng để demo chức năng. Mọi dòng sinh ra đều có IsSimulated = 1
(L4) và KHÔNG được dùng để huấn luyện hay đánh giá mô hình ML ở Mức 1 (L3, D-04).

Quy tắc cứng đã cài vào code:
  - Seed cố định (42), mọi tham số nằm trong etl/simulation_config.json (L1, R-05).
  - KHÔNG đọc nhãn Churn khi sinh dữ liệu (L2). Script chỉ đọc CustomerID và
    EstimatedJoinDate từ bảng Customers. Mỗi khách có bộ sinh số ngẫu nhiên riêng,
    nên kết quả không phụ thuộc thứ tự khách và không phụ thuộc "hôm nay" (L5).
  - Mỗi khách có 5 đến 20 tương tác và 0 đến 5 ticket.
  - Thời gian nằm trong [max(EstimatedJoinDate, SnapshotDate - 730 ngày), hết ngày SnapshotDate].
  - Ticket: ClosedAt chỉ có khi Status = 'Closed', ClosedAt >= CreatedAt,
    SatisfactionScore (1 đến 5) chỉ có ở ticket Closed (L7).
  - StaffID và AssignedStaffID để NULL (bảng Staff chưa seed, sẽ seed lúc dựng web).
  - Từ chối chạy nếu Interactions hoặc Tickets đã có dòng (script KHÔNG xóa gì).
  - Ghi trong MỘT transaction, tự kiểm lại (L8); sai một mục là ROLLBACK.
  - Kiểm xong thì ghi báo cáo vào ml/results/simulation_report.txt (đưa vào gói nộp).

Chạy thật:   python simulate_interactions.py
Chạy thử:    python simulate_interactions.py --dry-run   (sinh và kiểm trong bộ nhớ, KHÔNG ghi database)
Cần:         pip install pandas pyodbc   (load_telco.py phải nằm cạnh file này)
Đặt file này ở:  <thư mục dự án>/etl/simulate_interactions.py
"""

import json
import platform
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import load_telco

PROJECT_ROOT = load_telco.PROJECT_ROOT
SIMULATION_CONFIG_FILE = PROJECT_ROOT / "etl" / "simulation_config.json"
REPORT_FILE = PROJECT_ROOT / "ml" / "results" / "simulation_report.txt"

# Số dòng ghi mỗi lần gọi executemany (chỉ để in tiến độ, không ảnh hưởng kết quả)
INSERT_CHUNK_SIZE = 5000

MAX_TICKETS_PER_CUSTOMER = 5

# Cột của hai bảng đích. KHÔNG có StaffID, AssignedStaffID, ReopenReason:
# để SQL Server tự điền NULL (bảng Staff chưa seed; dữ liệu mô phỏng không có mở lại ticket).
INTERACTION_COLUMNS = [
    "CustomerID", "InteractionDate", "Channel", "InteractionType",
    "Description", "Result", "IsSimulated",
]
TICKET_COLUMNS = [
    "CustomerID", "CreatedAt", "ClosedAt", "Category", "Priority",
    "Status", "Resolution", "SatisfactionScore", "IsSimulated",
]


# ---------------------------------------------------------------
# 1. Đọc và kiểm file cấu hình
# ---------------------------------------------------------------

def load_simulation_config():
    """Đọc simulation_config.json và kiểm tra hợp lệ. Sai thì ném ValueError."""
    with open(SIMULATION_CONFIG_FILE, "r", encoding="utf-8") as file:
        simulation_config = json.load(file)
    validate_simulation_config(simulation_config)
    return simulation_config


def validate_simulation_config(simulation_config):
    """Kiểm tên nhóm giá trị, trọng số và khoảng số. Sai thì dừng trước khi sinh gì."""
    # Mỗi khóa trọng số phải có ĐÚNG các giá trị cho phép (khớp CHECK của database)
    expected_names = {
        "channel_weights": {"Phone", "Email", "Chat", "Web"},
        "interaction_type_weights": {"Inquiry", "Support", "Complaint", "Renewal"},
        "interaction_result_weights": {"Resolved", "Follow-up", "Escalated"},
        "ticket_category_weights": {"Billing", "Technical", "Service"},
        "ticket_priority_weights": {"Low", "Medium", "High"},
        "ticket_status_weights": {"Open", "InProgress", "Closed"},
        "satisfaction_score_weights": {"1", "2", "3", "4", "5"},
    }
    for key_name, names in expected_names.items():
        found_names = set(simulation_config[key_name].keys())
        if found_names != names:
            raise ValueError(
                "Cấu hình " + key_name + " phải có đúng các giá trị " + str(sorted(names))
                + ", đang có " + str(sorted(found_names))
            )
        weights = list(simulation_config[key_name].values())
        if min(weights) < 0 or sum(weights) <= 0:
            raise ValueError("Cấu hình " + key_name + ": trọng số phải >= 0 và tổng > 0")

    ticket_weights = simulation_config["tickets_per_customer_weights"]
    if len(ticket_weights) != MAX_TICKETS_PER_CUSTOMER + 1:
        raise ValueError("tickets_per_customer_weights phải có đúng 6 phần tử (0 đến 5 ticket)")
    if min(ticket_weights) < 0 or sum(ticket_weights) <= 0:
        raise ValueError("tickets_per_customer_weights: trọng số phải >= 0 và tổng > 0")

    interaction_range = simulation_config["interactions_per_customer"]
    if not (5 <= interaction_range["min"] <= interaction_range["max"] <= 20):
        raise ValueError("interactions_per_customer phải thỏa 5 <= min <= max <= 20")

    probability = simulation_config["satisfaction_given_probability"]
    if not (0 <= probability <= 1):
        raise ValueError("satisfaction_given_probability phải thuộc [0, 1]")

    if set(simulation_config["resolution_hours"].keys()) != expected_names["ticket_priority_weights"]:
        raise ValueError("resolution_hours phải có đúng 3 mức ưu tiên Low, Medium, High")
    for priority_name, hour_range in simulation_config["resolution_hours"].items():
        if not (0 < hour_range[0] < hour_range[1]):
            raise ValueError("resolution_hours[" + priority_name + "] phải có dạng [nhỏ, lớn] dương")

    if set(simulation_config["descriptions"].keys()) != expected_names["interaction_type_weights"]:
        raise ValueError("descriptions phải có đủ 4 loại tương tác")
    if set(simulation_config["resolutions"].keys()) != expected_names["ticket_category_weights"]:
        raise ValueError("resolutions phải có đủ 3 loại ticket")
    for text_list in list(simulation_config["descriptions"].values()) + list(simulation_config["resolutions"].values()):
        if len(text_list) == 0:
            raise ValueError("Mỗi nhóm mô tả/giải quyết phải có ít nhất một câu")
        for text in text_list:
            if len(text) > 1000:
                raise ValueError("Có câu mô tả dài hơn 1000 ký tự (cột nvarchar(1000))")


# ---------------------------------------------------------------
# 2. Sinh dữ liệu (không đụng database, không đọc Churn)
# ---------------------------------------------------------------

def compute_window_end(snapshot_date):
    """Hết ngày SnapshotDate (23:59:59). Khách mới (tenure = 0) có EstimatedJoinDate
    đúng bằng SnapshotDate nên vẫn có cửa sổ khoảng một ngày để đặt thời điểm."""
    return snapshot_date + timedelta(days=1) - timedelta(seconds=1)


def compute_window(join_date, snapshot_date, simulation_config):
    """Cửa sổ thời gian của một khách: từ max(ngày tham gia ước lượng, snapshot - 730 ngày)
    đến hết ngày SnapshotDate."""
    window_end = compute_window_end(snapshot_date)
    earliest_allowed = snapshot_date - timedelta(days=simulation_config["window_days"])
    if join_date is None or join_date < earliest_allowed:
        window_start = earliest_allowed
    else:
        window_start = join_date
    return window_start, window_end


def make_customer_rng(seed, customer_id):
    """Mỗi khách có bộ sinh số ngẫu nhiên riêng, gieo từ chuỗi 'seed|CustomerID'.
    Nhờ vậy kết quả của một khách không đổi dù thứ tự khách hay số khách thay đổi.
    (Gieo bằng chuỗi dùng SHA-512 nên không phụ thuộc PYTHONHASHSEED.)"""
    return random.Random(str(seed) + "|" + customer_id)


def pick_weighted(rng, weights_by_name):
    """Chọn một tên theo trọng số."""
    names = list(weights_by_name.keys())
    weights = list(weights_by_name.values())
    return rng.choices(names, weights=weights, k=1)[0]


def pick_random_moment(rng, range_start, range_end):
    """Chọn một thời điểm (làm tròn đến giây) trong [range_start, range_end].
    Dùng số nguyên giây để kết quả ổn định, không dính sai số số thực."""
    total_seconds = int((range_end - range_start).total_seconds())
    offset_seconds = rng.randint(0, total_seconds)
    return range_start + timedelta(seconds=offset_seconds)


def make_interactions(rng, customer_id, window_start, window_end, simulation_config):
    """Sinh danh sách tương tác của một khách (5 đến 20 dòng)."""
    interaction_range = simulation_config["interactions_per_customer"]
    interaction_count = rng.randint(interaction_range["min"], interaction_range["max"])

    rows = []
    for _ in range(interaction_count):
        moment = pick_random_moment(rng, window_start, window_end)
        channel = pick_weighted(rng, simulation_config["channel_weights"])
        interaction_type = pick_weighted(rng, simulation_config["interaction_type_weights"])
        result = pick_weighted(rng, simulation_config["interaction_result_weights"])
        description = rng.choice(simulation_config["descriptions"][interaction_type])
        rows.append((customer_id, moment, channel, interaction_type, description, result, 1))

    rows.sort(key=lambda row: row[1])  # xếp theo thời gian cho dễ đọc
    return rows


def make_tickets(rng, customer_id, window_start, window_end, simulation_config):
    """Sinh danh sách ticket của một khách (0 đến 5 dòng), đúng quy tắc nghiệp vụ L7."""
    ticket_count_options = list(range(MAX_TICKETS_PER_CUSTOMER + 1))
    ticket_count = rng.choices(
        ticket_count_options, weights=simulation_config["tickets_per_customer_weights"], k=1
    )[0]

    window_seconds = int((window_end - window_start).total_seconds())
    recent_start_limit = window_end - timedelta(days=simulation_config["open_ticket_recent_days"])

    rows = []
    for _ in range(ticket_count):
        status = pick_weighted(rng, simulation_config["ticket_status_weights"])
        category = pick_weighted(rng, simulation_config["ticket_category_weights"])
        priority = pick_weighted(rng, simulation_config["ticket_priority_weights"])

        if status == "Closed":
            # Thời gian xử lý phụ thuộc mức ưu tiên (ưu tiên cao xử lý nhanh hơn)
            hour_range = simulation_config["resolution_hours"][priority]
            duration_seconds = rng.randint(hour_range[0] * 3600, hour_range[1] * 3600)
            if duration_seconds > window_seconds:
                duration_seconds = window_seconds  # khách quá mới: rút ngắn để vẫn nằm trong cửa sổ

            # Tạo sớm đến mức đóng xong vẫn không vượt quá cuối cửa sổ
            latest_created = window_end - timedelta(seconds=duration_seconds)
            created_at = pick_random_moment(rng, window_start, latest_created)
            closed_at = created_at + timedelta(seconds=duration_seconds)
            resolution = rng.choice(simulation_config["resolutions"][category])

            # Chỉ một phần ticket Closed có điểm hài lòng
            satisfaction_score = None
            if rng.random() < simulation_config["satisfaction_given_probability"]:
                score_text = pick_weighted(rng, simulation_config["satisfaction_score_weights"])
                satisfaction_score = int(score_text)
        else:
            # Open / InProgress: chỉ tạo trong những ngày gần SnapshotDate (còn đang xử lý)
            recent_start = max(window_start, recent_start_limit)
            created_at = pick_random_moment(rng, recent_start, window_end)
            closed_at = None
            resolution = None
            satisfaction_score = None

        rows.append((
            customer_id, created_at, closed_at, category, priority,
            status, resolution, satisfaction_score, 1,
        ))

    rows.sort(key=lambda row: row[1])
    return rows


def generate_all(customers, snapshot_date, simulation_config):
    """Sinh dữ liệu cho mọi khách. customers là danh sách (CustomerID, EstimatedJoinDate).
    KHÔNG có tham số nào liên quan đến nhãn Churn."""
    seed = simulation_config["seed"]
    all_interactions = []
    all_tickets = []

    for customer_id, join_date in customers:
        rng = make_customer_rng(seed, customer_id)
        window_start, window_end = compute_window(join_date, snapshot_date, simulation_config)
        all_interactions.extend(
            make_interactions(rng, customer_id, window_start, window_end, simulation_config)
        )
        all_tickets.extend(
            make_tickets(rng, customer_id, window_start, window_end, simulation_config)
        )

    return all_interactions, all_tickets


# ---------------------------------------------------------------
# 3. Tự kiểm trong bộ nhớ (L8, trước khi đụng database)
# ---------------------------------------------------------------

def validate_generated(customers, interaction_rows, ticket_rows, snapshot_date, simulation_config):
    """Kiểm dữ liệu vừa sinh. Trả về danh sách (mô tả, thực tế, kỳ vọng).
    Các mục 'vi phạm' đều có kỳ vọng 0."""
    window_end = compute_window_end(snapshot_date)

    windows = {}
    interaction_count_by_customer = {}
    ticket_count_by_customer = {}
    for customer_id, join_date in customers:
        windows[customer_id] = compute_window(join_date, snapshot_date, simulation_config)
        interaction_count_by_customer[customer_id] = 0
        ticket_count_by_customer[customer_id] = 0

    allowed = {
        "channel": set(simulation_config["channel_weights"].keys()),
        "type": set(simulation_config["interaction_type_weights"].keys()),
        "result": set(simulation_config["interaction_result_weights"].keys()),
        "category": set(simulation_config["ticket_category_weights"].keys()),
        "priority": set(simulation_config["ticket_priority_weights"].keys()),
        "status": set(simulation_config["ticket_status_weights"].keys()),
    }

    orphan_interactions = 0
    interaction_out_of_window = 0
    interaction_bad_value = 0
    interaction_not_simulated = 0

    for row in interaction_rows:
        customer_id, moment, channel, interaction_type, description, result, is_simulated = row
        if customer_id not in windows:
            orphan_interactions += 1
            continue
        interaction_count_by_customer[customer_id] += 1
        window_start, window_end_of_customer = windows[customer_id]
        if moment < window_start or moment > window_end_of_customer:
            interaction_out_of_window += 1
        if (channel not in allowed["channel"] or interaction_type not in allowed["type"]
                or result not in allowed["result"]):
            interaction_bad_value += 1
        if is_simulated != 1:
            interaction_not_simulated += 1

    orphan_tickets = 0
    ticket_out_of_window = 0
    ticket_bad_value = 0
    ticket_not_simulated = 0
    closed_without_closed_at = 0
    not_closed_with_closed_at = 0
    closed_before_created = 0
    score_outside_range = 0
    score_on_unclosed_ticket = 0
    unclosed_created_too_early = 0
    recent_limit = window_end - timedelta(days=simulation_config["open_ticket_recent_days"])

    for row in ticket_rows:
        (customer_id, created_at, closed_at, category, priority,
         status, resolution, satisfaction_score, is_simulated) = row
        if customer_id not in windows:
            orphan_tickets += 1
            continue
        ticket_count_by_customer[customer_id] += 1
        window_start, window_end_of_customer = windows[customer_id]

        if created_at < window_start or created_at > window_end_of_customer:
            ticket_out_of_window += 1
        if (category not in allowed["category"] or priority not in allowed["priority"]
                or status not in allowed["status"]):
            ticket_bad_value += 1
        if is_simulated != 1:
            ticket_not_simulated += 1

        if status == "Closed":
            if closed_at is None:
                closed_without_closed_at += 1
            else:
                if closed_at < created_at:
                    closed_before_created += 1
                if closed_at > window_end_of_customer:
                    ticket_out_of_window += 1
        else:
            if closed_at is not None:
                not_closed_with_closed_at += 1
            if created_at < recent_limit:
                unclosed_created_too_early += 1

        if satisfaction_score is not None:
            if satisfaction_score < 1 or satisfaction_score > 5:
                score_outside_range += 1
            if status != "Closed":
                score_on_unclosed_ticket += 1

    interaction_range = simulation_config["interactions_per_customer"]
    customers_bad_interaction_count = 0
    customers_bad_ticket_count = 0
    for customer_id, _ in customers:
        if not (interaction_range["min"] <= interaction_count_by_customer[customer_id] <= interaction_range["max"]):
            customers_bad_interaction_count += 1
        if ticket_count_by_customer[customer_id] > MAX_TICKETS_PER_CUSTOMER:
            customers_bad_ticket_count += 1

    checks = [
        ("Tương tác mồ côi (CustomerID không có trong danh sách khách)", orphan_interactions, 0),
        ("Ticket mồ côi", orphan_tickets, 0),
        ("Khách có số tương tác ngoài khoảng " + str(interaction_range["min"]) + " đến " + str(interaction_range["max"]),
         customers_bad_interaction_count, 0),
        ("Khách có hơn " + str(MAX_TICKETS_PER_CUSTOMER) + " ticket", customers_bad_ticket_count, 0),
        ("Tương tác nằm ngoài cửa sổ thời gian của khách", interaction_out_of_window, 0),
        ("Ticket (ngày tạo hoặc ngày đóng) nằm ngoài cửa sổ thời gian của khách", ticket_out_of_window, 0),
        ("Tương tác có giá trị kênh/loại/kết quả ngoài danh sách", interaction_bad_value, 0),
        ("Ticket có giá trị loại/ưu tiên/trạng thái ngoài danh sách", ticket_bad_value, 0),
        ("Tương tác có IsSimulated khác 1", interaction_not_simulated, 0),
        ("Ticket có IsSimulated khác 1", ticket_not_simulated, 0),
        ("Ticket Closed thiếu ClosedAt", closed_without_closed_at, 0),
        ("Ticket chưa Closed mà có ClosedAt", not_closed_with_closed_at, 0),
        ("Ticket có ClosedAt sớm hơn CreatedAt", closed_before_created, 0),
        ("Ticket có điểm hài lòng ngoài 1 đến 5", score_outside_range, 0),
        ("Ticket chưa Closed mà có điểm hài lòng", score_on_unclosed_ticket, 0),
        ("Ticket Open/InProgress tạo quá xa SnapshotDate (hơn "
         + str(simulation_config["open_ticket_recent_days"]) + " ngày)", unclosed_created_too_early, 0),
    ]
    return checks


# ---------------------------------------------------------------
# 4. Phần làm việc với SQL Server
# ---------------------------------------------------------------

def count_with_params(connection, sql_text, params):
    """Chạy một câu SELECT có tham số (?) trả về một con số."""
    cursor = connection.cursor()
    if len(params) == 0:
        cursor.execute(sql_text)  # không có dấu ? thì không truyền tham số
    else:
        cursor.execute(sql_text, params)
    return cursor.fetchone()[0]


def check_ready(connection, config, write_mode):
    """Phải có đủ bảng, đủ 12 CHECK, Customers đủ số dòng; khi ghi thật thì
    Interactions và Tickets phải đang trống. Không thì dừng, chưa ghi gì."""
    for table_name in ["Customers", "Interactions", "Tickets"]:
        table_exists = load_telco.count_value(
            connection, "SELECT COUNT(*) FROM sys.tables WHERE name = '" + table_name + "'"
        )
        if table_exists == 0:
            raise RuntimeError("Chưa có bảng " + table_name + ". Chạy schema.sql trước.")

    expected_check_count = config["expected"].get("check_constraints", 12)
    check_count = load_telco.count_value(connection, "SELECT COUNT(*) FROM sys.check_constraints")
    if check_count < expected_check_count:
        raise RuntimeError(
            "Database mới có " + str(check_count) + " CHECK, cần " + str(expected_check_count)
            + ". Chạy constraints_bo_sung.sql (sau schema.sql) trước."
        )

    customer_count = load_telco.count_value(connection, "SELECT COUNT(*) FROM Customers")
    if customer_count != config["expected"]["rows"]:
        raise RuntimeError(
            "Customers có " + str(customer_count) + " dòng, kỳ vọng " + str(config["expected"]["rows"])
            + ". Chạy load_telco.py trước."
        )

    if write_mode:
        for table_name in ["Interactions", "Tickets"]:
            row_count = load_telco.count_value(connection, "SELECT COUNT(*) FROM " + table_name)
            if row_count > 0:
                raise RuntimeError(
                    "Bảng " + table_name + " đã có " + str(row_count) + " dòng. "
                    "Script không xóa gì. Muốn sinh lại: xóa database, chạy lại chuỗi SQL + load_telco.py rồi chạy script này."
                )


def fetch_customers(connection):
    """Đọc CustomerID và EstimatedJoinDate. KHÔNG đọc cột nào liên quan đến nhãn Churn."""
    cursor = connection.cursor()
    cursor.execute("SELECT CustomerID, EstimatedJoinDate FROM Customers ORDER BY CustomerID")
    customers = []
    for row in cursor.fetchall():
        customers.append((row[0], row[1]))
    return customers


def insert_in_chunks(connection, table_name, column_names, rows):
    """Ghi các dòng vào một bảng, từng khối cho dễ theo dõi. Chưa commit."""
    sql_text = load_telco.build_insert_sql(table_name, column_names)
    cursor = connection.cursor()
    for start in range(0, len(rows), INSERT_CHUNK_SIZE):
        chunk = rows[start:start + INSERT_CHUNK_SIZE]
        cursor.executemany(sql_text, chunk)
        written = min(start + INSERT_CHUNK_SIZE, len(rows))
        print("  ", table_name, ":", written, "/", len(rows))


def run_database_checks(connection, snapshot_date, simulation_config,
                        expected_interaction_count, expected_ticket_count):
    """Đếm lại trong database sau khi ghi (chưa commit). Trả về (mô tả, thực tế, kỳ vọng)."""
    window_end = compute_window_end(snapshot_date)
    earliest_allowed = snapshot_date - timedelta(days=simulation_config["window_days"])
    recent_limit = window_end - timedelta(days=simulation_config["open_ticket_recent_days"])
    interaction_range = simulation_config["interactions_per_customer"]

    channel_names = list(simulation_config["channel_weights"].keys())
    type_names = list(simulation_config["interaction_type_weights"].keys())
    result_names = list(simulation_config["interaction_result_weights"].keys())
    category_names = list(simulation_config["ticket_category_weights"].keys())
    priority_names = list(simulation_config["ticket_priority_weights"].keys())
    status_names = list(simulation_config["ticket_status_weights"].keys())

    def marks(names):
        return ", ".join(["?"] * len(names))

    checks = [
        ("Interactions: số dòng", count_with_params(connection, "SELECT COUNT(*) FROM Interactions", []),
         expected_interaction_count),
        ("Tickets: số dòng", count_with_params(connection, "SELECT COUNT(*) FROM Tickets", []),
         expected_ticket_count),

        ("Interactions mồ côi (không có khách)", count_with_params(
            connection,
            "SELECT COUNT(*) FROM Interactions i LEFT JOIN Customers c ON i.CustomerID = c.CustomerID "
            "WHERE c.CustomerID IS NULL", []), 0),
        ("Tickets mồ côi (không có khách)", count_with_params(
            connection,
            "SELECT COUNT(*) FROM Tickets t LEFT JOIN Customers c ON t.CustomerID = c.CustomerID "
            "WHERE c.CustomerID IS NULL", []), 0),

        ("Khách có số tương tác ngoài khoảng " + str(interaction_range["min"]) + " đến " + str(interaction_range["max"]),
         count_with_params(
             connection,
             "SELECT COUNT(*) FROM (SELECT c.CustomerID AS CustomerID, COUNT(i.InteractionID) AS SoTuongTac "
             "FROM Customers c LEFT JOIN Interactions i ON i.CustomerID = c.CustomerID "
             "GROUP BY c.CustomerID) AS Dem WHERE Dem.SoTuongTac < ? OR Dem.SoTuongTac > ?",
             [interaction_range["min"], interaction_range["max"]]), 0),
        ("Khách có hơn " + str(MAX_TICKETS_PER_CUSTOMER) + " ticket", count_with_params(
            connection,
            "SELECT COUNT(*) FROM (SELECT c.CustomerID AS CustomerID, COUNT(t.TicketID) AS SoTicket "
            "FROM Customers c LEFT JOIN Tickets t ON t.CustomerID = c.CustomerID "
            "GROUP BY c.CustomerID) AS Dem WHERE Dem.SoTicket > ?", [MAX_TICKETS_PER_CUSTOMER]), 0),

        ("Interactions có IsSimulated khác 1", count_with_params(
            connection, "SELECT COUNT(*) FROM Interactions WHERE IsSimulated <> 1", []), 0),
        ("Tickets có IsSimulated khác 1", count_with_params(
            connection, "SELECT COUNT(*) FROM Tickets WHERE IsSimulated <> 1", []), 0),

        ("Interactions có StaffID khác NULL (chưa seed Staff)", count_with_params(
            connection, "SELECT COUNT(*) FROM Interactions WHERE StaffID IS NOT NULL", []), 0),
        ("Tickets có AssignedStaffID khác NULL (chưa seed Staff)", count_with_params(
            connection, "SELECT COUNT(*) FROM Tickets WHERE AssignedStaffID IS NOT NULL", []), 0),

        ("Interactions sau cuối ngày SnapshotDate", count_with_params(
            connection, "SELECT COUNT(*) FROM Interactions WHERE InteractionDate > ?", [window_end]), 0),
        ("Interactions trước mốc SnapshotDate - " + str(simulation_config["window_days"]) + " ngày",
         count_with_params(
             connection, "SELECT COUNT(*) FROM Interactions WHERE InteractionDate < ?", [earliest_allowed]), 0),
        ("Interactions sớm hơn EstimatedJoinDate của khách", count_with_params(
            connection,
            "SELECT COUNT(*) FROM Interactions i JOIN Customers c ON i.CustomerID = c.CustomerID "
            "WHERE c.EstimatedJoinDate IS NOT NULL AND i.InteractionDate < c.EstimatedJoinDate", []), 0),

        ("Tickets tạo sau cuối ngày SnapshotDate", count_with_params(
            connection, "SELECT COUNT(*) FROM Tickets WHERE CreatedAt > ?", [window_end]), 0),
        ("Tickets đóng sau cuối ngày SnapshotDate", count_with_params(
            connection, "SELECT COUNT(*) FROM Tickets WHERE ClosedAt > ?", [window_end]), 0),
        ("Tickets tạo trước mốc SnapshotDate - " + str(simulation_config["window_days"]) + " ngày",
         count_with_params(
             connection, "SELECT COUNT(*) FROM Tickets WHERE CreatedAt < ?", [earliest_allowed]), 0),
        ("Tickets tạo sớm hơn EstimatedJoinDate của khách", count_with_params(
            connection,
            "SELECT COUNT(*) FROM Tickets t JOIN Customers c ON t.CustomerID = c.CustomerID "
            "WHERE c.EstimatedJoinDate IS NOT NULL AND t.CreatedAt < c.EstimatedJoinDate", []), 0),
        ("Tickets Closed thiếu ClosedAt, hoặc chưa Closed mà có ClosedAt", count_with_params(
            connection,
            "SELECT COUNT(*) FROM Tickets WHERE (Status = 'Closed' AND ClosedAt IS NULL) "
            "OR (Status <> 'Closed' AND ClosedAt IS NOT NULL)", []), 0),
        ("Tickets có ClosedAt sớm hơn CreatedAt", count_with_params(
            connection, "SELECT COUNT(*) FROM Tickets WHERE ClosedAt < CreatedAt", []), 0),
        ("Tickets có điểm hài lòng nhưng chưa Closed", count_with_params(
            connection,
            "SELECT COUNT(*) FROM Tickets WHERE SatisfactionScore IS NOT NULL AND Status <> 'Closed'", []), 0),
        ("Tickets Open/InProgress tạo quá xa SnapshotDate (hơn "
         + str(simulation_config["open_ticket_recent_days"]) + " ngày)", count_with_params(
            connection,
            "SELECT COUNT(*) FROM Tickets WHERE Status <> 'Closed' AND CreatedAt < ?", [recent_limit]), 0),

        ("Interactions có kênh/loại/kết quả ngoài danh sách", count_with_params(
            connection,
            "SELECT COUNT(*) FROM Interactions WHERE Channel NOT IN (" + marks(channel_names) + ") "
            "OR InteractionType NOT IN (" + marks(type_names) + ") "
            "OR Result IS NULL OR Result NOT IN (" + marks(result_names) + ")",
            channel_names + type_names + result_names), 0),
        ("Tickets có loại/ưu tiên/trạng thái ngoài danh sách", count_with_params(
            connection,
            "SELECT COUNT(*) FROM Tickets WHERE Category NOT IN (" + marks(category_names) + ") "
            "OR Priority NOT IN (" + marks(priority_names) + ") "
            "OR Status NOT IN (" + marks(status_names) + ")",
            category_names + priority_names + status_names), 0),
    ]
    return checks


def query_pairs(connection, sql_text):
    """Chạy câu SELECT trả về hai cột (tên, giá trị) và gom thành danh sách."""
    cursor = connection.cursor()
    cursor.execute(sql_text)
    pairs = []
    for row in cursor.fetchall():
        pairs.append((row[0], row[1]))
    return pairs


def build_distribution_lines(connection):
    """Phân bố các giá trị đã ghi (để đưa vào báo cáo)."""
    lines = []
    sections = [
        ("Interactions theo kênh", "SELECT Channel, COUNT(*) FROM Interactions GROUP BY Channel ORDER BY Channel"),
        ("Interactions theo loại", "SELECT InteractionType, COUNT(*) FROM Interactions GROUP BY InteractionType ORDER BY InteractionType"),
        ("Interactions theo kết quả", "SELECT Result, COUNT(*) FROM Interactions GROUP BY Result ORDER BY Result"),
        ("Tickets theo trạng thái", "SELECT Status, COUNT(*) FROM Tickets GROUP BY Status ORDER BY Status"),
        ("Tickets theo ưu tiên", "SELECT Priority, COUNT(*) FROM Tickets GROUP BY Priority ORDER BY Priority"),
        ("Tickets theo loại", "SELECT Category, COUNT(*) FROM Tickets GROUP BY Category ORDER BY Category"),
        ("Tickets Closed theo điểm hài lòng (NULL = không ghi điểm)",
         "SELECT COALESCE(CAST(SatisfactionScore AS varchar(5)), 'NULL'), COUNT(*) FROM Tickets "
         "WHERE Status = 'Closed' GROUP BY SatisfactionScore ORDER BY SatisfactionScore"),
    ]
    for title, sql_text in sections:
        lines.append(title + ":")
        for name, count in query_pairs(connection, sql_text):
            lines.append("    " + str(name) + " = " + str(count))
    return lines


def build_independence_lines(connection):
    """KIỂM ĐỘC LẬP SAU KHI SINH (không dùng để sinh dữ liệu): trung bình số tương tác,
    số ticket và tỷ lệ Complaint theo nhãn ChurnLabel. Vì dữ liệu sinh KHÔNG nhìn nhãn,
    các số này chỉ lệch nhau do ngẫu nhiên."""
    customers_by_label = dict(query_pairs(
        connection, "SELECT ChurnLabel, COUNT(*) FROM CustomerSnapshots GROUP BY ChurnLabel"))
    interactions_by_label = dict(query_pairs(
        connection,
        "SELECT s.ChurnLabel, COUNT(i.InteractionID) FROM CustomerSnapshots s "
        "LEFT JOIN Interactions i ON i.CustomerID = s.CustomerID GROUP BY s.ChurnLabel"))
    complaints_by_label = dict(query_pairs(
        connection,
        "SELECT s.ChurnLabel, COUNT(i.InteractionID) FROM CustomerSnapshots s "
        "LEFT JOIN Interactions i ON i.CustomerID = s.CustomerID AND i.InteractionType = 'Complaint' "
        "GROUP BY s.ChurnLabel"))
    tickets_by_label = dict(query_pairs(
        connection,
        "SELECT s.ChurnLabel, COUNT(t.TicketID) FROM CustomerSnapshots s "
        "LEFT JOIN Tickets t ON t.CustomerID = s.CustomerID GROUP BY s.ChurnLabel"))

    lines = []
    for label in sorted(customers_by_label.keys()):
        customer_count = customers_by_label[label]
        interaction_count = interactions_by_label[label]
        complaint_count = complaints_by_label[label]
        ticket_count = tickets_by_label[label]
        lines.append(
            "    ChurnLabel = " + str(label) + ": " + str(customer_count) + " khách; "
            + "tương tác TB/khách = " + format(interaction_count / customer_count, ".2f") + "; "
            + "tỷ lệ Complaint = " + format(complaint_count / interaction_count, ".3f") + "; "
            + "ticket TB/khách = " + format(ticket_count / customer_count, ".2f")
        )
    return lines


# ---------------------------------------------------------------
# 5. Báo cáo kiểm (L8)
# ---------------------------------------------------------------

def format_check_lines(checks):
    """Biến danh sách (mô tả, thực tế, kỳ vọng) thành các dòng ĐẠT/KHÁC; trả về (dòng, số mục KHÁC)."""
    lines = []
    failed_count = 0
    for description, actual, expected_value in checks:
        if actual == expected_value:
            lines.append("  ĐẠT : " + description + " = " + str(actual))
        else:
            lines.append("  KHÁC: " + description + " = thực tế " + str(actual)
                         + ", kỳ vọng " + str(expected_value))
            failed_count += 1
    return lines, failed_count


def write_report(report_lines):
    """Ghi báo cáo kiểm ra file văn bản UTF-8 (đưa vào gói nộp, L8)."""
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(report_lines) + "\n")


def build_report_header(config, simulation_config, customer_count, interaction_count, ticket_count):
    return [
        "BÁO CÁO KIỂM DỮ LIỆU MÔ PHỎNG: Interactions và Tickets (đề tài 18, Mức 1)",
        "Dữ liệu này là MÔ PHỎNG (IsSimulated = 1), chỉ để demo chức năng CRM.",
        "Không dùng để huấn luyện hay đánh giá mô hình ML ở Mức 1 (L3, D-04).",
        "",
        "Tham số:",
        "  seed                  = " + str(simulation_config["seed"]),
        "  SnapshotDate          = " + config["snapshot_date"],
        "  cửa sổ thời gian      = max(EstimatedJoinDate, SnapshotDate - "
        + str(simulation_config["window_days"]) + " ngày) đến hết ngày SnapshotDate",
        "  Python                = " + platform.python_version(),
        "  số khách              = " + str(customer_count),
        "  số Interactions sinh  = " + str(interaction_count),
        "  số Tickets sinh       = " + str(ticket_count),
        "  StaffID, AssignedStaffID = NULL (chưa seed Staff)",
        "",
    ]


# ---------------------------------------------------------------
# 6. Chương trình chính
# ---------------------------------------------------------------

def main():
    dry_run = "--dry-run" in sys.argv
    config = load_telco.load_config()
    snapshot_date = datetime.strptime(config["snapshot_date"], "%Y-%m-%d")

    try:
        simulation_config = load_simulation_config()
    except (ValueError, KeyError) as error:
        print("CẤU HÌNH MÔ PHỎNG KHÔNG HỢP LỆ, chưa làm gì:")
        print(error)
        return

    print("seed         :", simulation_config["seed"])
    print("SnapshotDate :", config["snapshot_date"])
    print("Chế độ       :", "CHẠY THỬ (không ghi database)" if dry_run else "GHI THẬT vào database")

    # Bước 1: nối database, kiểm điều kiện, đọc danh sách khách
    try:
        connection = load_telco.connect_sql_server(config["server"], config["database"])
    except Exception as error:
        print("KẾT NỐI THẤT BẠI:")
        print(error)
        return

    try:
        check_ready(connection, config, write_mode=not dry_run)
        customers = fetch_customers(connection)
    except RuntimeError as error:
        print("DỪNG, chưa ghi gì:")
        print(error)
        connection.close()
        return
    print("Bước 1: kết nối OK, đọc được", len(customers), "khách")

    # Bước 2: sinh dữ liệu trong bộ nhớ
    interaction_rows, ticket_rows = generate_all(customers, snapshot_date, simulation_config)
    print("Bước 2: đã sinh", len(interaction_rows), "tương tác và", len(ticket_rows), "ticket")

    # Bước 3: tự kiểm trong bộ nhớ, sai thì dừng, chưa đụng database
    memory_checks = validate_generated(customers, interaction_rows, ticket_rows, snapshot_date, simulation_config)
    memory_lines, memory_failed = format_check_lines(memory_checks)
    print("Bước 3: tự kiểm trong bộ nhớ")
    for line in memory_lines:
        print(line)
    if memory_failed > 0:
        print("CÓ", memory_failed, "MỤC KHÁC trong bộ nhớ. Chưa ghi gì. Chụp màn hình gửi tao.")
        connection.close()
        return

    if dry_run:
        print("CHẠY THỬ XONG: dữ liệu sinh ra hợp lệ, KHÔNG ghi gì vào database.")
        connection.close()
        return

    # Bước 4: ghi trong một transaction, đếm lại, đúng hết mới commit
    try:
        print("Bước 4: ghi vào database (chưa commit)")
        insert_in_chunks(connection, "Interactions", INTERACTION_COLUMNS, interaction_rows)
        insert_in_chunks(connection, "Tickets", TICKET_COLUMNS, ticket_rows)
        database_checks = run_database_checks(
            connection, snapshot_date, simulation_config, len(interaction_rows), len(ticket_rows)
        )
        distribution_lines = build_distribution_lines(connection)
        independence_lines = build_independence_lines(connection)
    except Exception as error:
        connection.rollback()
        connection.close()
        print("LỖI KHI GHI, đã ROLLBACK, database không đổi:")
        print(error)
        return

    database_lines, database_failed = format_check_lines(database_checks)
    print("Bước 4: đối chiếu trong database (chưa commit)")
    for line in database_lines:
        print(line)

    if database_failed > 0:
        connection.rollback()
        connection.close()
        print("CÓ", database_failed, "MỤC KHÁC: đã ROLLBACK, database không đổi. Chụp màn hình gửi tao.")
        return

    connection.commit()
    connection.close()
    print("SINH XONG: đã commit.")

    # Bước 5: ghi báo cáo kiểm ra file (chỉ khi đã commit thành công)
    report_lines = build_report_header(
        config, simulation_config, len(customers), len(interaction_rows), len(ticket_rows)
    )
    report_lines.append("Tự kiểm trong bộ nhớ (trước khi ghi):")
    report_lines.extend(memory_lines)
    report_lines.append("")
    report_lines.append("Đối chiếu trong database (trước khi commit):")
    report_lines.extend(database_lines)
    report_lines.append("")
    report_lines.append("Phân bố giá trị đã ghi:")
    report_lines.extend(distribution_lines)
    report_lines.append("")
    report_lines.append("Kiểm độc lập với nhãn (CHỈ ĐỂ KIỂM SAU KHI SINH; dữ liệu sinh KHÔNG đọc nhãn Churn, L2):")
    report_lines.extend(independence_lines)
    write_report(report_lines)
    print("Đã ghi báo cáo kiểm:", REPORT_FILE)


if __name__ == "__main__":
    main()
