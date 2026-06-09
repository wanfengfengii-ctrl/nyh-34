from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem,
    QGraphicsItemGroup, QLabel, QPushButton, QSlider, QComboBox,
    QGroupBox, QFormLayout, QListWidget, QListWidgetItem,
    QSplitter, QMessageBox,
)
from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QLineF
from PySide6.QtGui import QPen, QBrush, QColor, QFont, QPainter, QPixmap
from typing import List, Dict, Any, Optional
import math

from ..core.rubbing_service import RubbingService
from ..db.database import EditionRelationDAO


RELATION_COLORS = {
    EditionRelationDAO.RELATION_SAME_EDITION: QColor("#2ecc71"),
    EditionRelationDAO.RELATION_EVOLUTION: QColor("#3498db"),
    EditionRelationDAO.RELATION_SUSPECTED_FORGERY: QColor("#e74c3c"),
    EditionRelationDAO.RELATION_SOURCE_RELATION: QColor("#9b59b6"),
}


class EditionNodeItem(QGraphicsItemGroup):
    def __init__(self, group_data: Dict[str, Any], radius: int = 40, parent=None):
        super().__init__(parent)
        self._data = group_data
        self._radius = radius
        self._is_selected = False
        self.setAcceptHoverEvents(True)
        self._build_item()
        self.setFlag(QGraphicsItemGroup.ItemIsMovable, True)
        self.setFlag(QGraphicsItemGroup.ItemIsSelectable, True)
        self.setCursor(Qt.PointingHandCursor)

    def _build_item(self):
        r = self._radius
        member_count = self._data.get("member_count", 0)
        if member_count > 5:
            r = min(r + member_count * 2, 80)
            self._radius = r

        color = QColor("#4a90d9")
        if member_count == 0:
            color = QColor("#95a5a6")

        self._circle = QGraphicsEllipseItem(-r, -r, r * 2, r * 2)
        self._circle.setBrush(QBrush(color))
        self._circle.setPen(QPen(QColor("#2c3e50"), 2))
        self.addToGroup(self._circle)

        name = self._data.get("name", "")
        short_name = name[:6] + "..." if len(name) > 6 else name
        self._text = QGraphicsTextItem(short_name)
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        self._text.setFont(font)
        self._text.setDefaultTextColor(QColor("white"))
        text_rect = self._text.boundingRect()
        self._text.setPos(-text_rect.width() / 2, -text_rect.height() / 2 - 8)
        self.addToGroup(self._text)

        count_text = QGraphicsTextItem(f"{member_count}件")
        count_font = QFont()
        count_font.setPointSize(9)
        count_text.setFont(count_font)
        count_text.setDefaultTextColor(QColor("white"))
        count_rect = count_text.boundingRect()
        count_text.setPos(-count_rect.width() / 2, r - count_rect.height() - 8)
        self.addToGroup(count_text)

        self._count_text = count_text

    def data(self) -> Dict[str, Any]:
        return self._data

    def group_id(self) -> int:
        return self._data.get("id", 0)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        if selected:
            self._circle.setPen(QPen(QColor("#f39c12"), 4))
        else:
            self._circle.setPen(QPen(QColor("#2c3e50"), 2))

    def hoverEnterEvent(self, event):
        if not self._is_selected:
            self._circle.setPen(QPen(QColor("#f39c12"), 3))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if not self._is_selected:
            self._circle.setPen(QPen(QColor("#2c3e50"), 2))
        super().hoverLeaveEvent(event)


