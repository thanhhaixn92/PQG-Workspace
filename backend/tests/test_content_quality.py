from __future__ import annotations

from pathlib import Path

from app.services.content_quality import check_output_file_quality, enrich_desktop_file_blocks


def test_html_missing_utf8_sources_and_suspicious_phrase_is_flagged(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    html_file = workspace / "outputs" / "article.html"
    html_file.parent.mkdir()
    html_file.write_text(
        "<!doctype html><html><head></head><body>"
        "<p>kênh thông lương</p><p>Xi măng ASEAN</p>"
        "<p>Đây là nội dung mẫu đủ dài để vượt qua kiểm tra độ dài tối thiểu cho bài viết. Chúng tôi cần thêm nhiều chữ hơn để đạt yêu cầu về độ dài nội dung.</p>"
        "</body></html>",
        encoding="utf-8",
    )

    result = check_output_file_quality(html_file, workspace, tmp_path)

    assert result.status == "needs_review"
    assert result.label == "HTML chưa đạt"
    assert any("HTML thiếu meta charset UTF-8" in issue for issue in result.issues)
    assert any("Bài viết thiếu nguồn" in issue for issue in result.issues)
    assert any("thông thương" in issue for issue in result.issues)
    assert any("hàng hải" in issue for issue in result.issues)


def test_output_in_code_directory_is_flagged(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    workspace = project_root
    output_file = project_root / "backend" / "article.html"
    output_file.parent.mkdir(parents=True)
    output_file.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        '<body><a href="https://example.com">Nguồn</a></body></html>',
        encoding="utf-8",
    )

    result = check_output_file_quality(output_file, workspace, project_root)

    assert result.status == "needs_review"
    assert result.label == "Sai vị trí lưu file"
    assert any("backend/frontend/infra" in issue for issue in result.issues)


def test_enrich_desktop_local_file_block_adds_quality_metadata(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    file_path = workspace / "article.html"
    file_path.write_text("<article>Không có nguồn</article>", encoding="utf-8")
    response = (
        "File:\n"
        "```desktop-local-file\n"
        f'{{"localPath":"{str(file_path).replace(chr(92), chr(92) * 2)}","fileName":"article.html"}}\n'
        "```"
    )

    enriched, results = enrich_desktop_file_blocks(response, workspace, tmp_path)

    assert len(results) == 1
    assert '"contentQuality"' in enriched
    assert any(label in enriched for label in ("Cần rà soát", "Thiếu nguồn", "HTML chưa đạt"))


def test_html_missing_h1_is_flagged_as_html_chua_dat(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    html_file = workspace / "article.html"
    html_file.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        '<body><p>Đây là nội dung bài viết mẫu đủ dài để vượt qua kiểm tra độ dài tối thiểu.</p></body></html>',
        encoding="utf-8",
    )

    result = check_output_file_quality(html_file, workspace, tmp_path)

    assert result.status == "needs_review"
    assert result.label == "HTML chưa đạt"
    assert any("thẻ h1" in issue for issue in result.issues)


def test_html_with_title_and_sources_returns_usable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    html_file = workspace / "article.html"
    html_file.write_text(
        '<!doctype html><html><head><meta charset="utf-8"><title>Bài viết</title></head>'
        '<body><h1>Tựa đề bài viết</h1>'
        '<p>Nội dung chính của bài viết này. Đây là một bài viết mẫu đủ dài để vượt qua kiểm tra độ dài tối thiểu. Chúng tôi đang thêm nhiều nội dung hơn để đảm bảo bài viết đạt yêu cầu về độ dài.</p>'
        '<p>Nguồn tham khảo: <a href="https://example.com">Example</a></p></body></html>',
        encoding="utf-8",
    )

    result = check_output_file_quality(html_file, workspace, tmp_path)

    assert result.status == "usable"
    assert result.label == "Có thể dùng"
    assert len(result.issues) == 0


def test_html_too_short_is_flagged(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    html_file = workspace / "short.html"
    html_file.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        '<body><h1>Short</h1></body></html>',
        encoding="utf-8",
    )

    result = check_output_file_quality(html_file, workspace, tmp_path)

    assert result.status == "needs_review"
    assert any("quá ngắn" in issue for issue in result.issues)


def test_strong_claims_without_sources_is_flagged(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    html_file = workspace / "claims.html"
    html_file.write_text(
        '<!doctype html><html><head><meta charset="utf-8"></head>'
        '<body><h1>Tin nóng</h1>'
        '<p>Chắc chắn sự thật là không thể phủ nhận. Rõ ràng chứng minh rằng nhà chức trách đã xác minh tuyên bố này. Chính phủ quyết định khẳng định thông tin này.</p>'
        '</body></html>',
        encoding="utf-8",
    )

    result = check_output_file_quality(html_file, workspace, tmp_path)

    assert result.status == "needs_review"
    assert any("nhận định mạnh" in issue for issue in result.issues)


def test_suspicious_phrase_detected_in_non_html(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    txt_file = workspace / "outputs" / "note.txt"
    txt_file.parent.mkdir()
    txt_file.write_text("Ghi chú về thông lương.", encoding="utf-8")

    result = check_output_file_quality(txt_file, workspace, tmp_path)

    assert result.status == "needs_review"
    assert any("thông thương" in issue for issue in result.issues)
