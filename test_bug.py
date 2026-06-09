import sys
sys.path.insert(0, '.')

from PySide6.QtWidgets import QApplication
from rubbing_manager.ui.main_window import MainWindow
from rubbing_manager.ui.report_dialog import ReportDialog
from rubbing_manager.core.rubbing_service import RubbingService

app = QApplication.instance() or QApplication(sys.argv)

service = RubbingService()
print("Service created")

try:
    dlg = ReportDialog(service, mode='single')
    print("Dialog created successfully")
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
