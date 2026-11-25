import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[1]))

from eval.rcaeval.baselines import _prepare_metrics
from eval.rcaeval.common import Case


def _case(tmp_path: Path, frame: pd.DataFrame, inject: int) -> Case:
    case_path = tmp_path / "re2ob_checkoutservice_cpu_1"
    case_path.mkdir()
    frame.to_parquet(case_path / "metrics.parquet")
    (case_path / "inject_time.txt").write_text(str(inject))
    return Case(case_path, "re2ob", "checkoutservice", "cpu", "1")


def test_prepare_metrics_mirrors_rcaeval_main_py(tmp_path: Path):
    frame = pd.DataFrame(
        {
            "time": [4, 1, 2, 3],
            "checkoutservice_cpu": [4.0, 1.0, np.nan, np.inf],
            "checkoutservice_latency-50": [1, 2, 3, 4],
            "checkoutservice_latency-90": [5, 6, 7, 8],
        }
    )
    result = _prepare_metrics(_case(tmp_path, frame, inject=3), window_rows=1)
    assert list(result.columns) == ["time", "checkoutservice_cpu", "checkoutservice_latency"]
    assert result["time"].tolist() == [2, 3]
    assert result["checkoutservice_cpu"].tolist() == [1.0, 1.0]
