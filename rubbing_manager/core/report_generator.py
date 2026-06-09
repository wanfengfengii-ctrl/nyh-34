from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from ..db.database import (
    RubbingDAO,
    ComparisonDAO,
    SimilarityFeedbackDAO,
    EditionGroupDAO,
    EditionRelationDAO,
    ImportRecordDAO,
)
from .rubbing_service import RubbingService


MISSING = "—"


def _safe_str(value, default=MISSING):
    if value is None or value == "":
        return default
    return str(value)


def _safe_num(value, digits=2, default=MISSING):
    if value is None:
        return default
    try:
        return f"{float(value):.{digits}f}"
    except (ValueError, TypeError):
        return default


def _conclusion_label(conclusion: Optional[str]) -> str:
    mapping = {
        ComparisonDAO.CONCLUSION_SAME_EDITION: "同版",
        ComparisonDAO.CONCLUSION_SUSPECTED_FORGERY: "疑似仿刻",
        ComparisonDAO.CONCLUSION_DIFFERENT: "不同版",
        ComparisonDAO.CONCLUSION_UNCONFIRMED: "待确认",
    }
    return mapping.get(conclusion, MISSING)


def _feedback_label(feedback_type: Optional[str]) -> str:
    mapping = {
        SimilarityFeedbackDAO.FEEDBACK_CORRECT: "推荐正确",
        SimilarityFeedbackDAO.FEEDBACK_WRONG: "推荐错误",
    }
    return mapping.get(feedback_type, MISSING)


def _relation_label(rel_type: Optional[str]) -> str:
    return EditionRelationDAO.RELATION_LABELS.get(rel_type, MISSING)


