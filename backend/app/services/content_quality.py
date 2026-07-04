"""Lightweight content quality checks for user-visible output files."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DESKTOP_FILE_BLOCK_RE = re.compile(
    r"```desktop-local-file\s*\n(?P<json>.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)

COMMON_VIETNAMESE = {
    # Function words & grammar
    "và","của","các","với","những","đã","được","có","cho","trong","một","không","tại",
    "vào","ra","năm","về","là","cũng","ở","người","bị","mà","khi","sẽ","để","còn",
    "nếu","thì","hay","hoặc","qua","lại","rồi","sau","trước","trên","dưới","trong",
    "ngoài","giữa","bên","từ","đến","vì","nên","do","như","theo","bằng","đây","đó",
    "kia","ấy","nào","đâu","sao","thế","vậy","lắm","quá","lên","xuống","thôi","à",
    "hả","nhỉ","nhé","ạ","đi","nhé","vậy","ư","sao","mới","đang","sẽ","đã","từng",
    "đều","cứ","hãy","chớ","đừng","phải","cần","muốn","thể","bắt","đầu",
    "tiếp","tục","kết","thúc","thường","luôn","toàn","hầu","hễ","mỗi","mọi","vài",
    "dăm","mấy","bao","bấy","chút","tí","ít","nhiều","lớn","nhỏ","rộng","hẹp","dài",
    "ngắn","cao","thấp","gần","xa","nặng","nhẹ","nhanh","chậm","sớm","muộn","cũ","mới",
    "tốt","xấu","đẹp","xinh","giàu","nghèo","mạnh","yếu","khỏe","bệnh","vui","buồn",
    "giận","thương","nhớ","quên","tin","ngờ","sợ","hãi","ngạc","nhiên","thích","ghét",
    "hài","lòng","hối","tiếc","thất","vọng","chính","mẫu","đủ","vượt","qua",
    "kiểm","tra","độ","tối","thiểu","chúng","tôi","thêm","hơn","đảm","bảo",
    "yêu","cầu","nay","mai","kia","vẫn","cứ","đang","sắp","từng","liền",
    "nội","dung","này","đây","đạt","giá","trị","phần","loại","hình",
    "liên","quan","dụng","cụ","thể","hiện","nhất","thứ","hai","ba",
    "bốn","sáu","bảy","tám","chín","mười","triệu","tỉ","tỷ","phần",
    "trăm","điều","kiện","hoàn","cảnh","trường","hợp","khoảng","cách",
    "hướng","dẫn","chỉ","dẫn","kết","quả","nguyên","nhân","hệ","thống",
    "mục","đích","phương","thức","phạm","vi","đối","tượng","thành","phần",
    "cấu","trúc","chức","năng","tính","chất","đặc","điểm","thuộc","tính",
    "phương","pháp","giải","pháp","thông","tin","dữ","liệu","cơ","sở",
    "dữ liệu","dễ","dàng","thuận","lợi","khó","khăn","thách","thức",
    "cơ hội","nguy","cơ","rủi","ro","lợi","ích","bất","lợi","tác","động",
    "ảnh","hưởng","tương","tác","hỗ","trợ","phát","triển","xây","dựng",
    "thiết","kế","triển","khai","vận","hành","bảo","trì","nâng","cấp",
    "mở","rộng","thu","hẹp","tập","trung","phân","tán","tích","hợp",
    "đồng","bộ","nhất","quán","liên","tục","gián","đoạn","cơ","bản",
    "nâng cao","cao cấp","trung cấp","sơ cấp","chuyên","nghiệp",
    "nghiệp vụ","kỹ thuật","kỹ năng","nghiệp vụ",
    "tựa","đề","bài","viết","nguồn","tham","khảo","trích","dẫn",
    "nói","viết","đọc","xem","nghe","hỏi","đáp","trả","lời","gửi",
    "nhận","gọi","đặt","mở","đóng","bật","tắt","chạy","dừng","nghỉ",
    "ngừng","chờ","đợi","tìm","kiếm","tra","cứu","soạn","thảo",
    "biên","tập","hiệu","đính","dịch","thuật","xuất","bản","đăng",
    "tải","công","bố","phát","hành","tổng","hợp","phân","tích",
    "nghiên","cứu","khảo","sát","thống","kê","điều","chỉnh","tối ưu",
    "tối ưu hóa","chuẩn","bị","sẵn","sàng","chuẩn bị","chuẩn mực",
    "phù","hợp","tương","thích","tương ứng","đồng nhất","khác biệt",
    "tách","biệt","riêng","lẻ","chung","toàn thể","toàn bộ","từng",
    "từng cái","từng người","mỗi","mọi","tất cả","tất thảy","hết thảy",
    # Common nouns
    "người","việc","vật","nơi","lúc","giờ","phút","giây","ngày","tuần","tháng",
    "thứ","năm","mùa","xuân","hạ","thu","đông","trời","đất","nước","biển","rừng",
    "núi","sông","hồ","đường","xóm","làng","thành phố","quốc gia","thế giới",
    "nhà","cửa","xe","máy","bàn","ghế","giường","tủ","sách","vở","bút","điện thoại",
    "máy tính","ti vi","tivi","điều khiển","công việc","học tập","giải trí",
    "thể thao","âm nhạc","nghệ thuật","khoa học","công nghệ","kinh tế","chính trị",
    "xã hội","văn hóa","giáo dục","y tế","quốc phòng","an ninh","môi trường",
    "thông tin","dữ liệu","số liệu","báo cáo","văn bản","tài liệu","hồ sơ",
    "chứng từ","hợp đồng","thỏa thuận","quyết định","chính sách","pháp luật",
    "quy định","hướng dẫn","chỉ dẫn","lời khuyên","ý kiến","nhận xét","đánh giá",
    "phân tích","tổng hợp","so sánh","đối chiếu","kiểm tra","xác nhận","xác minh",
    # Common verbs
    "làm","nói","viết","đọc","nghe","nhìn","thấy","biết","hiểu","nghĩ","nhớ",
    "quên","gọi","đặt","lấy","cho","nhận","tặng","mua","bán","trao","đổi",
    "mang","đem","đưa","lấy","cất","giữ","bỏ","thêm","bớt","sửa","chữa",
    "xây","dựng","phá","hủy","mở","đóng","bật","tắt","bắt đầu","kết thúc",
    "tiếp tục","tạm dừng","ngừng","thôi","nghỉ","chạy","đi","đến","về","lên",
    "xuống","vào","ra","qua","lại","quanh","theo","đuổi","tìm","kiếm","gặp",
    "hỏi","trả lời","đáp","cảm ơn","xin lỗi","chào","tạm biệt","hẹn",
    "giúp","hỗ trợ","bảo vệ","duy trì","phát triển","cải thiện","nâng cao",
    "giảm","tăng","thay đổi","điều chỉnh","chỉnh sửa","cập nhật","xóa","thêm",
    # Common adjectives & states
    "đúng","sai","thật","giả","thực","ảo","rõ","mờ","sáng","tối","ấm","lạnh",
    "nóng","nguội","khô","ướt","sạch","bẩn","đầy","vơi","cứng","mềm","dẻo",
    "giòn","ngọt","mặn","chua","cay","đắng","thơm","thối","hôi","bốc",
    # Tech & office
    "backend","frontend","database","server","client","api","rest","graphql",
    "sqlite","python","javascript","typescript","react","node","docker","git",
    "github","ci","cd","test","deploy","config","env","file","folder","directory",
    "workspace","session","project","code","source","build","compile","run",
    "debug","log","error","warning","info","status","health","check","audit",
    "event","stream","socket","request","response","prompt","model","provider",
    "token","auth","login","logout","user","admin","role","permission","policy",
    "rule","schema","table","column","row","query","insert","update","delete",
    "select","join","index","key","value","json","xml","html","css","markdown",
    # Common numbers and time words
    "một","hai","ba","bốn","năm","sáu","bảy","tám","chín","mười","trăm","ngàn",
    "triệu","tỉ","tỷ","phần trăm","số","đầu","cuối","giữa","trước","sau",
    "nay","mai","hôm qua","hôm nay","ngày mai","ngày kia","tuần trước",
    "tuần sau","tháng trước","tháng sau","năm ngoái","năm nay","năm sau",
    # Domain-specific Hermes project
    "hermes","n8n","mcp","sse","fastapi","pydantic","vite","zustand",
    "monaco","opencode","codex","antigravity","acp","preflight",
    "desktop","local","stack","outputs","workspace","automation",
    # Additional common Vietnamese
    "đồng","tiền","giá","chi phí","doanh thu","lợi nhuận","thuế","phí",
    "lương","thưởng","phúc lợi","bảo hiểm","đầu tư","tiết kiệm","vay",
    "trả","nợ","tài sản","ngân sách","kế hoạch","mục tiêu","chiến lược",
    "thị trường","khách hàng","đối tác","nhà cung cấp","đối thủ",
    "sản phẩm","dịch vụ","thương hiệu","quảng cáo","tiếp thị","bán hàng",
    "học","sinh viên","giáo viên","trường","lớp","môn","bài","kiểm tra",
    "thi","tốt nghiệp","bằng cấp","chứng chỉ","kỹ năng","kinh nghiệm",
    "sức khỏe","bệnh viện","bác sĩ","thuốc","khám","chữa","phẫu thuật",
    "tai nạn","cấp cứu","phòng ngừa","vaccine","dinh dưỡng","tập luyện",
    "món ăn","thức uống","bữa sáng","bữa trưa","bữa tối","nguyên liệu",
    "gia vị","rau","củ","quả","thịt","cá","trứng","sữa","bánh","kẹo",
    "du lịch","khách sạn","vé máy bay","đặt phòng","hành lý","hộ chiếu",
    "visa","bản đồ","địa điểm","thắng cảnh","di tích","bảo tàng","công viên",
    "thể thao","bóng đá","bóng chuyền","bóng rổ","cầu lông","quần vợt",
    "bơi lội","chạy bộ","đạp xe","tập gym","yoga","võ thuật",
    "xe máy","ô tô","tàu hỏa","máy bay","tàu thủy","xe buýt","xe taxi",
    "tắc đường","cầu","hầm","bến xe","nhà ga","sân bay","cảng",
    "giấy tờ","chứng minh","căn cước","hộ khẩu","đăng ký","giấy phép",
    "biên lai","hóa đơn","phiếu","vé","thẻ","ví","túi","ba lô",
    "điện","nước","ga","xăng","dầu","năng lượng","mặt trời","gió",
    "tái tạo","tiết kiệm","hiệu quả","bền vững","xanh","sạch",
    # Publishing / writing
    "bài viết","tựa đề","tiêu đề","đoạn mở đầu","lead","nội dung",
    "kết luận","tóm tắt","nguồn tham khảo","tài liệu tham khảo",
    "trích dẫn","dẫn nguồn","biên tập","hiệu đính","xuất bản",
    "đăng tải","công bố","phát hành","tin tức","bản tin","phóng sự",
    "phỏng vấn","báo cáo","khảo sát","nghiên cứu","phân tích","đánh giá",
    "nhận định","bình luận","góc nhìn","quan điểm","chuyên mục",
    "viết bài","soạn thảo","biên soạn","tổng hợp","dịch thuật",
}

SUSPICIOUS_PHRASES = {
    "thông lương": "Cụm từ nghi ngờ sai chính tả; thường là 'thông thương'.",
    "xi măng asean": "Cụm từ không phù hợp ngữ cảnh bài báo hàng hải.",
    "phá vỡ cảng biển": "Cụm từ dịch máy/sai nghĩa trong ngữ cảnh cảng biển.",
    "phản lực hạt nhân": "Cụm từ sai nghĩa hoặc không rõ nghĩa trong ngữ cảnh bài viết.",
}


WORD_TOKEN_RE = re.compile(r"[a-zA-ZàáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬĐÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴ]+")
NUMBERS_RE = re.compile(r"^[0-9.,%$€¥₫]+$")
ENGLISH_COMMON = {
    "the","be","to","of","and","a","in","that","have","it","for","on","with",
    "as","at","by","from","or","an","but","not","you","all","can","her","was",
    "one","our","out","has","had","his","its","say","who","get","make","them",
    "some","would","about","into","time","than","then","their","other","more",
    "these","when","which","what","your","will","may","also","each","only",
    "very","just","where","how","much","many","such","should","because","while",
    "well","still","even","too","here","there","down","back","right","left",
    "first","last","own","new","old","great","high","long","big","small",
    "next","same","both","need","use","work","help","keep","start","show",
    "turn","bring","take","give","know","think","want","look","find","call",
    "try","ask","tell","feel","seem","put","set","run","move","live","play",
    "change","follow","include","provide","support","create","develop","build",
    "design","implement","integrate","configure","deploy","test","release",
    "manage","control","ensure","maintain","improve","reduce","increase",
    "offer","require","allow","enable","disable","specify","define","describe",
    "explain","introduce","present","represent","identify","establish","form",
    "produce","perform","operate","function","process","handle","carry","lead",
    "serve","act","respond","react","determine","affect","influence","contribute",
    "participate","involve","engage","interact","communicate","connect","link",
    "relate","correspond","match","fit","suit","adapt","adjust","modify","convert",
    "transform","generate","produce","output","input","display","show","indicate",
    "reveal","demonstrate","illustrate","prove","verify","confirm","validate",
    "check","review","assess","evaluate","measure","calculate","estimate",
    "project","predict","forecast","plan","schedule","organize","arrange",
    "prepare","ready","finalize","complete","finish","deliver","distribute",
    "share","collaborate","cooperate","negotiate","discuss","debate","argue",
    "agree","disagree","accept","reject","approve","deny","allow","permit",
    "authorize","grant","assign","allocate","distribute","collect","gather",
    "assemble","compile","compose","write","draft","edit","rewrite","revise",
    "update","modify","alter","amend","correct","fix","repair","resolve",
    "address","tackle","handle","manage","deal","cover","include","contain",
    "consist","comprise","feature","offer","provide","supply","furnish","equip",
    "app","application","website","web","page","content","user","client",
    "server","system","platform","framework","tool","utility","library",
    "package","module","component","element","section","part","piece","portion",
    "segment","unit","item","entry","record","register","log","history",
    "version","release","update","upgrade","patch","fix","enhancement",
    "feature","improvement","optimization","configuration","setting","option",
    "preference","customization","default","standard","normal","basic","advanced",
    "simple","complex","efficient","effective","productive","useful","helpful",
    "valuable","important","critical","essential","necessary","required",
    "mandatory","optional","additional","extra","supplementary","complementary",
    "alternative","different","similar","identical","equivalent","corresponding",
    "minimum","maximum","average","median","typical","common","unusual","unique",
    "specific","general","overall","total","partial","complete","full","empty",
    "null","undefined","unknown","missing","present","available","visible",
    "hidden","accessible","public","private","internal","external","local",
    "remote","global","central","distributed","direct","indirect","immediate",
    "delayed","synchronous","asynchronous","real-time","batch","online","offline",
    "standalone","embedded","integrated","isolated","dependent","independent",
    "automatic","manual","guided","automated","smart","intelligent","adaptive",
    "dynamic","static","fixed","variable","constant","temporary","permanent",
    "durable","reliable","stable","consistent","coherent","clear","precise",
    "accurate","exact","correct","valid","proper","appropriate","suitable",
    "acceptable","satisfactory","adequate","sufficient","enough","plenty",
    "abundant","scarce","limited","finite","infinite","boundless","endless",
    "recent","latest","current","previous","former","latter","prior","next",
    "following","subsequent","consecutive","sequential","ordered","sorted",
    "random","arbitrary","chaotic","organized","structured","formatted",
    "encoded","encrypted","hashed","plain","raw","processed","compiled",
    "interpreted","transpiled","minified","bundled","packaged","optimized",
    "debugged","tested","verified","validated","certified","approved","checked",
    "reviewed","audited","inspected","examined","analyzed","evaluated",
    "assessed","rated","scored","ranked","graded","classified","categorized",
    "grouped","sorted","filtered","searched","browsed","navigated","explored",
    "browser","client","desktop","mobile","tablet","device","screen","display",
    "monitor","resolution","pixel","density","aspect","ratio","orientation",
    "portrait","landscape","responsive","adaptive","fluid","flexible","elastic",
    "scalable","maintainable","testable","deployable","reusable","extensible",
    "pluggable","composable","configurable","customizable","themeable","stylable",
    "readable","writable","executable","loadable","editable","clickable","tappable",
    "selectable","draggable","resizable","scrollable","zoomable",
}


SUSPICIOUS_CHAR_PATTERNS = re.compile(
    r"[àáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]"
)

SUSPICIOUS_SUBSTRINGS = [
    "ăă", "ââ", "êê", "ôô", "ơơ", "ưư",  # double diacritic (typo)
    "uw", "ue", "uo", "oa", "oe", "ui", "oi", "ai", "au", "iu",  # rare diphthongs
]


def _check_spelling(text: str) -> list[str]:
    """Flag suspicious words based on character-level heuristics.

    Only flags words that:
    - Contain Vietnamese diacritics
    - Are >= 4 characters long
    - Aren't in the common dictionary
    - Have an unusual structure suggesting a typo or machine-translation artifact
    """
    issues: list[str] = []
    seen: set[str] = set()
    for match in WORD_TOKEN_RE.finditer(text):
        word = match.group()
        if NUMBERS_RE.match(word):
            continue
        lower = word.lower()
        if lower in COMMON_VIETNAMESE or lower in ENGLISH_COMMON:
            continue
        if len(lower) <= 3:
            continue
        if word[0].isupper() and not word.isupper():
            continue
        if not SUSPICIOUS_CHAR_PATTERNS.search(word):
            continue
        lower = word.lower()
        if lower not in seen:
            seen.add(lower)
            if len(seen) > 10:
                break
    if seen:
        examples = ", ".join(sorted(seen)[:3])
        issues.append(f"Phát hiện từ không phổ biến: {examples}. Nên kiểm tra chính tả.")
    return issues

STRONG_CLAIM_MARKERS = [
    "chắc chắn", "không thể phủ nhận", "sự thật là", "rõ ràng", "chứng minh",
    "đã xác minh", "chính thức công bố", "chính phủ", "quyết định", "tuyên bố",
    "nhà chức trách", "khẳng định",
]

MIN_CONTENT_LENGTH = 100

CODE_DIR_NAMES = {"backend", "frontend", "infra"}


@dataclass(frozen=True)
class ContentQualityResult:
    status: str
    label: str
    issues: list[str]
    file_path: str
    checked_at: int

    def model_dump(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "label": self.label,
            "issues": self.issues,
            "file_path": self.file_path,
            "checked_at": self.checked_at,
        }


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _is_in_code_dir(file_path: Path, project_root: Path) -> bool:
    try:
        relative_parts = file_path.resolve().relative_to(project_root.resolve()).parts
    except ValueError:
        return False
    return bool(relative_parts) and relative_parts[0].lower() in CODE_DIR_NAMES


def _has_source_reference(text: str) -> bool:
    lowered = text.lower()
    return (
        "nguồn tham khảo" in lowered
        or "nguồn:" in lowered
        or "tài liệu tham khảo" in lowered
        or "<a " in lowered
        or "href=" in lowered
        or "http://" in lowered
        or "https://" in lowered
    )


def _has_title_h1(text: str) -> bool:
    return bool(re.search(r"<h1[\s>]", text, re.IGNORECASE))


def _has_minimum_length(text: str) -> bool:
    stripped = re.sub(r"<[^>]+>", "", text).strip()
    return len(stripped) >= MIN_CONTENT_LENGTH


def _has_strong_claims_without_sources(text: str) -> list[str]:
    if _has_source_reference(text):
        return []
    lowered = text.lower()
    found = [marker for marker in STRONG_CLAIM_MARKERS if marker in lowered]
    if len(found) >= 3:
        return ["Nhiều nhận định mạnh nhưng chưa có nguồn tham khảo cụ thể."]
    return []


def check_output_file_quality(
    file_path: Path,
    workspace_path: Path,
    project_root: Path,
) -> ContentQualityResult:
    """Return a small, deterministic quality result for one output file."""
    issues: list[str] = []
    checked_at = int(time.time())
    resolved_file = file_path.resolve()

    if not _is_inside(resolved_file, workspace_path):
        issues.append("Sai vị trí lưu file: file nằm ngoài workspace của phiên.")

    if _is_in_code_dir(resolved_file, project_root):
        issues.append("Sai vị trí lưu file: không nên lưu output vào backend/frontend/infra.")

    if not resolved_file.exists():
        issues.append("Không tìm thấy file đầu ra để kiểm tra.")
    else:
        try:
            text = resolved_file.read_text(encoding="utf-8")
            lowered = text.lower()
            if resolved_file.suffix.lower() in {".html", ".htm"}:
                if "<!doctype html" not in lowered or "<html" not in lowered or "<head" not in lowered:
                    issues.append("HTML thiếu cấu trúc tài liệu đầy đủ.")
                if "charset=\"utf-8\"" not in lowered and "charset=utf-8" not in lowered:
                    issues.append("HTML thiếu meta charset UTF-8.")
                if not _has_title_h1(text):
                    issues.append("HTML thiếu thẻ h1 (tựa đề) hoặc đoạn mở đầu.")
            if not _has_source_reference(text):
                issues.append("Bài viết thiếu nguồn tham khảo hoặc link nguồn cụ thể.")
            if not _has_minimum_length(text):
                issues.append("Bài viết quá ngắn.")
            claims_issues = _has_strong_claims_without_sources(text)
            issues.extend(claims_issues)
            for phrase, message in SUSPICIOUS_PHRASES.items():
                if phrase in lowered:
                    issues.append(message)
            spelling_issues = _check_spelling(text)
            issues.extend(spelling_issues)
        except UnicodeDecodeError:
            issues.append("Không đọc được HTML bằng UTF-8.")

    html_structural_issues = {"HTML thiếu cấu trúc", "HTML thiếu meta charset", "HTML thiếu thẻ h1"}
    has_html_issues = any(
        any(struct in issue for struct in html_structural_issues)
        for issue in issues
    )

    status = "usable" if not issues else "needs_review"
    label = "Có thể dùng" if status == "usable" else "Cần rà soát"
    if any("vị trí" in issue.lower() for issue in issues):
        label = "Sai vị trí lưu file"
    elif has_html_issues:
        label = "HTML chưa đạt"
    elif any("nguồn" in issue.lower() for issue in issues):
        label = "Thiếu nguồn"

    return ContentQualityResult(
        status=status,
        label=label,
        issues=issues,
        file_path=str(resolved_file),
        checked_at=checked_at,
    )


def enrich_desktop_file_blocks(
    text: str,
    workspace_path: Path,
    project_root: Path,
) -> tuple[str, list[ContentQualityResult]]:
    """Attach quality metadata to desktop-local-file blocks in a markdown response."""
    results: list[ContentQualityResult] = []

    def replace(match: re.Match[str]) -> str:
        raw_json = match.group("json")
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            return match.group(0)

        local_path = payload.get("localPath")
        if not isinstance(local_path, str) or not local_path.strip():
            return match.group(0)

        result = check_output_file_quality(Path(local_path), workspace_path, project_root)
        results.append(result)
        payload["contentQuality"] = result.model_dump()
        return "```desktop-local-file\n" + json.dumps(payload, ensure_ascii=False) + "\n```"

    return DESKTOP_FILE_BLOCK_RE.sub(replace, text), results
