import os
import tempfile
from pathlib import Path

# 确保单元测试使用隔离的独立测试数据目录，杜绝触碰或清空生产数据库
_test_temp_dir = tempfile.TemporaryDirectory(prefix="dailymanager-test-")
os.environ["DAILY_MANAGER_DATA_DIR"] = str(Path(_test_temp_dir.name) / "test-data")
