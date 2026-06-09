import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import font_manager
from typing import List, Dict, Any, Optional, Tuple
import platform
import cv2

from .image_processor import to_grayscale, find_main_contour, draw_contour_on_image
from ..db.database import blob_to_array


def _setup_chinese_font():
    system = platform.system()
    font_candidates = []
    if system == "Darwin":
        font_candidates = ["PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS"]
    elif system == "Windows":
        font_candidates = ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi"]
    else:
        font_candidates = ["WenQuanYi Zen Hei", "Noto Sans CJK SC", "Source Han Sans CN"]

    available_fonts = {f.name for f in font_manager.fontManager.ttflist}
    for font_name in font_candidates:
        if font_name in available_fonts:
            plt.rcParams["font.sans-serif"] = [font_name]
            plt.rcParams["axes.unicode_minus"] = False
            return font_name
    plt.rcParams["axes.unicode_minus"] = False
    return None


_setup_chinese_font()


class SimilarityChartCanvas(FigureCanvas):
    def __init__(self, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.axes = self.fig.add_subplot(111)

    def plot_similarity_bar(
        self,
        labels: List[str],
        scores: List[float],
        title: str = "相似度对比",
    ):
        self.axes.clear()
        colors = ["#2ecc71" if s >= 70 else "#f39c12" if s >= 40 else "#e74c3c"
                  for s in scores]
        bars = self.axes.bar(labels, scores, color=colors)
        self.axes.set_ylabel("相似度 (%)")
        self.axes.set_title(title)
        self.axes.set_ylim(0, 100)
        for bar, score in zip(bars, scores):
            self.axes.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{score:.1f}%",
                ha="center", va="bottom", fontsize=9,
            )
        self.fig.tight_layout()
        self.draw()

    def plot_radar_chart(
        self,
        categories: List[str],
        values_a: List[float],
        values_b: List[float],
        label_a: str = "拓片A",
        label_b: str = "拓片B",
    ):
        self.axes.clear()
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        values_a += values_a[:1]
        values_b += values_b[:1]
        angles += angles[:1]

        ax = self.fig.add_subplot(111, polar=True)
        self.fig.delaxes(self.axes)
        self.axes = ax

        ax.plot(angles, values_a, "o-", linewidth=2, label=label_a, color="#3498db")
        ax.fill(angles, values_a, alpha=0.25, color="#3498db")
        ax.plot(angles, values_b, "o-", linewidth=2, label=label_b, color="#e74c3c")
        ax.fill(angles, values_b, alpha=0.25, color="#e74c3c")

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories)
        ax.set_ylim(0, 100)
        ax.set_title("特征维度对比", pad=20)
        ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
        self.fig.tight_layout()
        self.draw()

    def plot_histogram(
        self,
        data: List[float],
        bins: int = 20,
        title: str = "相似度分布",
        xlabel: str = "相似度 (%)",
    ):
        self.axes.clear()
        self.axes.hist(data, bins=bins, color="#3498db", edgecolor="white", alpha=0.8)
        self.axes.set_title(title)
        self.axes.set_xlabel(xlabel)
        self.axes.set_ylabel("数量")
        self.fig.tight_layout()
        self.draw()

    def plot_feature_comparison(
        self,
        feat_a: np.ndarray,
        feat_b: np.ndarray,
        title: str = "特征向量对比",
    ):
        self.axes.clear()
        x = np.arange(len(feat_a))
        self.axes.plot(x, feat_a, label="拓片A", linewidth=1.5, alpha=0.8, color="#3498db")
        self.axes.plot(x, feat_b, label="拓片B", linewidth=1.5, alpha=0.8, color="#e74c3c")
        self.axes.fill_between(x, feat_a, feat_b, alpha=0.2, color="#95a5a6")
        self.axes.set_title(title)
        self.axes.set_xlabel("特征维度")
        self.axes.set_ylabel("特征值")
        self.axes.legend()
        self.fig.tight_layout()
        self.draw()

    def clear(self):
        self.axes.clear()
        self.draw()


def render_contour_overlay(img_path: str) -> Optional[np.ndarray]:
    try:
        img = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if img is None:
            return None
        gray = to_grayscale(img)
        contour, valid = find_main_contour(gray)
        if not valid or contour is None:
            return img
        result = draw_contour_on_image(img, contour, color=(0, 255, 0), thickness=2)
        return result
    except Exception:
        return None


