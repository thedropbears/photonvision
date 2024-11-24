import re
import subprocess
import os
import logging

logger = logging.getLogger(__name__)
LIB_LOCATION = os.path.dirname(os.path.abspath(__file__))


def get_git_version() -> str:
    return (
        subprocess.check_output(
            ["git", "-C", LIB_LOCATION, "describe", "--tags", "--match=v*", "--always"]
        )
        .decode("utf-8")
        .strip()
    )


def get_photon_lib_version_string() -> str:
    git_version = get_git_version()

    m = re.search(
        r"(v[0-9]{4}\.[0-9]{1}\.[0-9]{1})-?((?:beta)?(?:alpha)?)-?([0-9\.]*)",
        git_version,
    )

    # Extract the first portion of the git describe result
    # which should be PEP440 compliant
    if m:
        version_string = m.group(0)
        # Hack -- for strings like v2024.1.1, do NOT add matruity/suffix
        if len(m.group(2)) > 0:
            logger.info("using beta group matcher")
            prefix = m.group(1)
            maturity = m.group(2)
            suffix = m.group(3).replace(".", "")
            version_string = f"{prefix}.{maturity}.{suffix}"
        else:
            split = git_version.split("-")
            if len(split) == 3:
                year, commits, sha = split
                # Chop off leading v from "v2024.1.2", and use "post" for commits to master since
                version_string = f"{year[1:]}post{commits}"
                logger.info("using dev release " + version_string)
            else:
                year = git_version
                version_string = year[1:]
                logger.info("using full release " + version_string)
    else:
        logger.warning("Warning, no valid version found")
        version_string = git_version

    logger.info(f"Building version {version_string}")

    return version_string


def generate_version_file() -> None:
    # Put the version info into a python file for runtime access
    with open(
        f"{LIB_LOCATION}/src/photonlibpy/version.py", "w", encoding="utf-8"
    ) as fp:
        fp.write(f'PHOTONLIB_VERSION="{get_photon_lib_version_string()}"\n')
        fp.write(f'PHOTONVISION_VERSION="{get_git_version()}"\n')


from typing import Any
from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class VersionHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        generate_version_file()

        return super().initialize(version, build_data)