class EditionEdgeItem(QGraphicsLineItem):
    def __init__(self, source_pos: QPointF, target_pos: QPointF,
                 relation_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._data = relation_data
        self._source_pos = source_pos
        self._target_pos = target_pos
        self._setAcceptHoverEvents(True)
        self._build_item()

    def _build_item(self):
        rel_type = self._data.get("relation_type", "")
        color = RELATION_COLORS.get(rel_type, QColor("#95a5a6"))
        pen = QPen(color, 2)
        pen.setStyle(Qt.SolidLine)
        if rel_type == EditionRelationDAO.RELATION_SUSPECTED_FORGERY:
            pen.setStyle(Qt.DashLine)
        self.setPen(pen)
        self.setZValue(-1)

    def update_positions(self, source_pos: QPointF, target_pos: QPointF):
        self._source_pos = source_pos
        self._target_pos = target_pos
        line = QLineF(source_pos, target_pos)
        self.setLine(line)

    def data(self) -> Dict[str, Any]:
        return self._data

    def hoverEnterEvent(self, event):
        pen = self.pen()
        pen.setWidth(4)
        self.setPen(pen)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        pen = self.pen()
        pen.setWidth(2)
        self.setPen(pen)
        super().hoverLeaveEvent(event)


class EditionGraphView(QGraphicsView):
    nodeClicked = Signal(dict)
    edgeClicked = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#f8f9fa")))
        self._nodes: Dict[int, EditionNodeItem] = {}
        self._edges: List[EditionEdgeItem] = []
        self._selected_node: Optional[EditionNodeItem] = None
        self._scale_factor = 1.0

    def wheelEvent(self, event):
        zoom_in = 1.15
        zoom_out = 1 / zoom_in
        if event.angleDelta().y() > 0:
            self.scale(zoom_in, zoom_in)
            self._scale_factor *= zoom_in
        else:
            self.scale(zoom_out, zoom_out)
            self._scale_factor *= zoom_out

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            if isinstance(item, EditionNodeItem):
                self._select_node(item)
                self.nodeClicked.emit(item.data())
                super().mousePressEvent(event)
                return
            elif isinstance(item, EditionEdgeItem):
                self.edgeClicked.emit(item.data())
                super().mousePressEvent(event)
                return
            else:
                self._clear_selection()
        super().mousePressEvent(event)

    def _select_node(self, node: EditionNodeItem):
        if self._selected_node:
            self._selected_node.set_selected(False)
        self._selected_node = node
        node.set_selected(True)

    def _clear_selection(self):
        if self._selected_node:
            self._selected_node.set_selected(False)
            self._selected_node = None

    def set_graph_data(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        self._scene.clear()
        self._nodes.clear()
        self._edges.clear()
        self._selected_node = None

        if not nodes:
            return

        self._layout_circular(nodes)

        for node_data in nodes:
            node = EditionNodeItem(node_data)
            node.setPos(node_data["_x"], node_data["_y"])
            self._scene.addItem(node)
            self._nodes[node_data["id"]] = node

        for edge_data in edges:
            source_id = edge_data["source_group_id"]
            target_id = edge_data["target_group_id"]
            if source_id in self._nodes and target_id in self._nodes:
                source_node = self._nodes[source_id]
                target_node = self._nodes[target_id]
                edge = EditionEdgeItem(
                    source_node.pos(), target_node.pos(), edge_data
                )
                self._scene.addItem(edge)
                self._edges.append(edge)

        self._scene.setSceneRect(self._scene.itemsBoundingRect().adjusted(-100, -100, 100, 100))
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._scale_factor = 1.0

    def _layout_circular(self, nodes: List[Dict[str, Any]]):
        n = len(nodes)
        if n == 0:
            return
        radius = max(200, n * 40)
        center_x = 0
        center_y = 0
        for i, node in enumerate(nodes):
            angle = 2 * math.pi * i / n - math.pi / 2
            node["_x"] = center_x + radius * math.cos(angle)
            node["_y"] = center_y + radius * math.sin(angle)

    def highlight_group(self, group_id: int):
        self._clear_selection()
        if group_id in self._nodes:
            node = self._nodes[group_id]
            self._select_node(node)
            self.centerOn(node)

    def reset_view(self):
        self.resetTransform()
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._scale_factor = 1.0

    def get_selected_group_id(self) -> Optional[int]:
        if self._selected_node:
            return self._selected_node.group_id()
        return None

    def grab_graph_image(self) -> Optional[QPixmap]:
        if not self._scene or self._scene.itemsBoundingRect().isEmpty():
            return None
        rect = self._scene.itemsBoundingRect().adjusted(-50, -50, 50, 50)
        pixmap = QPixmap(rect.size().toSize())
        pixmap.fill(QColor("#f8f9fa"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self._scene.render(painter, pixmap.rect(), rect)
        painter.end()
        return pixmap


class EditionGraphWidget(QWidget):
    groupDoubleClicked = Signal(int)
    groupSelected = Signal(int)
    rubbingDoubleClicked = Signal(int)

    def __init__(self, service: RubbingService, parent=None):
        super().__init__(parent)
        self._service = service
        self._selected_group_id: Optional[int] = None
        self._build_ui()
        self._load_legend()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.btn_refresh = QPushButton("刷新图谱")
        self.btn_refresh.clicked.connect(self._on_refresh)
        toolbar.addWidget(self.btn_refresh)

        self.btn_reset = QPushButton("重置视图")
        self.btn_reset.clicked.connect(self._on_reset_view)
        toolbar.addWidget(self.btn_reset)

        toolbar.addStretch()

        toolbar.addWidget(QLabel("聚焦:"))
        self.focus_combo = QComboBox()
        self.focus_combo.currentIndexChanged.connect(self._on_focus_changed)
        toolbar.addWidget(self.focus_combo)

        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        self.graph_view = EditionGraphView()
        self.graph_view.nodeClicked.connect(self._on_node_clicked)
        splitter.addWidget(self.graph_view)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        legend_box = QGroupBox("图例")
        legend_layout = QFormLayout(legend_box)
        self._legend_labels = {}
        for rel_type, label in EditionRelationDAO.RELATION_LABELS.items():
            color_label = QLabel()
            color = RELATION_COLORS.get(rel_type, QColor("#999"))
            color_label.setStyleSheet(
                f"background: {color.name()}; min-height: 3px; max-height: 3px;"
            )
            self._legend_labels[rel_type] = color_label
            legend_layout.addRow(label, color_label)
        right_layout.addWidget(legend_box)

        info_box = QGroupBox("节点信息")
        info_layout = QVBoxLayout(info_box)
        self.info_label = QLabel("点击节点查看详情")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #666; padding: 8px;")
        info_layout.addWidget(self.info_label)

        self.btn_view_group = QPushButton("查看版别组详情")
        self.btn_view_group.clicked.connect(self._on_view_group)
        self.btn_view_group.setEnabled(False)
        info_layout.addWidget(self.btn_view_group)

        right_layout.addWidget(info_box)

        members_box = QGroupBox("关联拓片")
        members_layout = QVBoxLayout(members_box)
        self.members_list = QListWidget()
        self.members_list.itemDoubleClicked.connect(self._on_member_double_clicked)
        members_layout.addWidget(self.members_list)
        right_layout.addWidget(members_box, 1)

        right_layout.addStretch()
        splitter.addWidget(right_panel)
        splitter.setSizes([700, 300])

        layout.addWidget(splitter, 1)

    def _load_legend(self):
        pass

    def refresh(self):
        self._load_focus_combo()
        self._load_graph()

    def _load_focus_combo(self):
        current_id = self._selected_group_id
        self.focus_combo.clear()
        self.focus_combo.addItem("全部", None)
        groups = self._service.list_edition_groups()
        for g in groups:
            self.focus_combo.addItem(g.get("name", ""), g.get("id"))
        if current_id:
            idx = self.focus_combo.findData(current_id)
            if idx >= 0:
                self.focus_combo.setCurrentIndex(idx)

    def _load_graph(self):
        focus_id = self.focus_combo.currentData()
        if focus_id:
            data = self._service.get_subgraph_for_group(focus_id, max_depth=2)
        else:
            data = self._service.get_edition_graph_data()
        self.graph_view.set_graph_data(data["nodes"], data["edges"])
        if focus_id:
            self.graph_view.highlight_group(focus_id)

    def _on_refresh(self):
        self.refresh()

    def _on_reset_view(self):
        self.graph_view.reset_view()

    def _on_focus_changed(self, index: int):
        self._load_graph()

    def _on_node_clicked(self, node_data: Dict[str, Any]):
        group_id = node_data.get("id")
        self._selected_group_id = group_id
        self._update_info_panel(node_data)
        self._update_members_list(group_id)
        self.btn_view_group.setEnabled(True)
        self.groupSelected.emit(group_id)

    def _update_info_panel(self, node_data: Dict[str, Any]):
        name = node_data.get("name", "")
        era = node_data.get("era", "—") or "—"
        inscription = node_data.get("inscription", "—") or "—"
        member_count = node_data.get("member_count", 0)
        desc = node_data.get("description", "") or "—"

        info_text = (
            f"<b>名称:</b> {name}<br><br>"
            f"<b>年代:</b> {era}<br>"
            f"<b>钱文:</b> {inscription}<br>"
            f"<b>成员数:</b> {member_count} 个拓片<br><br>"
            f"<b>描述:</b><br>{desc}"
        )
        self.info_label.setText(info_text)

    def _update_members_list(self, group_id: int):
        self.members_list.clear()
        members = self._service.get_edition_group_members(group_id)
        if not members:
            item = QListWidgetItem("暂无拓片")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.members_list.addItem(item)
            return
        for m in members:
            item = QListWidgetItem(f"{m.get('code', '')} - {m.get('inscription', '—')}")
            item.setData(Qt.UserRole, m.get("id"))
            self.members_list.addItem(item)

    def _on_view_group(self):
        if self._selected_group_id:
            self.groupDoubleClicked.emit(self._selected_group_id)

    def _on_member_double_clicked(self, item: QListWidgetItem):
        rubbing_id = item.data(Qt.UserRole)
        if rubbing_id:
            self.rubbingDoubleClicked.emit(rubbing_id)

    def focus_on_group(self, group_id: int):
        idx = self.focus_combo.findData(group_id)
        if idx >= 0:
            self.focus_combo.setCurrentIndex(idx)

    def grab_graph_image(self) -> Optional[QPixmap]:
        return self.graph_view.grab_graph_image()
