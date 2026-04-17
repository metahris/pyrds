from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pyrds.application.runners.backtester import Backtester
from pyrds.application.services.qml_handler import QmlHandler
from pyrds.infrastructure.config.settings import FilesPath


def test_backtest_adjust_file_name_uses_historical_carto_token() -> None:
    assert (
        Backtester.adjust_file_name("YCSETUP_HISTO_20240102", "HISTO")
        == "YCSETUP|HISTO_20240102"
    )
    assert (
        Backtester.adjust_file_name("YCSETUP_HISTO_20240102", "HISTO_20240102")
        == "YCSETUP|HISTO_20240102"
    )
    assert (
        Backtester.adjust_file_name("YCSETUP_HISTO_20240103", "HISTO")
        == "YCSETUP|HISTO_20240103"
    )
    assert (
        Backtester.adjust_file_name("MODEL_6442_48_62_SwaptionMode_HISTO_20240102", "HISTO")
        == "MODEL_6442_48_62_SwaptionMode|HISTO_20240102"
    )
    assert (
        Backtester.adjust_file_name("MODEL_6442_48_62_SwaptionMode_HISTO_20240102", "HISTO_20240102")
        == "MODEL_6442_48_62_SwaptionMode|HISTO_20240102"
    )
    assert Backtester.adjust_file_name("QUOTE!USD_SOFR_1D", "HISTO_20240102") == "QUOTE!USD_SOFR_1D"


def test_backtest_market_data_uses_folder_historical_carto_when_payload_carto_is_base(tmp_path: Path, logger) -> None:
    root = tmp_path / "work"
    histo = root / "inputs" / "data" / "HISTO_20240102"
    histo.mkdir(parents=True)
    (root / "inputs" / "trade").mkdir(parents=True)
    (root / "results").mkdir(parents=True)
    (histo / "YCSETUP_HISTO_20240102.xml").write_text("<ycsetup />", encoding="utf-8")
    (histo / "QUOTE!USD_SOFR_1D.xml").write_text("<quote />", encoding="utf-8")
    (histo / "request_20240102.xml").write_text("<request />", encoding="utf-8")
    (histo / "instructionset_20240102.xml").write_text("<instructionset />", encoding="utf-8")

    runner = Backtester(
        logger=logger,
        files_path=FilesPath(working_dir=str(root)),
        qml_handler=QmlHandler(logger=logger),
        ps_api=SimpleNamespace(),
        market_api=SimpleNamespace(),
        trades_api=SimpleNamespace(),
        request_set_tags={"request", "instructionset"},
    )

    market_data = runner.get_mkt_data_qmls_for_path(str(histo), carto="BASE")

    assert "YCSETUP|HISTO_20240102" in market_data
    assert "YCSETUP_HISTO_20240102" not in market_data
    assert "QUOTE!USD_SOFR_1D" in market_data


def test_backtest_market_data_keeps_date_suffix_when_payload_carto_is_histo(tmp_path: Path, logger) -> None:
    root = tmp_path / "work"
    histo = root / "inputs" / "data" / "HISTO"
    histo.mkdir(parents=True)
    (root / "inputs" / "trade").mkdir(parents=True)
    (root / "results").mkdir(parents=True)
    (histo / "YCSETUP_HISTO_20240102.xml").write_text("<ycsetup />", encoding="utf-8")
    (histo / "YCSETUP_HISTO_20240103.xml").write_text("<ycsetup />", encoding="utf-8")
    (histo / "MODEL_6442_48_62_SwaptionMode_HISTO_20240102.xml").write_text("<model />", encoding="utf-8")

    runner = Backtester(
        logger=logger,
        files_path=FilesPath(working_dir=str(root)),
        qml_handler=QmlHandler(logger=logger),
        ps_api=SimpleNamespace(),
        market_api=SimpleNamespace(),
        trades_api=SimpleNamespace(),
        request_set_tags={"request", "instructionset"},
    )

    market_data = runner.get_mkt_data_qmls_for_path(str(histo), carto="HISTO")

    assert "YCSETUP|HISTO_20240102" in market_data
    assert "YCSETUP|HISTO_20240103" in market_data
    assert "MODEL_6442_48_62_SwaptionMode|HISTO_20240102" in market_data
    assert "YCSETUP|HISTO" not in market_data
