from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd
from lxml import etree

from pyrds.domain.exceptions import QmlVerificationError, ResultParsingError, SerializationError


class QmlHandler:
    def __init__(self, logger: Any | None = None) -> None:
        self.logger = logger

    def load_qml(self, file_path: str) -> str:
        try:
            return Path(file_path).read_text(encoding="utf-8")
        except Exception as exc:
            raise SerializationError(f"Failed to load QML file: {file_path}") from exc

    def load_qmls(self, folder_path: str) -> dict[str, dict[str, str]]:
        folder = Path(folder_path)
        if not folder.exists():
            raise SerializationError(f"QML folder does not exist: {folder_path}")

        output: dict[str, dict[str, str]] = {}
        for file_path in sorted(folder.glob("*.xml")):
            raw_data = self.load_qml(str(file_path))
            output[file_path.stem] = {
                "data_type": self.get_root_tag(raw_data),
                "raw_data": raw_data,
            }
        return output

    def dump_qml(self, *, dump_path: str, data: str | dict[str, str]) -> None:
        path = Path(dump_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = (
            "\n".join(f"<!-- {key} -->\n{value}" for key, value in data.items())
            if isinstance(data, dict)
            else data
        )
        try:
            path.write_text(content, encoding="utf-8")
        except Exception as exc:
            raise SerializationError(f"Failed to dump QML file: {dump_path}") from exc

    def dump_qml_concurrent(self, *, output_dir: str, data: dict[str, str]) -> None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        for key, value in data.items():
            safe_name = key.replace("|", "-").replace("/", "_")
            self.dump_qml(dump_path=str(output_path / f"{safe_name}.xml"), data=value)

    def verify_request_qml(self, *, request_qml: str) -> str:
        root = self._parse_xml(request_qml)
        if self._local_name(root.tag) != "request":
            raise QmlVerificationError("Request QML root must be 'request'.")
        return request_qml

    def verify_instruction_set_qml(self, *, instruction_set_qml: str, ps_request: Any | None = None) -> None:
        if not instruction_set_qml:
            return
        root = self._parse_xml(instruction_set_qml)
        if self._local_name(root.tag) != "instructionset":
            raise QmlVerificationError("Instruction set QML root must be 'instructionset'.")

    def get_root_tag(self, qml: str) -> str:
        return self._local_name(self._parse_xml(qml).tag)

    def get_product_name(self, result_qml: str) -> str | None:
        root = self._parse_xml(result_qml)
        request = root.find("request")
        if request is not None:
            product = request.find("product")
            if product is not None and product.text:
                return product.text.strip()

        product_name = root.find(".//ProductName")
        if product_name is not None and product_name.text:
            return product_name.text.strip()
        return None

    def parse_result_price(self, result_qml: str | None = None, *, qml: str | None = None) -> dict[str, Any]:
        root = self._parse_xml(result_qml or qml or "")
        parsed: dict[str, Any] = {}
        for instr in root.findall("instruction"):
            instr_name = instr.get("name")
            if instr_name == "PRICE":
                parsed.update(self._parse_price_instruction(instr))
            elif instr_name == "BACKPRICE":
                parsed.update(self._parse_backprice_instruction(instr))
            elif instr_name == "DELTAIR":
                parsed.update(self._parse_deltair_price_refs(instr))
        return parsed

    def parse_result_vegair(self, result_qml: str) -> dict[str, Any] | list[dict[str, Any]]:
        root = self._parse_xml(result_qml)
        scenarios = root.findall("scenario")
        if scenarios:
            return {
                scenario.get("name") or "WITHOUT_STRESS": self._parse_vector_instruction(
                    scenario.find("results"),
                    instruction_name="VEGAIR",
                    split_maturity_tenor=True,
                )
                for scenario in scenarios
            }
        return self._parse_vector_instruction(root, instruction_name="VEGAIR", split_maturity_tenor=True)

    def parse_result_deltair(self, result_qml: str) -> dict[str, Any] | list[dict[str, Any]]:
        root = self._parse_xml(result_qml)
        scenarios = root.findall("scenario")
        if scenarios:
            return {
                scenario.get("name") or "WITHOUT_STRESS": self._parse_vector_instruction(
                    scenario.find("results"),
                    instruction_name="DELTAIR",
                    split_maturity_tenor=False,
                )
                for scenario in scenarios
            }
        return self._parse_vector_instruction(root, instruction_name="DELTAIR", split_maturity_tenor=False)

    def get_fx_tree(self, *, qml: str) -> list[dict[str, Any]]:
        root = self._parse_xml(qml)
        fx_spots = root.find("fxspots")
        if fx_spots is None:
            return []
        return [
            {
                "asset": self._required_text(item, "asset"),
                "basis": self._required_text(item, "basis"),
                "value": float(self._required_text(item, "value")),
            }
            for item in fx_spots.findall("item")
        ]

    def get_at_bu_curves(self, result_qml: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        root = self._parse_xml(result_qml)
        price_instruction = self._find_instruction(root, "PRICE")
        curves = price_instruction.find("./model/exotic/modelData/curves")
        if curves is None:
            raise ResultParsingError("Could not find PRICE model curves.")
        return self._curve_to_dataframe(curves.find("at")), self._curve_to_dataframe(curves.find("bu"))

    def get_valdate_from_price_instruction(self, instruction_set_qml: str) -> str:
        root = self._parse_xml(instruction_set_qml)
        for tag in ("ValuationDate", "valuationDate", "date"):
            node = root.find(f".//{tag}")
            if node is not None and node.text:
                return node.text.strip()
        raise ResultParsingError("Could not find valuation date in instruction set QML.")

    @staticmethod
    def override_in_xpath(qml: str, overrides: list[Any]) -> str:
        try:
            root = etree.fromstring(qml.encode("utf-8"))
        except Exception as exc:
            raise SerializationError("Invalid QML XML.") from exc

        for override in overrides:
            xpath_expr = getattr(override, "path", None)
            if not xpath_expr:
                continue
            for node in root.xpath(xpath_expr):
                if isinstance(node, etree._Element):
                    node.text = str(getattr(override, "value", ""))
        return etree.tostring(root, encoding="unicode")

    def update_block_in_qml(self, *, qml: str, block: str, data_id: str) -> str:
        root = self._parse_xml(qml)
        replacement = self._parse_xml(block)
        replacement_tag = self._local_name(replacement.tag)
        for parent in root.iter():
            for index, child in enumerate(list(parent)):
                if self._local_name(child.tag) == replacement_tag:
                    parent[index] = replacement
                    return ET.tostring(root, encoding="unicode")
        raise ResultParsingError(f"Could not find block '{replacement.tag}' in QML '{data_id}'.")

    def update_request_with_mult_add_shift_scenarios(self, *, request_qml: str, stresses_request: Any) -> str:
        return request_qml

    def get_override_qml_values(self, *, qml: str) -> dict[str, Any]:
        return {}

    def _parse_price_instruction(self, instruction: ET.Element) -> dict[str, Any]:
        output = instruction.find("output")
        if output is None:
            return {}
        parsed: dict[str, Any] = {}
        for item in output.findall("item"):
            item_name = item.get("name") or "UNKNOWN"
            parsed[item_name] = {
                "price": self._optional_text(item, "price"),
                "currency": self._optional_text(item, "currency"),
            }
        return parsed

    def _parse_backprice_instruction(self, instruction: ET.Element) -> dict[str, Any]:
        backprices = instruction.find("backprices")
        if backprices is None:
            return {}
        parsed: dict[str, Any] = {"PRICE": {}}
        for item in backprices.findall("item"):
            key = self._required_text(item, "key")
            total_item = item.find("./val/output/item[@name='total']")
            if total_item is None:
                continue
            parsed["PRICE"][key] = {
                "total": float(self._required_text(total_item, "price")),
                "currency": self._required_text(total_item, "currency"),
            }
        return parsed

    def _parse_deltair_price_refs(self, instruction: ET.Element) -> dict[str, Any]:
        parsed: dict[str, Any] = {"DELTAIR": {}}
        for hedge in instruction.findall("./values/hedges/hedge"):
            curve = hedge.get("data") or "UNKNOWN"
            for item in hedge.findall("./output/item"):
                ref_value = item.find("refValue")
                if ref_value is None or self._optional_text(ref_value, "type") != "PRICE":
                    continue
                parsed["DELTAIR"][curve] = {
                    "item": item.get("name"),
                    "price": self._optional_text(ref_value, "value"),
                    "currency": self._optional_text(ref_value, "currency"),
                }
        return parsed

    def _parse_vector_instruction(
        self,
        root: ET.Element | None,
        *,
        instruction_name: str,
        split_maturity_tenor: bool,
    ) -> list[dict[str, Any]]:
        if root is None:
            return []
        curves: list[dict[str, Any]] = []
        for instr in root.findall("instruction"):
            if instr.get("name") != instruction_name:
                continue
            for hedge in instr.findall("./values/hedges/hedge"):
                items: list[dict[str, Any]] = []
                for item in hedge.findall("./output/item"):
                    points = [
                        self._parse_vector_row(row, split_maturity_tenor=split_maturity_tenor)
                        for row in item.findall("./vector/row")
                    ]
                    items.append({"item": item.get("name"), "points": points})
                curves.append({"curve": hedge.get("data"), "items": items})
        return curves

    @staticmethod
    def _parse_vector_row(row: ET.Element, *, split_maturity_tenor: bool) -> dict[str, Any]:
        name = row.get("name") or ""
        if split_maturity_tenor and "-" in name:
            maturity, tenor = name.split("-", 1)
            return {"maturity": maturity, "tenor": tenor, "value": float(row.text or 0)}
        return {"maturity": name, "value": float(row.text or 0)}

    def _find_instruction(self, root: ET.Element, instruction_name: str) -> ET.Element:
        for instruction in root.findall("instruction"):
            if instruction.get("name") == instruction_name:
                return instruction
        raise ResultParsingError(f"Could not find instruction '{instruction_name}'.")

    @staticmethod
    def _curve_to_dataframe(curve: ET.Element | None) -> pd.DataFrame:
        if curve is None:
            return pd.DataFrame({"x": [], "y": []})
        x_values = [float(item.text or 0) for item in curve.findall("./x/item")]
        y_values = [float(item.text or 0) for item in curve.findall("./y/item")]
        return pd.DataFrame({"x": x_values, "y": y_values})

    @staticmethod
    def _parse_xml(xml_text: str) -> ET.Element:
        try:
            return ET.fromstring(xml_text)
        except Exception as exc:
            raise SerializationError("Invalid QML XML.") from exc

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    @staticmethod
    def _optional_text(parent: ET.Element, tag: str) -> str | None:
        node = parent.find(tag)
        if node is None or node.text is None:
            return None
        return node.text.strip()

    @classmethod
    def _required_text(cls, parent: ET.Element, tag: str) -> str:
        value = cls._optional_text(parent, tag)
        if value is None:
            raise ResultParsingError(f"Missing required XML tag '{tag}'.")
        return value
