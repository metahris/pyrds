from __future__ import annotations

import pytest

from pyrds.application.services.qml_handler import QmlHandler
from pyrds.application.services.response_parser import ResponseParser
from pyrds.domain.exceptions import ResultParsingError
from tests.conftest import PRICE_RESULT_QML


def test_response_parser_extracts_raw_data_and_errors(logger) -> None:
    parser = ResponseParser(qml_handler=QmlHandler(logger=logger))
    response = {
        "responses": [
            {
                "psRequestKey": "req_1",
                "tradeId": "trade_1",
                "rawResults": [PRICE_RESULT_QML],
                "errors": [],
            },
            {
                "psRequestKey": "req_2",
                "tradeId": "trade_2",
                "rawResults": [],
                "errors": [{"message": "failed"}],
            },
        ]
    }

    raw_data, errors = parser.get_raw_data(response)

    assert raw_data == {"TradeA_req_1": PRICE_RESULT_QML}
    assert errors == {"0_req_2": {"message": "failed"}}


def test_response_parser_extracts_set_ids() -> None:
    response = {
        "responses": [
            {
                "marketDataSetIds": ["mkt_set"],
                "tradeSetId": "trade_set",
                "requestDataSetId": "request_set",
                "tradeId": "trade_1",
            }
        ]
    }

    assert ResponseParser.get_market_data_set_id(response) == "mkt_set"
    assert ResponseParser.get_trade_set_id(response) == "trade_set"
    assert ResponseParser.get_request_set_id(response) == "request_set"
    assert ResponseParser.get_trade_id(response) == "trade_1"


def test_response_parser_raises_when_response_has_no_raw_data(logger) -> None:
    parser = ResponseParser(qml_handler=QmlHandler(logger=logger))

    with pytest.raises(ResultParsingError):
        parser.get_raw_data({"responses": [{"rawResults": [], "errors": []}]})