def generate_similarity_report_figure(
    rubbing_a: Dict[str, Any],
    rubbing_b: Dict[str, Any],
    similarity_data: Dict[str, Any],
) -> Figure:
    fig = Figure(figsize=(10, 6))

    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

    ax1 = fig.add_subplot(gs[0, 0])
    categories = ["综合", "轮廓", "纹理"]
    scores = [
        similarity_data.get("similarity_score", 0),
        similarity_data.get("contour_similarity", 0),
        similarity_data.get("texture_similarity", 0),
    ]
    colors = ["#2ecc71" if s >= 70 else "#f39c12" if s >= 40 else "#e74c3c"
              for s in scores]
    bars = ax1.bar(categories, scores, color=colors)
    ax1.set_ylabel("相似度 (%)")
    ax1.set_title("相似度分析")
    ax1.set_ylim(0, 100)
    for bar, score in zip(bars, scores):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            f"{score:.1f}%",
            ha="center", va="bottom", fontsize=9,
        )

    ax2 = fig.add_subplot(gs[0, 1])
    feat_a_contour = blob_to_array(rubbing_a.get("contour_feature"))
    feat_b_contour = blob_to_array(rubbing_b.get("contour_feature"))
    if feat_a_contour is not None and feat_b_contour is not None:
        x = np.arange(min(len(feat_a_contour), len(feat_b_contour)))
        ax2.plot(x, feat_a_contour[:len(x)], label=rubbing_a.get("code", "A"),
                 linewidth=1.5, alpha=0.8)
        ax2.plot(x, feat_b_contour[:len(x)], label=rubbing_b.get("code", "B"),
                 linewidth=1.5, alpha=0.8)
        ax2.set_title("轮廓特征对比")
        ax2.set_xlabel("维度")
        ax2.legend(fontsize=8)
    else:
        ax2.text(0.5, 0.5, "无轮廓特征数据", ha="center", va="center",
                 transform=ax2.transAxes)
        ax2.set_title("轮廓特征对比")

    ax3 = fig.add_subplot(gs[1, 0])
    feat_a_tex = blob_to_array(rubbing_a.get("texture_feature"))
    feat_b_tex = blob_to_array(rubbing_b.get("texture_feature"))
    if feat_a_tex is not None and feat_b_tex is not None:
        x = np.arange(min(len(feat_a_tex), len(feat_b_tex)))
        ax3.plot(x, feat_a_tex[:len(x)], label=rubbing_a.get("code", "A"),
                 linewidth=1, alpha=0.8)
        ax3.plot(x, feat_b_tex[:len(x)], label=rubbing_b.get("code", "B"),
                 linewidth=1, alpha=0.8)
        ax3.set_title("纹理特征对比")
        ax3.set_xlabel("维度")
        ax3.legend(fontsize=8)
    else:
        ax3.text(0.5, 0.5, "无纹理特征数据", ha="center", va="center",
                 transform=ax3.transAxes)
        ax3.set_title("纹理特征对比")

    ax4 = fig.add_subplot(gs[1, 1])
    conclusions = ["同版", "疑似仿品", "不同版", "待确认"]
    counts = [0, 0, 0, 0]
    from ..db.database import ComparisonDAO
    all_comps = ComparisonDAO.list_all()
    for c in all_comps:
        conc = c.get("conclusion", "")
        if conc == ComparisonDAO.CONCLUSION_SAME_EDITION:
            counts[0] += 1
        elif conc == ComparisonDAO.CONCLUSION_SUSPECTED_FORGERY:
            counts[1] += 1
        elif conc == ComparisonDAO.CONCLUSION_DIFFERENT:
            counts[2] += 1
        else:
            counts[3] += 1
    colors_pie = ["#2ecc71", "#e74c3c", "#3498db", "#95a5a6"]
    if sum(counts) > 0:
        ax4.pie(counts, labels=conclusions, colors=colors_pie, autopct="%1.0f%%",
                startangle=90)
        ax4.set_title("全局对比结论分布")
    else:
        ax4.text(0.5, 0.5, "暂无对比记录", ha="center", va="center",
                 transform=ax4.transAxes)
        ax4.set_title("全局对比结论分布")

    return fig
