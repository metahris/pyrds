from __future__ import annotations

from os.path import isabs, join
from typing import Any

from lxml import etree

from pyrds.domain.exceptions import OverrideApplicationError, OverrideValidationError
from pyrds.domain.override_models import (
    MatchPolicy,
    OverrideOperation,
    OverrideScenario,
    OverrideTargetType,
    QmlOverride,
    QmlSource,
)


class QmlOverrideService:
    def __init__(self, *, files_path: Any, logger: Any | None = None) -> None:
        self.files_path = files_path
        self.logger = logger

    def apply_scenario_to_mapping(
        self,
        *,
        qml_by_target_id: dict[str, str],
        scenario: OverrideScenario,
        target_type: OverrideTargetType,
    ) -> dict[str, str]:
        output = dict(qml_by_target_id)
        applicable = [item for item in scenario.overrides if item.target_type == target_type]

        for override in applicable:
            if override.operation in {OverrideOperation.ADD_FILE, OverrideOperation.ADD_FILES}:
                continue

            if override.target_sources:
                for target_source in override.target_sources:
                    target_id = target_source.target_id
                    if target_id not in output:
                        raise OverrideApplicationError(
                            f"Target '{target_id}' does not exist for override '{override.name}'."
                        )
                    target_override = override.model_copy(
                        update={
                            "target_id": target_id,
                            "target_ids": None,
                            "target_sources": None,
                            "apply_to_all": False,
                            "source": target_source.source,
                        }
                    )
                    output[target_id] = self.apply_override(qml=output[target_id], override=target_override)
                continue

            target_ids = self._resolve_target_ids(override=override, available_target_ids=list(output.keys()))
            for target_id in target_ids:
                if target_id not in output:
                    raise OverrideApplicationError(
                        f"Target '{target_id}' does not exist for override '{override.name}'."
                    )
                output[target_id] = self.apply_override(qml=output[target_id], override=override)

        return output

    def apply_scenario_to_single_qml(
        self,
        *,
        qml: str,
        scenario: OverrideScenario,
        target_type: OverrideTargetType,
    ) -> str:
        output = qml
        applicable = [item for item in scenario.overrides if item.target_type == target_type]
        for override in applicable:
            output = self.apply_override(qml=output, override=override)
        return output

    def apply_override(self, *, qml: str, override: QmlOverride) -> str:
        if override.operation == OverrideOperation.REPLACE_FILE:
            replacement = self.resolve_source_text(override.source, override.target_type)
            return self.replace_file(qml=qml, replacement_qml=replacement)

        if override.operation == OverrideOperation.REPLACE_BLOCK:
            block_xml = self.resolve_source_text(override.source, override.target_type)
            return self.replace_block(qml=qml, block_xml=block_xml)

        if override.operation == OverrideOperation.REPLACE_BLOCKS:
            blocks_xml = [
                self.resolve_source_text(source, override.target_type)
                for source in (override.sources or [])
            ]
            return self.replace_blocks(
                qml=qml,
                blocks_xml=blocks_xml,
                allow_duplicate_tags=override.allow_duplicate_tags,
            )

        if override.operation == OverrideOperation.REPLACE_XPATH:
            replacement = self.resolve_source_text(override.source, override.target_type)
            return self.replace_xpath(
                qml=qml,
                xpath=self._require_xpath(override),
                replacement_xml=replacement,
                match_policy=override.match_policy,
            )

        if override.operation == OverrideOperation.SET_XPATH_TEXT:
            return self.set_xpath_text(
                qml=qml,
                xpath=self._require_xpath(override),
                value=self._require_value(override),
                match_policy=override.match_policy,
            )

        if override.operation == OverrideOperation.SET_XPATH_ATTRIBUTE:
            return self.set_xpath_attribute(
                qml=qml,
                xpath=self._require_xpath(override),
                attribute=self._require_attribute(override),
                value=self._require_value(override),
                match_policy=override.match_policy,
            )

        raise OverrideApplicationError(f"Unsupported override operation: {override.operation}")

    def replace_file(self, *, qml: str, replacement_qml: str) -> str:
        self._parse_xml(qml)
        replacement_root = self._parse_xml(replacement_qml)
        return self._to_xml_string(replacement_root)

    def replace_block(self, *, qml: str, block_xml: str) -> str:
        root = self._parse_xml(qml)
        new_block = self._parse_xml(block_xml)
        replaced = self._replace_first_matching_tag(root=root, tag=self._local_name(new_block), replacement=new_block)
        if not replaced:
            raise OverrideApplicationError(f"Could not find block tag '{self._local_name(new_block)}' to replace.")
        return self._to_xml_string(root)

    def replace_blocks(
        self,
        *,
        qml: str,
        blocks_xml: list[str],
        allow_duplicate_tags: bool = False,
    ) -> str:
        if not blocks_xml:
            raise OverrideValidationError("replace_blocks requires at least one block.")

        if not allow_duplicate_tags:
            tags = [self._local_name(self._parse_xml(block_xml)) for block_xml in blocks_xml]
            if len(tags) != len(set(tags)):
                raise OverrideValidationError("replace_blocks contains duplicate block tags.")

        output = qml
        for block_xml in blocks_xml:
            output = self.replace_block(qml=output, block_xml=block_xml)
        return output

    def replace_xpath(
        self,
        *,
        qml: str,
        xpath: str,
        replacement_xml: str,
        match_policy: MatchPolicy = MatchPolicy.EXACTLY_ONE,
    ) -> str:
        root = self._parse_xml(qml)
        replacement = self._parse_xml(replacement_xml)
        matches = self._findall(root, xpath)
        self._validate_xpath_matches(xpath=xpath, matches=matches, match_policy=match_policy)

        for match in matches:
            if not isinstance(match, etree._Element):
                raise OverrideApplicationError(
                    f"XPath '{xpath}' must match XML elements for replace_xpath."
                )
            parent = match.getparent()
            if parent is None:
                raise OverrideApplicationError("replace_xpath cannot replace the XML document root.")
            parent.replace(match, self._clone_element(replacement))
        return self._to_xml_string(root)

    def set_xpath_text(
        self,
        *,
        qml: str,
        xpath: str,
        value: str,
        match_policy: MatchPolicy = MatchPolicy.EXACTLY_ONE,
    ) -> str:
        root = self._parse_xml(qml)
        matches = self._findall(root, xpath)
        self._validate_xpath_matches(xpath=xpath, matches=matches, match_policy=match_policy)

        for node in matches:
            if not isinstance(node, etree._Element):
                raise OverrideApplicationError(
                    "set_xpath_text only supports XML element matches. "
                    "Use set_xpath_attribute to change attributes."
                )
            node.text = value
        return self._to_xml_string(root)

    def set_xpath_attribute(
        self,
        *,
        qml: str,
        xpath: str,
        attribute: str,
        value: str,
        match_policy: MatchPolicy = MatchPolicy.EXACTLY_ONE,
    ) -> str:
        root = self._parse_xml(qml)
        matches = self._findall(root, xpath)
        self._validate_xpath_matches(xpath=xpath, matches=matches, match_policy=match_policy)

        for node in matches:
            if not isinstance(node, etree._Element):
                raise OverrideApplicationError(
                    f"XPath '{xpath}' must match XML elements for set_xpath_attribute."
                )
            node.set(attribute, value)
        return self._to_xml_string(root)

    def resolve_source_text(self, source: QmlSource | None, target_type: OverrideTargetType) -> str:
        if source is None:
            raise OverrideValidationError("Override source is required.")

        if source.inline_xml is not None:
            return source.inline_xml

        if source.file_path is not None:
            file_path = source.file_path if isabs(source.file_path) else join(self.files_path.working_dir, source.file_path)
            return self._read_text(file_path)

        if source.file_name is not None:
            file_path = join(self._default_dir(target_type), source.file_name)
            return self._read_text(file_path)

        raise OverrideValidationError("Invalid override source.")

    def _default_dir(self, target_type: OverrideTargetType) -> str:
        if target_type == OverrideTargetType.MARKETDATA:
            return self.files_path.data
        if target_type in {OverrideTargetType.PRODUCT, OverrideTargetType.PRICINGPARAMS}:
            return self.files_path.trade
        if target_type in {OverrideTargetType.REQUEST, OverrideTargetType.INSTRUCTIONSET}:
            return self.files_path.data
        return self.files_path.inputs

    @staticmethod
    def _read_text(file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8") as file_handle:
            return file_handle.read()

    @staticmethod
    def _parse_xml(xml_text: str) -> etree._Element:
        try:
            parser = etree.XMLParser(remove_blank_text=False, recover=False)
            return etree.fromstring(xml_text.encode("utf-8"), parser=parser)
        except Exception as exc:
            raise OverrideApplicationError("Invalid XML content.") from exc

    @staticmethod
    def _to_xml_string(root: etree._Element) -> str:
        return etree.tostring(root, encoding="unicode")

    @staticmethod
    def _clone_element(element: etree._Element) -> etree._Element:
        return etree.fromstring(etree.tostring(element, encoding="utf-8"))

    def _replace_first_matching_tag(self, *, root: etree._Element, tag: str, replacement: etree._Element) -> bool:
        for parent in root.iter():
            for child in list(parent):
                if self._local_name(child) == tag:
                    parent.replace(child, self._clone_element(replacement))
                    return True
        return False

    @staticmethod
    def _findall(root: etree._Element, xpath: str) -> list[Any]:
        try:
            return list(root.xpath(xpath))
        except Exception as exc:
            raise OverrideApplicationError(f"Invalid xpath '{xpath}'.") from exc

    @staticmethod
    def _validate_xpath_matches(
        *,
        xpath: str,
        matches: list[Any],
        match_policy: MatchPolicy,
    ) -> None:
        if match_policy == MatchPolicy.EXACTLY_ONE and len(matches) != 1:
            raise OverrideApplicationError(
                f"XPath '{xpath}' must match exactly one node, got {len(matches)}."
            )
        if match_policy in {MatchPolicy.ONE_OR_MORE, MatchPolicy.ALL} and not matches:
            raise OverrideApplicationError(f"XPath '{xpath}' did not match any node.")

    @staticmethod
    def _require_target_id(override: QmlOverride) -> str:
        if not override.target_id:
            raise OverrideValidationError(f"Override '{override.name}' requires target_id.")
        return override.target_id

    @classmethod
    def _resolve_target_ids(cls, *, override: QmlOverride, available_target_ids: list[str]) -> list[str]:
        if override.apply_to_all:
            return available_target_ids
        if override.target_ids:
            return override.target_ids
        return [cls._require_target_id(override)]

    @staticmethod
    def _require_xpath(override: QmlOverride) -> str:
        if not override.xpath:
            raise OverrideValidationError(f"Override '{override.name}' requires xpath.")
        return override.xpath

    @staticmethod
    def _require_value(override: QmlOverride) -> str:
        if override.value is None:
            raise OverrideValidationError(f"Override '{override.name}' requires value.")
        return override.value

    @staticmethod
    def _require_attribute(override: QmlOverride) -> str:
        if not override.attribute:
            raise OverrideValidationError(f"Override '{override.name}' requires attribute.")
        return override.attribute

    @staticmethod
    def _local_name(element: etree._Element) -> str:
        return etree.QName(element).localname
