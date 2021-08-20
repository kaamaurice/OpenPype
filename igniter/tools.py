# -*- coding: utf-8 -*-
"""Tools used in **Igniter** GUI.

Functions ``compose_url()`` and ``decompose_url()`` are the same as in
``openpype.lib`` and they are here to avoid importing OpenPype module before its
version is decided.

"""
import os
import sys
from typing import Dict, Union
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import platform
from typing import Optional, Iterable

from pymongo import MongoClient
from pymongo.errors import (
    ServerSelectionTimeoutError,
    InvalidURI,
    ConfigurationError,
    OperationFailure
)
from cloudpathlib import AnyPath
from cloudpathlib.cloudpath import CloudPath, register_path_class
from cloudpathlib.client import Client, register_client_class
import dropbox
from appdirs import user_data_dir


# Hack to share url to AnyPath paths.
MODULE = sys.modules[__name__]
URL = ""


@register_path_class("file")
class FilePath(CloudPath):

    cloud_prefix: str = "file://"
    client: str = "File"

    def __init__(
        self,
        cloud_path: Union[str, "CloudPath"],
        client: Optional["Client"] = None
    ):
        super().__init__(cloud_path, client=client)

        results = urlparse(str(cloud_path))
        self.path = os.path.normpath(
            os.path.join(results.netloc, results.path)
        )
        self.path_object = AnyPath(self.path)

    def drive(self) -> str:
        """
        For example "bucket" on S3 or "container" on Azure; needs to be defined
        for each class
        """
        raise ValueError("We should not need the drive part.")

    def is_dir(self) -> bool:
        """Should be implemented without requiring a dir is downloaded"""
        return self.path_object.is_dir()

    def is_file(self) -> bool:
        """
        Should be implemented without requiring that the file is downloaded
        """
        return self.path_object.is_file()

    def mkdir(self, parents: bool = False, exist_ok: bool = False):
        """
        Should be implemented using the client API without requiring a dir is
        downloaded
        """
        raise ValueError("We should not be making any directories.")

    def touch(self):
        """
        Should be implemented using the client API to create and update
        modified time
        """
        raise ValueError("We should not be touching anything.")

    def stat(self):
        return self.path_object.stat()


@register_client_class("file")
class FileClient(Client):

    def _download_file(
        self, cloud_path: FilePath, local_path: Union[str, os.PathLike]
    ) -> Path:
        raise ValueError("We should not be downloading anything.")

    def _exists(self, cloud_path: FilePath) -> bool:
        return os.path.exists(cloud_path.path)

    def _list_dir(
        self, cloud_path: FilePath, recursive: bool
    ) -> Iterable[FilePath]:
        """List all the files and folders in a directory.
        Parameters
        ----------
        cloud_path : CloudPath
            The folder to start from.
        recursive : bool
            Whether or not to list recursively.
        """
        items = []
        for item in os.listdir(cloud_path.path):
            items.append(
                FilePath(
                    FilePath.cloud_prefix + os.path.join(cloud_path, item)
                )
            )
        return items

    def _move_file(
        self, src: FilePath, dst: FilePath, remove_src: bool = True
    ) -> FilePath:
        raise ValueError("We should not be moving anything.")

    def _remove(self, path: FilePath) -> None:
        """Remove a file or folder from the server.
        Parameters
        ----------
        path : CloudPath
            The file or folder to remove.
        """
        raise ValueError("We should not be removing anything.")

    def _upload_file(
        self, local_path: Union[str, os.PathLike], cloud_path: FilePath
    ) -> FilePath:
        raise ValueError("We should not be uploading anything.")


@register_path_class("dropbox")
class DropboxPath(CloudPath):

    cloud_prefix: str = "dropbox://"
    client: str = "Dropbox"

    def __init__(
        self,
        cloud_path: Union[str, "CloudPath"],
        client: Optional["Client"] = None
    ):
        super().__init__(cloud_path, client=client)

        path = cloud_path.replace(self.cloud_prefix, "")
        # Root folder needs to be empty string rather than "/".
        if path == "":
            self.path = path
        else:
            self.path = "/" + path

    def drive(self) -> str:
        """
        For example "bucket" on S3 or "container" on Azure; needs to be defined
        for each class
        """
        raise ValueError("We should not need the drive part.")

    def is_dir(self) -> bool:
        """Should be implemented without requiring a dir is downloaded"""
        return self.client._is_file_or_dir(self) == "dir"

    def is_file(self) -> bool:
        """
        Should be implemented without requiring that the file is downloaded
        """
        return self.client._is_file_or_dir(self) == "file"

    def mkdir(self, parents: bool = False, exist_ok: bool = False):
        """
        Should be implemented using the client API without requiring a dir is
        downloaded
        """
        raise ValueError("We should not be making any directories.")

    def touch(self):
        """
        Should be implemented using the client API to create and update
        modified time
        """
        raise ValueError("We should not be touching anything.")

    def stat(self):
        metadata = self.client._get_metadata(self)

        if metadata is None:
            raise NotImplementedError(
                f"No stats available for {self}; it may be a directory or not "
                "exist."
            )

        return os.stat_result(
            (
                None,  # mode
                None,  # ino
                self.cloud_prefix,  # dev,
                None,  # nlink,
                None,  # uid,
                None,  # gid,
                metadata.size,  # size,
                None,  # atime,
                int(metadata.client_modified.strftime('%Y%m%d')),  # mtime,
                None,  # ctime,
            )
        )

    def resolve(self):
        # Casting the local cached path to Path object to return.
        return AnyPath(self.fspath)