class ReportGenerator:
    def __init__(self, service: RubbingService):
        self._service = service

    def generate_single_report(self, rubbing_id: int) -> Dict[str, Any]:
        rubbing = RubbingDAO.get_by_id(rubbing_id)
        if not rubbing:
            raise ValueError(f"拓片不存在: {rubbing_id}")

        comparisons = ComparisonDAO.get_by_rubbing(rubbing_id)
        feedbacks = SimilarityFeedbackDAO.get_by_rubbing(rubbing_id)
        edition_groups = EditionGroupDAO.get_by_rubbing(rubbing_id)
        import_records = self._get_import_records(rubbing)

        try:
            similar_items = self._service.find_similar(rubbing_id, top_k=10)
        except Exception:
            similar_items = []

        report = {
            "report_type": "single",
            "title": f"拓片研究报告 - {rubbing.get('code', '未知')}",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rubbing": rubbing,
            "similar_items": similar_items,
            "comparisons": comparisons,
            "feedbacks": feedbacks,
            "edition_groups": edition_groups,
            "import_records": import_records,
            "graph_image_path": None,
        }
        return report

    def generate_group_report(self, group_id: int) -> Dict[str, Any]:
        group = EditionGroupDAO.get_by_id(group_id)
        if not group:
            raise ValueError(f"版别组不存在: {group_id}")

        members = EditionGroupDAO.get_members(group_id)
        relations = EditionRelationDAO.get_by_group(group_id)

        member_reports = []
        for m in members:
            try:
                rep = self.generate_single_report(m["id"])
                member_reports.append(rep)
            except Exception:
                pass

        report = {
            "report_type": "group",
            "title": f"版别组研究报告 - {group.get('name', '未知')}",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "group": group,
            "members": members,
            "member_reports": member_reports,
            "relations": relations,
            "graph_image_path": None,
        }
        return report

    def generate_batch_report(
        self, rubbing_ids: List[int], title: str = "批量研究报告"
    ) -> Dict[str, Any]:
        reports = []
        for rid in rubbing_ids:
            try:
                rep = self.generate_single_report(rid)
                reports.append(rep)
            except Exception:
                pass

        report = {
            "report_type": "batch",
            "title": title,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(reports),
            "reports": reports,
            "graph_image_path": None,
        }
        return report

    def _get_import_records(self, rubbing: Dict[str, Any]) -> List[Dict[str, Any]]:
        file_hash = rubbing.get("file_hash")
        if not file_hash:
            return []
        records = []
        try:
            all_records = ImportRecordDAO.get_by_batch("")
        except Exception:
            all_records = []
        for r in all_records:
            if r.get("file_hash") == file_hash:
                records.append(r)
        return records

    def render_html(self, report: Dict[str, Any]) -> str:
        report_type = report.get("report_type")
        if report_type == "single":
            return self._render_single_html(report)
        elif report_type == "group":
            return self._render_group_html(report)
        elif report_type == "batch":
            return self._render_batch_html(report)
        else:
            return "<html><body><p>未知报告类型</p></body></html>"

    def _render_single_html(self, report: Dict[str, Any]) -> str:
        rubbing = report["rubbing"]
        code = _safe_str(rubbing.get("code"))
        era = _safe_str(rubbing.get("era"))
        inscription = _safe_str(rubbing.get("inscription"))
        material = _safe_str(rubbing.get("material"))
        excavation = _safe_str(rubbing.get("excavation_site"))
        has_contour = "是" if rubbing.get("has_valid_contour") else "否"
        w = rubbing.get("width")
        h = rubbing.get("height")
        size = f"{w} × {h}" if w and h else MISSING
        notes = _safe_str(rubbing.get("notes"))
        created_at = _safe_str(rubbing.get("created_at"))
        updated_at = _safe_str(rubbing.get("updated_at"))

        img_path = rubbing.get("processed_path") or rubbing.get("original_path")
        img_html = ""
        if img_path and os.path.exists(img_path):
            import base64
            with open(img_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")
            ext = Path(img_path).suffix.lstrip(".") or "png"
            img_html = f'<img src="data:image/{ext};base64,{img_data}" style="max-width:300px; max-height:300px; border:1px solid #ddd;"/>'

        graph_html = ""
        if report.get("graph_image_path") and os.path.exists(report["graph_image_path"]):
            import base64
            with open(report["graph_image_path"], "rb") as f:
                graph_data = base64.b64encode(f.read()).decode("utf-8")
            ext = Path(report["graph_image_path"]).suffix.lstrip(".") or "png"
            graph_html = f'''
            <div class="section">
                <h2>关系图谱</h2>
                <img src="data:image/{ext};base64,{graph_data}" style="max-width:600px; border:1px solid #ddd;"/>
            </div>
            '''

        similar_html = self._render_similar_items(report.get("similar_items", []))
        comparisons_html = self._render_comparisons(report.get("comparisons", []))
        feedbacks_html = self._render_feedbacks(report.get("feedbacks", []))
        groups_html = self._render_edition_groups(report.get("edition_groups", []))

        html = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{report["title"]}</title>
<style>
    body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 20px; color: #333; }}
    h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
    h2 {{ color: #2c3e50; margin-top: 24px; border-left: 4px solid #3498db; padding-left: 10px; }}
    .info-table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
    .info-table th, .info-table td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    .info-table th {{ background: #f5f7fa; width: 120px; font-weight: 600; }}
    .missing {{ color: #999; font-style: italic; }}
    .section {{ margin: 16px 0; }}
    .rubbing-image {{ text-align: center; margin: 16px 0; }}
    .similarity-bar {{ display: inline-block; height: 8px; background: #3498db; border-radius: 4px; }}
    .score-high {{ color: #27ae60; font-weight: bold; }}
    .score-mid {{ color: #f39c12; font-weight: bold; }}
    .score-low {{ color: #e74c3c; font-weight: bold; }}
    .meta {{ color: #666; font-size: 12px; margin-bottom: 16px; }}
    table.data-table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    table.data-table th, table.data-table td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
    table.data-table th {{ background: #f5f7fa; font-weight: 600; }}
    .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
    .tag-same {{ background: #d5f5e3; color: #1e8449; }}
    .tag-diff {{ background: #fadbd8; color: #922b21; }}
    .tag-forgery {{ background: #fdebd0; color: #b9770e; }}
    .tag-pending {{ background: #e8e8e8; color: #666; }}
    .conclusion-same {{ background: #d5f5e3; }}
    .conclusion-forgery {{ background: #fdebd0; }}
    .conclusion-diff {{ background: #fadbd8; }}
    .conclusion-pending {{ background: #f4f4f4; }}
</style>
</head>
<body>
    <h1>{report["title"]}</h1>
    <div class="meta">生成时间: {report["generated_at"]}</div>

    <div class="rubbing-image">{img_html}</div>

    <div class="section">
        <h2>一、拓片基本信息</h2>
        <table class="info-table">
            <tr><th>编号</th><td>{code}</td></tr>
            <tr><th>年代</th><td>{era}</td></tr>
            <tr><th>钱文</th><td>{inscription}</td></tr>
            <tr><th>材质</th><td>{material}</td></tr>
            <tr><th>出土地</th><td>{excavation}</td></tr>
            <tr><th>有效轮廓</th><td>{has_contour}</td></tr>
            <tr><th>尺寸</th><td>{size}</td></tr>
            <tr><th>创建时间</th><td>{created_at}</td></tr>
            <tr><th>更新时间</th><td>{updated_at}</td></tr>
            <tr><th>备注</th><td>{notes}</td></tr>
        </table>
    </div>

    <div class="section">
        <h2>二、版别组归属</h2>
        {groups_html}
    </div>

    <div class="section">
        <h2>三、相似候选 (Top 10)</h2>
        {similar_html}
    </div>

    <div class="section">
        <h2>四、对比结论</h2>
        {comparisons_html}
    </div>

    <div class="section">
        <h2>五、反馈记录</h2>
        {feedbacks_html}
    </div>

    {graph_html}
</body>
</html>
'''
        return html

    def _render_similar_items(self, items: List[Dict[str, Any]]) -> str:
        if not items:
            return '<p class="missing">暂无相似候选数据</p>'

        rows = []
        for i, item in enumerate(items, 1):
            code = _safe_str(item.get("code"))
            score = item.get("similarity_score", 0)
            contour_sim = item.get("contour_similarity", 0)
            texture_sim = item.get("texture_similarity", 0)
            score_str = f"{score:.1f}%"
            if score >= 70:
                score_cls = "score-high"
            elif score >= 40:
                score_cls = "score-mid"
            else:
                score_cls = "score-low"
            bar_width = max(10, int(score * 2))
            rows.append(f'''
                <tr>
                    <td>{i}</td>
                    <td>{code}</td>
                    <td class="{score_cls}">{score_str}</td>
                    <td>
                        <div class="similarity-bar" style="width:{bar_width}px;"></div>
                        {score:.0f}%
                    </td>
                    <td>{contour_sim:.1f}%</td>
                    <td>{texture_sim:.1f}%</td>
                </tr>
            ''')

        return f'''
        <table class="data-table">
            <thead>
                <tr><th>序号</th><th>编号</th><th>综合相似度</th><th>相似度示意</th><th>轮廓相似度</th><th>纹理相似度</th></tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
        <p style="color:#666; font-size:12px; margin-top:6px;">* 相似度范围: 0-100，数值越高越相似</p>
        '''

    def _render_comparisons(self, comparisons: List[Dict[str, Any]]) -> str:
        if not comparisons:
            return '<p class="missing">暂无对比结论记录</p>'

        rows = []
        for c in comparisons:
            code_a = _safe_str(c.get("code_a") or c.get("rubbing_a_id"))
            code_b = _safe_str(c.get("code_b") or c.get("rubbing_b_id"))
            score = _safe_num(c.get("similarity_score"), 1)
            conclusion = c.get("conclusion")
            conc_label = _conclusion_label(conclusion)
            conc_cls = "conclusion-pending"
            if conclusion == ComparisonDAO.CONCLUSION_SAME_EDITION:
                conc_cls = "conclusion-same"
            elif conclusion == ComparisonDAO.CONCLUSION_SUSPECTED_FORGERY:
                conc_cls = "conclusion-forgery"
            elif conclusion == ComparisonDAO.CONCLUSION_DIFFERENT:
                conc_cls = "conclusion-diff"
            notes = _safe_str(c.get("notes"))
            created_at = _safe_str(c.get("created_at"))
            rows.append(f'''
                <tr class="{conc_cls}">
                    <td>{code_a}</td>
                    <td>{code_b}</td>
                    <td>{score}%</td>
                    <td>{conc_label}</td>
                    <td>{notes}</td>
                    <td>{created_at}</td>
                </tr>
            ''')

        return f'''
        <table class="data-table">
            <thead>
                <tr><th>拓片A</th><th>拓片B</th><th>相似度</th><th>结论</th><th>备注</th><th>对比时间</th></tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
        '''

    def _render_feedbacks(self, feedbacks: List[Dict[str, Any]]) -> str:
        if not feedbacks:
            return '<p class="missing">暂无反馈记录</p>'

        rows = []
        for f in feedbacks:
            src_code = _safe_str(f.get("source_code") or f.get("source_rubbing_id"))
            tgt_code = _safe_str(f.get("target_code") or f.get("target_rubbing_id"))
            fb_type = f.get("feedback_type")
            fb_label = _feedback_label(fb_type)
            overall = _safe_num(f.get("overall_similarity"), 1)
            contour = _safe_num(f.get("contour_similarity"), 1)
            texture = _safe_num(f.get("texture_similarity"), 1)
            created_at = _safe_str(f.get("created_at"))
            rows.append(f'''
                <tr>
                    <td>{src_code}</td>
                    <td>{tgt_code}</td>
                    <td>{fb_label}</td>
                    <td>{overall}%</td>
                    <td>{contour}%</td>
                    <td>{texture}%</td>
                    <td>{created_at}</td>
                </tr>
            ''')

        return f'''
        <table class="data-table">
            <thead>
                <tr><th>源拓片</th><th>目标拓片</th><th>反馈类型</th><th>综合相似度</th><th>轮廓相似度</th><th>纹理相似度</th><th>反馈时间</th></tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
        '''

    def _render_edition_groups(self, groups: List[Dict[str, Any]]) -> str:
        if not groups:
            return '<p class="missing">未加入任何版别组</p>'

        items = []
        for g in groups:
            name = _safe_str(g.get("name"))
            era = _safe_str(g.get("era"))
            inscription = _safe_str(g.get("inscription"))
            desc = _safe_str(g.get("description"))
            items.append(f'''
                <div style="margin:8px 0; padding:10px; border:1px solid #ddd; border-radius:4px;">
                    <strong>{name}</strong>
                    <span style="color:#666; margin-left:8px;">年代: {era} | 钱文: {inscription}</span>
                    <div style="color:#666; font-size:12px; margin-top:4px;">描述: {desc}</div>
                </div>
            ''')
        return "".join(items)

    def _render_group_html(self, report: Dict[str, Any]) -> str:
        group = report["group"]
        name = _safe_str(group.get("name"))
        era = _safe_str(group.get("era"))
        inscription = _safe_str(group.get("inscription"))
        material = _safe_str(group.get("material"))
        desc = _safe_str(group.get("description"))
        created_at = _safe_str(group.get("created_at"))
        member_count = len(report.get("members", []))

        members_html = self._render_group_members(report.get("members", []))
        relations_html = self._render_group_relations(report.get("relations", []))

        member_reports_html = ""
        for i, mrep in enumerate(report.get("member_reports", []), 1):
            mrep_html = self._render_single_html(mrep)
            member_reports_html += f'<div class="member-report" style="page-break-before: always;"><h2>成员报告 {i}</h2>{mrep_html}</div>'

        graph_html = ""
        if report.get("graph_image_path") and os.path.exists(report["graph_image_path"]):
            import base64
            with open(report["graph_image_path"], "rb") as f:
                graph_data = base64.b64encode(f.read()).decode("utf-8")
            ext = Path(report["graph_image_path"]).suffix.lstrip(".") or "png"
            graph_html = f'''
            <div class="section">
                <h2>关系图谱</h2>
                <img src="data:image/{ext};base64,{graph_data}" style="max-width:600px; border:1px solid #ddd;"/>
            </div>
            '''

        html = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{report["title"]}</title>
<style>
    body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 20px; color: #333; }}
    h1 {{ color: #2c3e50; border-bottom: 2px solid #27ae60; padding-bottom: 10px; }}
    h2 {{ color: #2c3e50; margin-top: 24px; border-left: 4px solid #27ae60; padding-left: 10px; }}
    .info-table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
    .info-table th, .info-table td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    .info-table th {{ background: #f5f7fa; width: 120px; font-weight: 600; }}
    .missing {{ color: #999; font-style: italic; }}
    .section {{ margin: 16px 0; }}
    .meta {{ color: #666; font-size: 12px; margin-bottom: 16px; }}
    table.data-table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    table.data-table th, table.data-table td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
    table.data-table th {{ background: #f5f7fa; font-weight: 600; }}
    .member-report {{ margin-top: 32px; padding-top: 16px; border-top: 2px dashed #ddd; }}
</style>
</head>
<body>
    <h1>{report["title"]}</h1>
    <div class="meta">生成时间: {report["generated_at"]} | 成员数: {member_count}</div>

    <div class="section">
        <h2>一、版别组信息</h2>
        <table class="info-table">
            <tr><th>名称</th><td>{name}</td></tr>
            <tr><th>年代</th><td>{era}</td></tr>
            <tr><th>钱文</th><td>{inscription}</td></tr>
            <tr><th>材质</th><td>{material}</td></tr>
            <tr><th>成员数</th><td>{member_count} 个</td></tr>
            <tr><th>创建时间</th><td>{created_at}</td></tr>
            <tr><th>描述</th><td>{desc}</td></tr>
        </table>
    </div>

    <div class="section">
        <h2>二、成员列表</h2>
        {members_html}
    </div>

    <div class="section">
        <h2>三、组间关系</h2>
        {relations_html}
    </div>

    {graph_html}

    <div style="page-break-before: always;">
        <h1>成员详细报告</h1>
    </div>
    {member_reports_html}
</body>
</html>
'''
        return html

    def _render_group_members(self, members: List[Dict[str, Any]]) -> str:
        if not members:
            return '<p class="missing">暂无成员</p>'

        rows = []
        for i, m in enumerate(members, 1):
            code = _safe_str(m.get("code"))
            era = _safe_str(m.get("era"))
            inscription = _safe_str(m.get("inscription"))
            notes = _safe_str(m.get("member_notes"))
            joined_at = _safe_str(m.get("joined_at"))
            rows.append(f'''
                <tr>
                    <td>{i}</td>
                    <td>{code}</td>
                    <td>{era}</td>
                    <td>{inscription}</td>
                    <td>{notes}</td>
                    <td>{joined_at}</td>
                </tr>
            ''')

        return f'''
        <table class="data-table">
            <thead>
                <tr><th>序号</th><th>编号</th><th>年代</th><th>钱文</th><th>成员备注</th><th>加入时间</th></tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
        '''

    def _render_group_relations(self, relations: List[Dict[str, Any]]) -> str:
        if not relations:
            return '<p class="missing">暂无组间关系</p>'

        rows = []
        for r in relations:
            src_name = _safe_str(r.get("source_name") or r.get("source_group_id"))
            tgt_name = _safe_str(r.get("target_name") or r.get("target_group_id"))
            rel_type = _relation_label(r.get("relation_type"))
            notes = _safe_str(r.get("notes"))
            rows.append(f'''
                <tr>
                    <td>{src_name}</td>
                    <td>{tgt_name}</td>
                    <td>{rel_type}</td>
                    <td>{notes}</td>
                </tr>
            ''')

        return f'''
        <table class="data-table">
            <thead>
                <tr><th>源版别组</th><th>目标版别组</th><th>关系类型</th><th>备注</th></tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
        '''

    def _render_batch_html(self, report: Dict[str, Any]) -> str:
        count = report.get("count", 0)

        index_rows = []
        for i, rep in enumerate(report.get("reports", []), 1):
            rubbing = rep.get("rubbing", {})
            code = _safe_str(rubbing.get("code"))
            era = _safe_str(rubbing.get("era"))
            inscription = _safe_str(rubbing.get("inscription"))
            index_rows.append(f'''
                <tr>
                    <td>{i}</td>
                    <td>{code}</td>
                    <td>{era}</td>
                    <td>{inscription}</td>
                </tr>
            ''')

        reports_html = ""
        for i, rep in enumerate(report.get("reports", []), 1):
            rep_html = self._render_single_html(rep)
            reports_html += f'<div style="page-break-before: always;"><h2>报告 {i}</h2>{rep_html}</div>'

        html = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{report["title"]}</title>
<style>
    body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 20px; color: #333; }}
    h1 {{ color: #2c3e50; border-bottom: 2px solid #9b59b6; padding-bottom: 10px; }}
    h2 {{ color: #2c3e50; margin-top: 24px; border-left: 4px solid #9b59b6; padding-left: 10px; }}
    .info-table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
    .info-table th, .info-table td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    .info-table th {{ background: #f5f7fa; width: 120px; font-weight: 600; }}
    .missing {{ color: #999; font-style: italic; }}
    .section {{ margin: 16px 0; }}
    .meta {{ color: #666; font-size: 12px; margin-bottom: 16px; }}
    table.data-table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    table.data-table th, table.data-table td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
    table.data-table th {{ background: #f5f7fa; font-weight: 600; }}
</style>
</head>
<body>
    <h1>{report["title"]}</h1>
    <div class="meta">生成时间: {report["generated_at"]} | 共 {count} 份报告</div>

    <div class="section">
        <h2>目录</h2>
        <table class="data-table">
            <thead>
                <tr><th>序号</th><th>编号</th><th>年代</th><th>钱文</th></tr>
            </thead>
            <tbody>{''.join(index_rows)}</tbody>
        </table>
    </div>

    <div style="page-break-before: always;"></div>
    {reports_html}
</body>
</html>
'''
        return html

    def export_pdf(self, report: Dict[str, Any], output_path: str) -> bool:
        try:
            from PySide6.QtGui import QTextDocument, QPdfWriter, QPageSize
            from PySide6.QtCore import QMarginsF

            html = self.render_html(report)
            doc = QTextDocument()
            doc.setHtml(html)

            writer = QPdfWriter(output_path)
            writer.setPageSize(QPageSize(QPageSize.A4))
            writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageSize.Millimeter)
            writer.setResolution(300)
            writer.setTitle(report.get("title", "研究报告"))

            doc.print_(writer)
            return True
        except Exception as e:
            print(f"PDF导出失败: {e}")
            return False

    def export_image_package(
        self,
        report: Dict[str, Any],
        output_path: str,
        include_original: bool = True,
    ) -> bool:
        try:
            tmp_dir = tempfile.mkdtemp(prefix="rubbing_report_")
            try:
                report_data = self._collect_report_images(report, tmp_dir, include_original)

                readme_path = os.path.join(tmp_dir, "README.txt")
                with open(readme_path, "w", encoding="utf-8") as f:
                    f.write(f"{report['title']}\n")
                    f.write(f"生成时间: {report['generated_at']}\n")
                    f.write(f"=" * 50 + "\n\n")
                    f.write(report_data["summary"])

                with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(tmp_dir):
                        for fn in files:
                            fp = os.path.join(root, fn)
                            arcname = os.path.relpath(fp, tmp_dir)
                            zf.write(fp, arcname)

                return True
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as e:
            print(f"图片归档包导出失败: {e}")
            return False

    def _collect_report_images(
        self,
        report: Dict[str, Any],
        target_dir: str,
        include_original: bool,
    ) -> Dict[str, Any]:
        summary_lines = []
        report_type = report.get("report_type")

        if report_type == "single":
            self._collect_single_images(report, target_dir, include_original, summary_lines)
        elif report_type == "group":
            self._collect_group_images(report, target_dir, include_original, summary_lines)
        elif report_type == "batch":
            self._collect_batch_images(report, target_dir, include_original, summary_lines)

        return {"summary": "\n".join(summary_lines)}

    def _collect_single_images(
        self,
        report: Dict[str, Any],
        target_dir: str,
        include_original: bool,
        summary_lines: List[str],
    ) -> str:
        rubbing = report["rubbing"]
        code = rubbing.get("code", "unknown")
        subdir = os.path.join(target_dir, code)
        os.makedirs(subdir, exist_ok=True)

        img_path = rubbing.get("processed_path") or rubbing.get("original_path")
        if img_path and os.path.exists(img_path) and include_original:
            dst = os.path.join(subdir, f"{code}{Path(img_path).suffix}")
            shutil.copy2(img_path, dst)
            summary_lines.append(f"拓片图片: {code}{Path(img_path).suffix}")

        if report.get("graph_image_path") and os.path.exists(report["graph_image_path"]):
            dst = os.path.join(subdir, f"{code}_graph.png")
            shutil.copy2(report["graph_image_path"], dst)
            summary_lines.append("关系图谱截图: 已包含")

        info_path = os.path.join(subdir, f"{code}_info.txt")
        with open(info_path, "w", encoding="utf-8") as f:
            f.write(f"编号: {rubbing.get('code', '—')}\n")
            f.write(f"年代: {rubbing.get('era', '—')}\n")
            f.write(f"钱文: {rubbing.get('inscription', '—')}\n")
            f.write(f"材质: {rubbing.get('material', '—')}\n")
            f.write(f"出土地: {rubbing.get('excavation_site', '—')}\n")
            f.write(f"尺寸: {rubbing.get('width', '—')} × {rubbing.get('height', '—')}\n")
            f.write(f"有效轮廓: {'是' if rubbing.get('has_valid_contour') else '否'}\n")
            f.write(f"创建时间: {rubbing.get('created_at', '—')}\n")
            f.write(f"备注: {rubbing.get('notes', '—')}\n")

        similar_items = report.get("similar_items", [])
        if similar_items:
            sim_path = os.path.join(subdir, f"{code}_similar.txt")
            with open(sim_path, "w", encoding="utf-8") as f:
                f.write("相似候选 (Top 10):\n")
                f.write("-" * 40 + "\n")
                for i, item in enumerate(similar_items, 1):
                    f.write(f"{i}. {item.get('code', '—')} - "
                            f"综合: {item.get('similarity_score', 0):.1f}% "
                            f"(轮廓: {item.get('contour_similarity', 0):.1f}%, "
                            f"纹理: {item.get('texture_similarity', 0):.1f}%)\n")

        comparisons = report.get("comparisons", [])
        if comparisons:
            comp_path = os.path.join(subdir, f"{code}_comparisons.txt")
            with open(comp_path, "w", encoding="utf-8") as f:
                f.write("对比结论:\n")
                f.write("-" * 40 + "\n")
                for c in comparisons:
                    conc_label = _conclusion_label(c.get("conclusion"))
                    f.write(f"{c.get('code_a', '—')} vs {c.get('code_b', '—')} - "
                            f"相似度: {c.get('similarity_score', '—')}% - "
                            f"结论: {conc_label}\n")

        return subdir

    def _collect_group_images(
        self,
        report: Dict[str, Any],
        target_dir: str,
        include_original: bool,
        summary_lines: List[str],
    ):
        group = report["group"]
        group_name = group.get("name", "unknown_group")
        safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in group_name)
        group_dir = os.path.join(target_dir, safe_name)
        os.makedirs(group_dir, exist_ok=True)

        summary_lines.append(f"版别组: {group_name}")
        summary_lines.append(f"成员数: {len(report.get('members', []))}")

        if report.get("graph_image_path") and os.path.exists(report["graph_image_path"]):
            dst = os.path.join(group_dir, "relation_graph.png")
            shutil.copy2(report["graph_image_path"], dst)
            summary_lines.append("关系图谱截图: 已包含")

        for mrep in report.get("member_reports", []):
            self._collect_single_images(mrep, group_dir, include_original, [])

    def _collect_batch_images(
        self,
        report: Dict[str, Any],
        target_dir: str,
        include_original: bool,
        summary_lines: List[str],
    ):
        summary_lines.append(f"批量报告总数: {report.get('count', 0)}")
        for i, rep in enumerate(report.get("reports", []), 1):
            sub_summary = []
            self._collect_single_images(rep, target_dir, include_original, sub_summary)
            summary_lines.extend([f"[{i}] " + s for s in sub_summary])
