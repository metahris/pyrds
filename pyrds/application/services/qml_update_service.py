from __future__ import annotations

import subprocess
from os import listdir
from os.path import join
from typing import Any

from pyrds.application.services.log_context import log_info
from pyrds.domain.exceptions import XmlUpdateError


class QmlUpdateService:
    def __init__(self, *, files_path: Any, logger: Any | None = None) -> None:
        self.files_path = files_path
        self.logger = logger

    def update_qml_to_latest_version(self, in_path: str, out_path: str) -> None:
        updater_path = self.files_path.qml_updater
        subfolders = listdir(in_path)

        try:
            if subfolders:
                for folder in subfolders:
                    temp_in_path = join(in_path, folder)
                    temp_out_path = join(out_path, folder)
                    command = [updater_path, f"-in={temp_in_path}", f"-out={temp_out_path}"]
                    subprocess.run(
                        command,
                        stdout=subprocess.PIPE,
                        stdin=subprocess.PIPE,
                        text=True,
                        shell=False,
                        check=True,
                    )
            else:
                command = [updater_path, f"-in={in_path}", f"-out={out_path}"]
                subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    shell=False,
                    check=True,
                )
        except Exception as exc:
            raise XmlUpdateError(f"Failed to update QMLs from {in_path} to {out_path}") from exc

        log_info(self.logger, "QMLs updated to latest version", in_path=in_path, out_path=out_path)
