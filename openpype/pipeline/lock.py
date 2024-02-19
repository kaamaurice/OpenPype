"""Lock module to specify a subset is locked or not in the Db.

Also stores lock date and site as last_opened data.
"""

from datetime import datetime, timedelta

from openpype.lib import get_local_site_id
from openpype.pipeline import (
    get_current_project_name,
    get_current_asset_name,
    get_current_task_name,
    get_workfile_subset,
    AvalonMongoDB,
)
from openpype.settings import get_project_settings


def lock_subset(subset: dict):
    """Lock a subset in the db.

    Args:
        subset (dict): Subset to lock.
    """
    if subset is None:
        raise Exception("Subset not found.")

    update_item_in_db_from_id(
        subset,
        {
            "$set": {
                "data.last_opened.date": datetime.now(),
                "data.last_opened.site": get_local_site_id(),
                "data.last_opened.locked": True,
            }
        },
    )


def unlock_subset(subset: dict):
    """Unlock a subset in the db.

    Args:
        subset (dict): Subset to unlock.
    """
    if subset is None:
        raise Exception("Subset not found.")

    update_item_in_db_from_id(
        subset,
        {"$set": {"data.last_opened.locked": False}},
    )


def subset_is_locked_and_lock_is_valid() -> bool:
    """Check if current subset is locked and its lock is valid.

    Returns:
        bool: True if current subset is locked and the lock is still valid.
    """
    workfile_subset = get_workfile_subset(
        get_current_project_name(),
        get_current_asset_name(),
        get_current_task_name(),
    )
    return (
        workfile_subset
        and subset_is_locked(workfile_subset)
        and not locked_on_same_site(workfile_subset)
        and subset_lock_is_valid(workfile_subset)
    )


def get_lock_settings() -> dict:
    """Get lock settings.

    Returns:
        dict: Project's lock settings.
    """
    return get_project_settings(get_current_project_name())["global"]["tools"][
        "loader"
    ].get("LockFileInDb", {})


def get_last_opened_data(subset: dict) -> dict:
    """Get last opened data settings.
    61

        Args:
            subset (dict): The subset to check.

        Returns:
            dict: Subset's last opened data.
    """
    return subset.get("data").get("last_opened")


def get_flush_delta() -> float:
    """Get lock flush delay.

    Returns:
        float: Flush delay (in hour(s)) from settings or 72.
    """
    return get_lock_settings().get("flush_delay", 72.0)


def get_lock_system_enabled() -> bool:
    """Get lock system is enabled on the project.

    Returns:
        bool: True if lock system is enabled in project's settings, else False.
    """
    return get_lock_settings().get("enabled", False)


def subset_lock_is_valid(subset: dict) -> bool:
    """Check subset lock is valid.

    A subset lock is valid if it was created sooner than the lock flush delay.

    Args:
        subset (dict): The subset to check.

    Returns:
        bool: Subset was locked before than the flush delay, or not.
    """
    return subset.get("data").get("last_opened").get("date") > (
        datetime.now() - timedelta(hours=get_flush_delta())
    )


def subset_is_locked(subset: dict) -> bool:
    """Check subset is locked.

    Args:
        subset (dict): The subset to check.

    Returns:
        bool: True if the subset is locked in the database, else False.
    """
    return get_last_opened_data(subset).get("locked")


def locked_on_same_site(subset: dict) -> bool:
    """Check if the subset's lock site matches local site.

    Args:
        subset (dict): The subset to check.

    Returns:
        bool: True if the subset site matches local site.
    """
    return (
        get_last_opened_data(subset).get("site", None) == get_local_site_id()
    )


def get_project_database() -> AvalonMongoDB:
    """Get project's mongodb database.

    Returns:
        (AvalonMongoDB): Project's mongodb database.
    """

    db = AvalonMongoDB()
    db.Session["AVALON_PROJECT"] = get_current_project_name()
    return db


def update_item_in_db_from_id(item: dict, values: dict):
    """Get mongodb client and update provided item.

    Args:
        item (dict): Item to update. Must contain "_id" key.
        values (dict): Values to update in the db for provided item.
    """
    get_project_database().update_one({"_id": item["_id"]}, values)