@register_client_class("dropbox")
class DropboxClient(Client):

    def __init__(
        self,
        local_cache_dir: Optional[Union[str, os.PathLike]] = None
    ):

        system_settings = get_openpype_system_settings(MODULE.URL)
        self.client = dropbox.Dropbox(
            system_settings["modules"]["dropbox"]["token"]
        )

        self.cache_dir = os.path.join(get_user_data_dir(), "dropbox_cache")
        super().__init__(local_cache_dir=self.cache_dir)

    def _get_metadata(self, cloud_path: DropboxPath) -> Optional[int]:
        # If the path is empty, this means the root directory.
        if cloud_path.path == "":
            return None

        entry = self.client.files_get_metadata(cloud_path.path)

        if isinstance(entry, dropbox.files.FileMetadata):
            return entry

        return None

    def _is_file_or_dir(self, cloud_path: DropboxPath) -> Optional[str]:
        # Empty path means the root directory.
        if cloud_path.path == "":
            self.client.files_list_folder(path=cloud_path.path)
            return "dir"

        entry = self.client.files_get_metadata(cloud_path.path)

        if isinstance(entry, dropbox.files.FolderMetadata):
            return "dir"
        elif isinstance(entry, dropbox.files.FileMetadata):
            return "file"
        else:
            return None

    def _download_file(
        self, cloud_path: DropboxPath, local_path: Union[str, os.PathLike]
    ) -> Path:
        self.client.files_download_to_file(local_path, cloud_path.path)

        # Clean local cache.
        for item in os.listdir(self.cache_dir):
            if item == os.path.basename(local_path):
                continue

            os.remove(os.path.join(self.cache_dir, item))

        return local_path

    def _exists(self, cloud_path: DropboxPath) -> bool:
        # If the path is empty, this means the root directory.
        if cloud_path.path == "":
            try:
                self.client.files_list_folder(path=cloud_path.path)
                return True
            except dropbox.exceptions.AuthError:
                return False

        try:
            self.client.files_get_metadata(cloud_path.path)
            return True
        except dropbox.exceptions.ApiError:
            return False

    def _list_dir(
        self, cloud_path: DropboxPath, recursive: bool
    ) -> Iterable[FilePath]:
        """List all the files and folders in a directory.
        Parameters
        ----------
        cloud_path : CloudPath
            The folder to start from.
        recursive : bool
            Whether or not to list recursively.
        """
        items = []
        cursor = self.client.files_list_folder(path=cloud_path.path)
        prefix = DropboxPath.cloud_prefix
        for entry in cursor.entries:
            items.append(
                DropboxPath(prefix + os.path.join(cloud_path.path, entry.name))
            )
        return items

    def _move_file(
        self, src: DropboxPath, dst: DropboxPath, remove_src: bool = True
    ) -> FilePath:
        raise ValueError("We should not be moving anything.")

    def _remove(self, path: DropboxPath) -> None:
        """Remove a file or folder from the server.
        Parameters
        ----------
        path : CloudPath
            The file or folder to remove.
        """
        raise ValueError("We should not be removing anything.")

    def _upload_file(
        self, local_path: Union[str, os.PathLike], cloud_path: DropboxPath
    ) -> FilePath:
        raise ValueError("We should not be uploading anything.")


def decompose_url(url: str) -> Dict:
    """Decompose mongodb url to its separate components.

    Args:
        url (str): Mongodb url.

    Returns:
        dict: Dictionary of components.

    """
    components = {
        "scheme": None,
        "host": None,
        "port": None,
        "username": None,
        "password": None,
        "auth_db": None
    }

    result = urlparse(url)
    if result.scheme is None:
        _url = "mongodb://{}".format(url)
        result = urlparse(_url)

    components["scheme"] = result.scheme
    components["host"] = result.hostname
    try:
        components["port"] = result.port
    except ValueError:
        raise RuntimeError("invalid port specified")
    components["username"] = result.username
    components["password"] = result.password

    try:
        components["auth_db"] = parse_qs(result.query)['authSource'][0]
    except KeyError:
        # no auth db provided, mongo will use the one we are connecting to
        pass

    return components


