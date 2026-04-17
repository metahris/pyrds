from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from xml.etree import ElementTree as ET

from pyrds.application.services.log_context import log_info
from pyrds.domain.exceptions import QmlVerificationError, ResultParsingError, SerializationError
from pyrds.domain.stress_models import (
    StressAffineDeformation,
    StressAffineDeformations,
    StressFactors,
)


class QmlHandler:
    def __init__(self, logger: Any | None = None) -> None:
        self.logger = logger

    def load_qml(self, file_path: str) -> str:
        try:
            return self.clean_qml(Path(file_path).read_text(encoding="utf-8"))
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
        try:
            if isinstance(data, dict):
                for key, value in data.items():
                    safe_key = self._safe_file_part(key)
                    item_path = path.with_name(f"{path.stem}_{safe_key}.xml")
                    item_path.write_text(self.format_qml(value), encoding="utf-8")
                return
            path.write_text(self.format_qml(data), encoding="utf-8")
        except Exception as exc:
            raise SerializationError(f"Failed to dump QML file: {dump_path}") from exc

    def dump_qml_concurrent(self, *, output_dir: str, data: dict[str, str]) -> None:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        for key, value in data.items():
            safe_name = self._safe_file_part(key)
            self.dump_qml(dump_path=str(output_path / f"{safe_name}.xml"), data=value)

    def verify_request_qml(self, *, request_qml: str) -> str:
        log_info(self.logger, "Verifying request QML")
        root = self._parse_xml(request_qml)
        if self._local_name(root.tag) != "request":
            raise QmlVerificationError("Request QML root must be 'request'.")

        request_root = root
        if root.get("type") == "MULTI BYSCENARIO":
            base_request = root.find("base_request")
            if base_request is not None:
                request_root = base_request

        self._require_request_text(
            request_root,
            "product",
            "!{PRODUCT}",
            label="product tag of the request qml",
        )
        self._require_request_text(
            request_root,
            "instructionset",
            "!{INSTRUCTIONSET}",
            label="instructionset tag of the request qml",
        )
        self._require_request_text(
            request_root,
            "pricingparam",
            "!{PRICINGPARAM}",
            label="pricingparam tag of the request qml",
        )
        self._require_request_text(
            request_root,
            "./gridConfiguration/distribute",
            "true",
            label="distribute tag of the gridConfiguration",
        )

        result = self.clean_qml(ET.tostring(root, encoding="unicode"))
        log_info(
            self.logger,
            "Request QML verified",
            request_type=root.get("type"),
        )
        return result

    def verify_instruction_set_qml(self, *, instruction_set_qml: str, ps_request: Any | None = None) -> None:
        log_info(self.logger, "Verifying instruction set QML")
        if not instruction_set_qml:
            raise QmlVerificationError("Instruction set QML is required.")
        root = self._parse_xml(instruction_set_qml)
        if self._local_name(root.tag) != "instructionset":
            raise QmlVerificationError("Instruction set QML root must be 'instructionset'.")

        instructions = root.find("instructions")
        if instructions is None:
            raise QmlVerificationError("Instruction set QML must contain an instructions block.")

        expected_date = self._extract_ps_request_date(ps_request) if ps_request is not None else None
        instruction_items = instructions.findall("item")
        if not instruction_items:
            raise QmlVerificationError("Instruction set QML instructions block must contain at least one item.")

        for index, item in enumerate(instruction_items, start=1):
            instruction_type = item.get("type")
            is_price = instruction_type == "PRICE"
            for tag in ("valdate", "filterDateCCF"):
                if is_price:
                    self._require_instruction_text(
                        item,
                        tag,
                        index=index,
                        instruction_type=instruction_type,
                    )
                if expected_date is not None:
                    self._verify_instruction_date(
                        item=item,
                        tag=tag,
                        expected_date=expected_date,
                        index=index,
                    )

            market_data_env = (
                self._require_instruction_text(
                    item,
                    "mktdataenv",
                    index=index,
                    instruction_type=instruction_type,
                )
                if is_price
                else self._optional_text(item, "mktdataenv")
            )
            if market_data_env is not None and market_data_env != "BASE":
                raise QmlVerificationError(
                    "mktdataenv in instructionset must be BASE "
                    f"for item {index}, got {market_data_env}."
                )

        log_info(
            self.logger,
            "Instruction set QML verified",
            instruction_count=len(instruction_items),
            expected_date=str(expected_date) if expected_date is not None else None,
        )

    def get_root_tag(self, qml: str) -> str:
        return self._local_name(self._parse_xml(qml).tag)

    def get_qml_type(self, qml: str) -> str:
        return self.get_root_tag(qml)

    @staticmethod
    def clean_qml(qml: str) -> str:
        return qml.replace("\n", "").replace("\t", "")

    @classmethod
    def format_qml(cls, qml: str) -> str:
        root = cls._parse_xml(qml)
        ET.indent(root)
        return ET.tostring(root, encoding="unicode")

    @classmethod
    def get_root_content(cls, qml: str | None) -> str | None:
        if not qml:
            return None
        root = cls._parse_xml(qml)
        return "".join(ET.tostring(child, encoding="unicode") for child in root)

    @staticmethod
    def delete_junk(qml: str, qml_type: str) -> str:
        closing_tag = f"</{qml_type}>"
        closing_tag_position = qml.find(closing_tag)
        if closing_tag_position == -1:
            return qml
        return qml[: closing_tag_position + len(closing_tag)]

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
        scenarios = root.findall("scenario")
        if scenarios:
            return {
                scenario.get("name") or "WITHOUT_STRESS": self._parse_price_container(
                    scenario.find("results")
                )
                for scenario in scenarios
            }
        return self._parse_price_container(root)

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

    def parse_calibrator_results(self, result_qml: str) -> dict[str, Any]:
        root = self._parse_xml(result_qml)
        product_name = self.get_product_name(result_qml)
        scenarios = root.findall("scenario")

        if scenarios:
            return {
                scenario.get("name") or "WITHOUT_STRESS": self._parse_calibration_container(
                    scenario.find("results")
                )
                for scenario in scenarios
            }

        parsed = self._parse_calibration_container(root)
        if not parsed:
            return {
                "product_name": product_name,
                "calibration_info": None,
                "calibration_result": None,
            }
        parsed.setdefault("product_name", product_name)
        return parsed

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

    def get_at_bu_curves(self, result_qml: str) -> tuple[Any, Any]:
        root = self._parse_xml(result_qml)
        price_instruction = self._find_instruction(root, "PRICE")
        curves = price_instruction.find("./model/exotic/modelData/curves")
        if curves is None:
            raise ResultParsingError("Could not find PRICE model curves.")
        return self._curve_to_dataframe(curves.find("at")), self._curve_to_dataframe(curves.find("bu"))

    def get_valdate_from_price_instruction(self, instruction_set_qml: str) -> str:
        root = self._parse_xml(instruction_set_qml)
        instructions = root.find("instructions")
        if instructions is not None:
            for item in instructions.findall("item"):
                if item.get("type") == "PRICE":
                    valdate = self._required_text(item, "valdate")
                    return self._parse_date(valdate, tag="valdate").strftime("%Y/%m/%d 23:59:59")
        for tag in ("ValuationDate", "valuationDate", "date"):
            node = root.find(f".//{tag}")
            if node is not None and node.text:
                return node.text.strip()
        raise ResultParsingError("Could not find valuation date in instruction set QML.")

    @staticmethod
    def override_in_xpath(qml: str, overrides: list[Any]) -> str:
        from lxml import etree

        try:
            root = etree.fromstring(qml.encode("utf-8"))
        except Exception as exc:
            raise SerializationError("Invalid QML XML.") from exc

        for override in overrides:
            xpath_expr = QmlHandler._get_attr_or_key(override, "path")
            if not xpath_expr:
                continue
            new_value = QmlHandler._get_attr_or_key(override, "value", "")
            for node in root.xpath(xpath_expr):
                if isinstance(node, str) and "/@" in xpath_expr:
                    elem_xpath, attr_name = xpath_expr.rsplit("/@", 1)
                    for element in root.xpath(elem_xpath):
                        element.set(attr_name, str(new_value))
                    continue
                if isinstance(node, etree._Element):
                    node.text = str(new_value)
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
        root = self._parse_xml(request_qml)
        if root.get("type") == "MULTI BYSCENARIO":
            return self.update_multi_byscenario_request_with_mult_add_shift_scenarios(
                byscenario_request=request_qml,
                stresses_request=stresses_request,
            )
        return self.update_base_request_with_mult_add_shift_scenarios(
            base_request=request_qml,
            stresses_request=stresses_request,
        )

    def get_override_qml_values(self, *, qml: str) -> dict[str, Any]:
        root = self._parse_xml(qml)
        output: dict[str, Any] = {}

        for item in root.findall("item"):
            scenario_id = item.get("type") or item.get("name")
            if not scenario_id:
                raise QmlVerificationError("Override QML scenario item must have a type or name.")

            market_data = self._parse_override_market_data(item.find("marketdata"))
            product = self._parse_override_block(item.find("product"))
            pricingparams = self._parse_override_block(item.find("pricingparams"))
            request_node = item.find("request")
            request = self._parse_override_request_enabled(request_node)
            instructionset_node = item.find("instructionset")
            if instructionset_node is None:
                instructionset_node = item.find("instructionsset")
            instructionset = self._parse_override_instructionset(instructionset_node)

            output[scenario_id] = {
                "marketdata": market_data,
                "product": product,
                "pricingparams": pricingparams,
                "request": request,
                "instructionset": instructionset,
            }

        return output

    def update_base_request_with_mult_add_shift_scenarios(
        self,
        *,
        base_request: str,
        stresses_request: Any,
    ) -> str:
        request = self._create_multi_byscenario_request_template()
        self._append_mult_add_shift_scenarios(
            request=request,
            stresses_request=stresses_request,
        )
        return self.rename_request_root_tag(base_request=base_request, request=request)

    def update_multi_byscenario_request_with_mult_add_shift_scenarios(
        self,
        *,
        byscenario_request: str,
        stresses_request: Any,
    ) -> str:
        request = self._parse_xml(byscenario_request)
        self._append_mult_add_shift_scenarios(
            request=request,
            stresses_request=stresses_request,
        )
        return self.clean_qml(ET.tostring(request, encoding="unicode"))

    @classmethod
    def rename_request_root_tag(cls, *, base_request: str, request: ET.Element) -> str:
        root = cls._parse_xml(base_request)
        root.tag = "base_request"
        request.insert(0, root)
        return cls.clean_qml(ET.tostring(request, encoding="unicode"))

    def update_qml_content(self, *, qml: str, override_values: list[Any]) -> str:
        root = self._parse_xml(qml)
        for item in override_values:
            path = self._get_attr_or_key(item, "path")
            value = self._get_attr_or_key(item, "value")
            create_if_not_found = bool(self._get_attr_or_key(item, "create_if_not_found", False))
            index = self._get_attr_or_key(item, "index")
            if not path:
                raise QmlVerificationError("Override value requires path.")

            element = root.find(str(path))
            if element is not None:
                element.text = str(value)
                continue

            if not create_if_not_found:
                raise QmlVerificationError(f"Element with XPath {path} does not exist.")
            if index is None:
                raise QmlVerificationError("index is required when create_if_not_found=True.")

            new_element = ET.Element(str(path).split("/")[-1])
            new_element.text = str(value)
            root.insert(int(index), new_element)

        return self.clean_qml(ET.tostring(root, encoding="unicode"))

    def get_pricing_duration(self, result_qml: str | None = None, *, qml: str | None = None) -> int | None:
        root = self._parse_xml(result_qml or qml or "")
        for path in (".//DurationMs", "./instruction[@name='PRICE']/base/duration"):
            node = root.find(path)
            if node is not None and node.text:
                try:
                    return int(float(node.text))
                except ValueError:
                    raise ResultParsingError(f"Invalid pricing duration value: {node.text}")
        return None

    def _parse_price_container(self, root: ET.Element | None) -> dict[str, Any]:
        if root is None:
            return {}

        parsed: dict[str, Any] = {}
        for instr in root.findall("instruction"):
            instr_name = instr.get("name")
            if instr_name == "PRICE":
                price_items = self._parse_price_instruction(instr)
                if price_items:
                    parsed.setdefault("PRICE", {}).update(price_items)
            elif instr_name == "BACKPRICE":
                backprice_items = self._parse_backprice_instruction(instr)
                if backprice_items:
                    parsed.setdefault("PRICE", {}).update(backprice_items)
            elif instr_name == "DELTAIR":
                deltair_items = self._parse_deltair_price_refs(instr)
                if deltair_items:
                    parsed["DELTAIR"] = deltair_items

        self._add_response_parser_price_compat(parsed)
        return parsed

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
        parsed: dict[str, Any] = {}
        for item in backprices.findall("item"):
            key = self._required_text(item, "key")
            total_item = item.find("./val/output/item[@name='total']")
            if total_item is None:
                continue
            parsed[key] = {
                "total": float(self._required_text(total_item, "price")),
                "currency": self._required_text(total_item, "currency"),
            }
        return parsed

    def _parse_deltair_price_refs(self, instruction: ET.Element) -> dict[str, Any]:
        parsed: dict[str, Any] = {}
        for hedge in instruction.findall("./values/hedges/hedge"):
            curve = hedge.get("data") or "UNKNOWN"
            parsed[curve] = []
            for item in hedge.findall("./output/item"):
                ref_value = item.find("refValue")
                if ref_value is None:
                    ref_value = item.find("refvalue")
                if ref_value is None or self._optional_text(ref_value, "type") != "PRICE":
                    continue
                parsed[curve].append(
                    {
                        "item": item.get("name"),
                        "price": self._optional_text(ref_value, "value"),
                        "currency": self._optional_text(ref_value, "currency"),
                    }
                )
        return parsed

    @staticmethod
    def _add_response_parser_price_compat(parsed: dict[str, Any]) -> None:
        price_items = parsed.get("PRICE")
        if not isinstance(price_items, dict):
            return

        total = price_items.get("total")
        if not isinstance(total, dict):
            return

        price_value = total.get("price", total.get("total"))
        currency = total.get("currency")
        parsed["price"] = {
            "PRICE": {
                "total": {
                    "price": price_value,
                    "currency": currency,
                }
            }
        }

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

    def _parse_calibration_container(self, root: ET.Element | None) -> dict[str, Any]:
        if root is None:
            return {}

        parsed: dict[str, Any] = {}
        for instruction in root.findall("instruction"):
            instruction_name = instruction.get("name") or "UNKNOWN"
            calibration_result = instruction.find("calibratorResults")
            if calibration_result is None:
                continue

            if calibration_result.get("type") == "MULTI":
                results = calibration_result.find("results")
                parsed[instruction_name] = {}
                if results is None:
                    continue
                for result in results.findall("result"):
                    result_name = result.get("name") or "UNKNOWN"
                    parsed[instruction_name][result_name] = {
                        "calibration_info": self._optional_text(result, "calibrationinfo"),
                        "calibration_result": self._optional_text(result, "calibrationresult"),
                    }
            else:
                parsed[instruction_name] = {
                    "calibration_info": self._optional_text(calibration_result, "calibrationinfo"),
                    "calibration_result": self._optional_text(calibration_result, "calibrationresult"),
                }

        return parsed

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
    def _curve_to_dataframe(curve: ET.Element | None) -> Any:
        import pandas as pd

        if curve is None:
            return pd.DataFrame({"x": [], "y": []})
        x_values = [float(item.text or 0) for item in curve.findall("./x/item")]
        y_values = [float(item.text or 0) for item in curve.findall("./y/item")]
        return pd.DataFrame({"x": x_values, "y": y_values})

    def _append_mult_add_shift_scenarios(self, *, request: ET.Element, stresses_request: Any) -> None:
        shift_scenarios = self._ensure_child(request, "shiftScenariosWithMultAdd")
        count_node = self._ensure_child(shift_scenarios, "count")
        count_shift = int(count_node.text or 0)

        for stress in self._get_attr_or_key(stresses_request, "stresses", []) or []:
            stress_name = self._get_attr_or_key(stress, "name")
            for affine_deformations in self._stress_affine_vectors(stress):
                item_shift = ET.Element("item", version="1")
                ET.SubElement(item_shift, "refKey").text = str(stress_name)

                affine_deformations_node = ET.SubElement(item_shift, "affineDeformations")
                count_deformation_node = ET.SubElement(affine_deformations_node, "count")

                count_deformation = 0
                for affine_deformation in affine_deformations.affineDeformations:
                    item_deformation = ET.SubElement(affine_deformations_node, "item")
                    ET.SubElement(item_deformation, "key").text = affine_deformation.deformation
                    val = ET.SubElement(item_deformation, "val")
                    ET.SubElement(val, "add").text = str(affine_deformation.factors.add)
                    ET.SubElement(val, "mult").text = str(affine_deformation.factors.mult)
                    count_deformation += 1

                count_deformation_node.text = str(count_deformation)
                shift_scenarios.append(item_shift)
                count_shift += 1

        count_node.text = str(count_shift)

    @staticmethod
    def _create_multi_byscenario_request_template() -> ET.Element:
        request = ET.Element("request", {"type": "MULTI BYSCENARIO", "version": "4"})
        ET.SubElement(request, "filterNonImpactedScenarios").text = "false"
        ET.SubElement(request, "emptyScenarioOverride")

        shift_scenarios = ET.SubElement(request, "shiftScenariosWithMultAdd")
        ET.SubElement(shift_scenarios, "count").text = "0"

        display = ET.SubElement(request, "dispScenariosCombination", {"version": "1"})
        ET.SubElement(display, "displayShiftScenarios").text = "true"
        crossed = ET.SubElement(display, "dispCrossedScenarios")
        ET.SubElement(crossed, "type").text = "PAU"
        ET.SubElement(crossed, "val")
        return request

    def _stress_affine_vectors(self, stress: Any) -> list[StressAffineDeformations]:
        vectors = self._get_attr_or_key(stress, "vectorAffineDeformations", []) or []
        if not vectors:
            return [
                StressAffineDeformations(
                    affineDeformations=[
                        StressAffineDeformation(
                            deformation="ALL",
                            factors=StressFactors(add=0.0, mult=1.0),
                        )
                    ]
                )
            ]

        normalized: list[StressAffineDeformations] = []
        for vector in vectors:
            if isinstance(vector, StressAffineDeformations):
                normalized.append(vector)
                continue

            raw_deformations = self._get_attr_or_key(vector, "affineDeformations", []) or []
            normalized.append(
                StressAffineDeformations(
                    affineDeformations=[
                        deformation
                        if isinstance(deformation, StressAffineDeformation)
                        else StressAffineDeformation.model_validate(deformation)
                        for deformation in raw_deformations
                    ]
                )
            )
        return normalized

    @staticmethod
    def _ensure_child(parent: ET.Element, tag: str) -> ET.Element:
        child = parent.find(tag)
        if child is None:
            child = ET.SubElement(parent, tag)
        return child

    def _parse_override_market_data(self, node: ET.Element | None) -> dict[str, list[dict[str, Any]]]:
        if node is None:
            return {}

        output: dict[str, list[dict[str, Any]]] = {}
        for item in node.findall("item"):
            item_type = item.get("type")
            if not item_type:
                raise QmlVerificationError("marketdata override items must have a type.")

            if item_type == "ALL":
                output.setdefault("ALL", []).append(
                    {
                        "base_file_name": self._required_text(item, "base_file_name"),
                        "new_file_name": self._required_text(item, "new_file_name"),
                    }
                )
                continue

            if item_type == "BLOCK":
                file_name = self._optional_text(item, "file_name") or self._optional_text(item, "filename")
                value = item.find("value")
                if not file_name or value is None:
                    raise QmlVerificationError("marketdata BLOCK override requires file_name/filename and value.")
                output.setdefault("BLOCK", []).append(
                    {
                        "file_name": file_name,
                        "value": self.get_root_content(ET.tostring(value, encoding="unicode")),
                    }
                )
                continue

            raise QmlVerificationError(f"Unsupported marketdata override type: {item_type}")

        return output

    def _parse_override_block(self, node: ET.Element | None) -> str | None:
        if node is None:
            return None
        value = node.find("value")
        if value is None:
            return None
        return self.get_root_content(ET.tostring(value, encoding="unicode")) or self._text_or_none(value)

    def _parse_override_instructionset(self, node: ET.Element | None) -> dict[str, Any] | None:
        if node is None:
            return None
        value = node.find("value")
        if value is None:
            return None

        if value.get("type") == "xpath":
            path = self._required_text(value, "path")
            override_with = self._required_text(value, "overridewith")
            return {"xpath": SimpleNamespace(path=path, value=override_with)}

        return {
            "block": self.get_root_content(ET.tostring(value, encoding="unicode"))
            or self._text_or_none(value)
        }

    def _parse_override_request_enabled(self, node: ET.Element | None) -> bool:
        if node is None:
            return False
        override = node.find("override")
        if override is None or override.text is None:
            return True
        return override.text.strip().lower() != "false"

    @staticmethod
    def _text_or_none(node: ET.Element) -> str | None:
        if node.text is None:
            return None
        value = node.text.strip()
        return value or None

    def _require_request_text(self, root: ET.Element, path: str, expected: str, *, label: str) -> None:
        node = root.find(path)
        if node is None:
            raise QmlVerificationError(f"{label} is required and must be {expected}.")
        current = (node.text or "").strip()
        if current != expected:
            raise QmlVerificationError(f"{label} must be {expected}, got {current or '<empty>'}.")

    def _require_instruction_text(
        self,
        item: ET.Element,
        tag: str,
        *,
        index: int,
        instruction_type: str | None,
    ) -> str:
        value = self._optional_text(item, tag)
        if value is None:
            type_label = instruction_type or "<missing type>"
            raise QmlVerificationError(
                f"{tag} is required in instruction set item {index} ({type_label})."
            )
        return value

    def _verify_instruction_date(
        self,
        *,
        item: ET.Element,
        tag: str,
        expected_date: datetime,
        index: int,
    ) -> None:
        value = self._optional_text(item, tag)
        if value is None:
            return
        actual_date = self._parse_date(value, tag=tag)
        if actual_date.date() != expected_date.date():
            raise QmlVerificationError(
                f"{tag} in instruction set item {index} must match ps_request.valuationDate "
                f"({expected_date.strftime('%Y/%m/%d')}), got {actual_date.strftime('%Y/%m/%d')}."
            )

    @staticmethod
    def _extract_ps_request_date(ps_request: Any) -> datetime:
        value = getattr(ps_request, "valuationDate", None)
        if value is None and isinstance(ps_request, dict):
            value = ps_request.get("valuationDate")
        if value is None:
            raise QmlVerificationError("ps_request.valuationDate is required for instruction set verification.")
        return QmlHandler._parse_date(str(value), tag="ps_request.valuationDate")

    @staticmethod
    def _parse_date(value: str, *, tag: str) -> datetime:
        for date_format in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), date_format)
            except ValueError:
                continue
        raise QmlVerificationError(f"Invalid date format for {tag}: {value}")

    @staticmethod
    def _get_attr_or_key(value: Any, key: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)

    @staticmethod
    def _safe_file_part(value: str) -> str:
        return value.replace("|", "-").replace("/", "_").replace("\\", "_").replace(":", "_")

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