def compose_url(scheme: str = None,
                host: str = None,
                username: str = None,
                password: str = None,
                port: int = None,
                auth_db: str = None) -> str:
    """Compose mongodb url from its individual components.

    Args:
        scheme (str, optional):
        host (str, optional):
        username (str, optional):
        password (str, optional):
        port (str, optional):
        auth_db (str, optional):

    Returns:
        str: mongodb url

    """

    url = "{scheme}://"

    if username and password:
        url += "{username}:{password}@"

    url += "{host}"
    if port:
        url += ":{port}"

    if auth_db:
        url += "?authSource={auth_db}"

    return url.format(**{
        "scheme": scheme,
        "host": host,
        "username": username,
        "password": password,
        "port": port,
        "auth_db": auth_db
    })


def validate_mongo_connection(cnx: str) -> (bool, str):
    """Check if provided mongodb URL is valid.

    Args:
        cnx (str): URL to validate.

    Returns:
        (bool, str): True if ok, False if not and reason in str.

    """
    parsed = urlparse(cnx)
    if parsed.scheme not in ["mongodb", "mongodb+srv"]:
        return False, "Not mongodb schema"

    try:
        client = MongoClient(
            cnx,
            serverSelectionTimeoutMS=2000
        )
        client.server_info()
        client.close()
    except ServerSelectionTimeoutError as e:
        return False, f"Cannot connect to server {cnx} - {e}"
    except ValueError:
        return False, f"Invalid port specified {parsed.port}"
    except (ConfigurationError, OperationFailure, InvalidURI) as exc:
        return False, str(exc)
    else:
        return True, "Connection is successful"


def validate_mongo_string(mongo: str) -> (bool, str):
    """Validate string if it is mongo url acceptable by **Igniter**..

    Args:
        mongo (str): String to validate.

    Returns:
        (bool, str):
            True if valid, False if not and in second part of tuple
            the reason why it failed.

    """
    if not mongo:
        return True, "empty string"
    parsed = urlparse(mongo)
    if parsed.scheme in ["mongodb", "mongodb+srv"]:
        return validate_mongo_connection(mongo)
    return False, "not valid mongodb schema"


def validate_path_string(path: str) -> (bool, str):
    """Validate string if it is path to OpenPype repository.

    Args:
        path (str): Path to validate.


    Returns:
        (bool, str):
            True if valid, False if not and in second part of tuple
            the reason why it failed.

    """
    if not path:
        return False, "empty string"

    if not Path(path).exists():
        return False, "path doesn't exists"

    if not Path(path).is_dir():
        return False, "path is not directory"

    return True, "valid path"


def get_openpype_system_settings(url: str) -> dict:
    """Load system settings from Mongo database.

    We are loading data from database `openpype` and collection `settings`.
    There we expect document type `system_settings`.

    Args:
        url (str): MongoDB url.

    Returns:
        dict: With settings data. Empty dictionary is returned if not found.
    """
    try:
        components = decompose_url(url)
    except RuntimeError:
        return {}
    mongo_kwargs = {
        "host": compose_url(**components),
        "serverSelectionTimeoutMS": 2000
    }
    port = components.get("port")
    if port is not None:
        mongo_kwargs["port"] = int(port)

    try:
        # Create mongo connection
        client = MongoClient(**mongo_kwargs)
        # Access settings collection
        col = client["openpype"]["settings"]
        # Query global settings
        settings = col.find_one({"type": "system_settings"}) or {}
        # Close Mongo connection
        client.close()

    except Exception:
        # TODO log traceback or message
        return {}

    return settings.get("data") or {}


def get_openpype_global_settings(url: str) -> dict:
    """Load global settings from Mongo database.

    We are loading data from database `openpype` and collection `settings`.
    There we expect document type `global_settings`.

    Args:
        url (str): MongoDB url.

    Returns:
        dict: With settings data. Empty dictionary is returned if not found.
    """
    try:
        components = decompose_url(url)
    except RuntimeError:
        return {}
    mongo_kwargs = {
        "host": compose_url(**components),
        "serverSelectionTimeoutMS": 2000
    }
    port = components.get("port")
    if port is not None:
        mongo_kwargs["port"] = int(port)

    try:
        # Create mongo connection
        client = MongoClient(**mongo_kwargs)
        # Access settings collection
        col = client["openpype"]["settings"]
        # Query global settings
        global_settings = col.find_one({"type": "global_settings"}) or {}
        # Close Mongo connection
        client.close()

    except Exception:
        # TODO log traceback or message
        return {}

    return global_settings.get("data") or {}


def get_openpype_path_from_db(url: str) -> Union[str, None]:
    """Get OpenPype path from global settings.

    Args:
        url (str): mongodb url.

    Returns:
        path to OpenPype or None if not found
    """
    global_settings = get_openpype_global_settings(url)
    paths = (
        global_settings
        .get("openpype_path", {})
        .get(platform.system().lower())
    ) or []
    # For cases when `openpype_path` is a single path
    if paths and isinstance(paths, str):
        paths = [paths]

    # Hack to share url to AnyPath paths.
    MODULE.URL = url

    # Loop over paths and return only existing
    for path in paths:
        if AnyPath(path).exists():
            return path
    return None


def get_user_data_dir():
    """Convenience method for centralize the user data directory path"""

    vendor = "pypeclub"
    app = "openpype"
    return AnyPath(user_data_dir(app, vendor))
