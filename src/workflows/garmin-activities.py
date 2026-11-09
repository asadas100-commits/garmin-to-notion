from datetime import datetime, UTC, timedelta

import pytz
from dotenv import load_dotenv
from garminconnect import Garmin as GarminClient
from notion_client import Client as NotionClient

from src.helpers import get_garmin_client, get_notion_client

# Your local time zone, replace with the appropriate one if needed
local_tz = pytz.timezone('America/Toronto')

ACTIVITY_ICONS = {
    "Barre": "https://img.icons8.com/?size=100&id=66924&format=png&color=000000",
    "Breathwork": "https://img.icons8.com/?size=100&id=9798&format=png&color=000000",
    "Cardio": "https://img.icons8.com/?size=100&id=71221&format=png&color=000000",
    "Cycling": "https://img.icons8.com/?size=100&id=47443&format=png&color=000000",
    "Hiking": "https://img.icons8.com/?size=100&id=9844&format=png&color=000000",
    "Indoor Cardio": "https://img.icons8.com/?size=100&id=62779&format=png&color=000000",
    "Indoor Cycling": "https://img.icons8.com/?size=100&id=47443&format=png&color=000000",
    "Indoor Rowing": "https://img.icons8.com/?size=100&id=71098&format=png&color=000000",
    "Pilates": "https://img.icons8.com/?size=100&id=9774&format=png&color=000000",
    "Meditation": "https://img.icons8.com/?size=100&id=9798&format=png&color=000000",
    "Rowing": "https://img.icons8.com/?size=100&id=71491&format=png&color=000000",
    "Running": "https://img.icons8.com/?size=100&id=k1l1XFkME39t&format=png&color=000000",
    "Strength Training": "https://img.icons8.com/?size=100&id=107640&format=png&color=000000",
    "Stretching": "https://img.icons8.com/?size=100&id=djfOcRn1m_kh&format=png&color=000000",
    "Swimming": "https://img.icons8.com/?size=100&id=9777&format=png&color=000000",
    "Treadmill Running": "https://img.icons8.com/?size=100&id=9794&format=png&color=000000",
    "Walking": "https://img.icons8.com/?size=100&id=9807&format=png&color=000000",
    "Yoga": "https://img.icons8.com/?size=100&id=9783&format=png&color=000000",
    # Add more mappings as needed
}


def get_all_activities(garmin_client: GarminClient, limit: int = 1000) -> list[dict]:
    return garmin_client.get_activities(0, limit)


def format_activity_type(activity_type: str, activity_name: str = "") -> tuple[str, str]:
    # First format the activity type as before
    formatted_type = activity_type.replace('_', ' ').title() if activity_type else "Unknown"

    # Initialize subtype as the same as the main type
    activity_subtype = formatted_type
    activity_type = formatted_type

    # Map of specific subtypes to their main types
    activity_mapping = {
        "Barre": "Strength",
        "Indoor Cardio": "Cardio",
        "Indoor Cycling": "Cycling",
        "Indoor Rowing": "Rowing",
        "Speed Walking": "Walking",
        "Strength Training": "Strength",
        "Treadmill Running": "Running"
    }

    # Special replacement for Rowing V2
    if formatted_type == "Rowing V2":
        activity_type = "Rowing"

    # Special case for Yoga and Pilates
    elif formatted_type in ["Yoga", "Pilates"]:
        activity_type = "Yoga/Pilates"
        activity_subtype = formatted_type

    # If the formatted type is in our mapping, update both main type and subtype
    if formatted_type in activity_mapping:
        activity_type = activity_mapping[formatted_type]
        activity_subtype = formatted_type

    # Special cases for activity names
    if activity_name and "meditation" in activity_name.lower():
        return "Meditation", "Meditation"
    if activity_name and "barre" in activity_name.lower():
        return "Strength", "Barre"
    if activity_name and "stretch" in activity_name.lower():
        return "Stretching", "Stretching"

    return activity_type, activity_subtype


def format_entertainment(activity_name: str) -> str:
    return activity_name.replace('ENTERTAINMENT', 'Netflix')


def format_training_message(message: str) -> str:
    messages = {
        'NO_': 'No Benefit',
        'MINOR_': 'Some Benefit',
        'RECOVERY_': 'Recovery',
        'MAINTAINING_': 'Maintaining',
        'IMPROVING_': 'Impacting',
        'IMPACTING_': 'Impacting',
        'HIGHLY_': 'Highly Impacting',
        'OVERREACHING_': 'Overreaching'
    }
    for key, value in messages.items():
        if message.startswith(key):
            return value
    return message


def format_training_effect(training_effect_label: str) -> str:
    return training_effect_label.replace('_', ' ').title()


def format_pace(average_speed: float) -> str:
    if average_speed > 0:
        pace_min_km = 1000 / (average_speed * 60)  # Convert to min/km
        minutes = int(pace_min_km)
        seconds = int((pace_min_km - minutes) * 60)
        return f"{minutes}:{seconds:02d} min/km"
    else:
        return ""


def activity_exists(
    notion_client: NotionClient,
    database_id: str,
    activity_date: datetime,
    activity_type: str,
    activity_name: str,
) -> dict | None:
    # Check if an activity already exists in the Notion database and return it if found.

    # Determine the correct activity type for the lookup
    lookup_type = "Stretching" if "stretch" in activity_name.lower() else activity_type

    # Create a time window to search for the activity. Notion has been observed to truncate datetimes to the minutes in
    # some instances, causing the lookup using exact datetime to fail.
    # TODO: We should store the activity ID in the Notion page to avoid this complexity.
    lookup_min_date = activity_date - timedelta(minutes=5)
    lookup_max_date = activity_date + timedelta(minutes=5)

    query = notion_client.databases.query(
        database_id=database_id,
        filter={
            "and": [
                {"property": "Date", "date": {"on_or_after": lookup_min_date.isoformat()}},
                {"property": "Date", "date": {"on_or_before": lookup_max_date.isoformat()}},
                # Further refine the search by activity type and name
                {"property": "Activity Type", "select": {"equals": lookup_type}},
                {"property": "Activity Name", "title": {"equals": activity_name}}
            ]
        }
    )
    results = query['results']
    return results[0] if results else None


def activity_needs_update(existing_activity: dict, new_activity: dict) -> bool:
    properties = existing_activity.get("properties", {})
    id_property = properties.get("Garmin Activity ID", {})
    rich_text = id_property.get("rich_text", [])

    existing_id = "".join(
        item.get("plain_text", "") for item in rich_text
    )
    new_id = str(new_activity.get("activityId") or "")

    # Garmin Activity IDが未登録の既存ページだけ、一度更新します。
    return bool(new_id) and existing_id != new_id


def create_activity(notion_client: NotionClient, database_id: str, activity: dict) -> str:
    activity_date = (
        datetime.strptime(activity.get("startTimeGMT"), "%Y-%m-%d %H:%M:%S")
        .replace(tzinfo=UTC)
        .isoformat()
    )
    activity_name = format_entertainment(
        activity.get("activityName", "Unnamed Activity")
    )
    activity_type, activity_subtype = format_activity_type(
        activity.get("activityType", {}).get("typeKey", "Unknown"),
        activity_name,
    )
    icon_url = ACTIVITY_ICONS.get(
        activity_subtype if activity_subtype != activity_type else activity_type
    )

    def number_value(key, digits=0, divisor=1):
        value = activity.get(key)
        return None if value is None else round(float(value) / divisor, digits)

    def text_value(value):
        value = str(value or "")
        return {"rich_text": [{"text": {"content": value}}]} if value else {"rich_text": []}

    duration_text = str(timedelta(seconds=int(activity.get("duration") or 0)))

    properties = {
        "Date": {"date": {"start": activity_date}},
        "Activity Type": {"select": {"name": activity_type}},
        "Activity Name": {"title": [{"text": {"content": activity_name}}]},
        "タイム": text_value(duration_text),
        "距離": {"number": number_value("distance", 2, 1000)},
        "標高": {"number": number_value("maxElevation", 1)},
        "獲得標高": {"number": number_value("elevationGain", 1)},
        "ケイデンス（平均）": {
            "number": number_value("averageRunningCadenceInStepsPerMinute", 1)
        },
        "パワー（平均）": {"number": number_value("avgPower", 1)},
        "心拍数（最大）": {"number": number_value("maxHR")},
        "ペース（平均）": text_value(format_pace(activity.get("averageSpeed") or 0)),
        "平均心拍": {"number": number_value("averageHR")},
        "消費カロリー": {"number": number_value("calories")},
        "GAP": text_value(
            format_pace(activity.get("averageGradeAdjustedSpeed") or 0)
        ),
        "Garmin Activity ID": text_value(activity.get("activityId")),
        "メモ": text_value(activity.get("description")),
    }

    page = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }

    if icon_url:
        page["icon"] = {"type": "external", "external": {"url": icon_url}}

    return notion_client.pages.create(**page)["id"]
def update_activity(notion_client: NotionClient, existing_activity: dict, new_activity: dict) -> None:
    activity_name = format_entertainment(
        new_activity.get("activityName", "Unnamed Activity")
    )
    activity_type, activity_subtype = format_activity_type(
        new_activity.get("activityType", {}).get("typeKey", "Unknown"),
        activity_name,
    )
    icon_url = ACTIVITY_ICONS.get(
        activity_subtype if activity_subtype != activity_type else activity_type
    )

    def number_value(key, digits=0, divisor=1):
        value = new_activity.get(key)
        return None if value is None else round(float(value) / divisor, digits)

    def text_value(value):
        value = str(value or "")
        return {"rich_text": [{"text": {"content": value}}]} if value else {"rich_text": []}

    duration_text = str(
        timedelta(seconds=int(new_activity.get("duration") or 0))
    )

    properties = {
        "Activity Type": {"select": {"name": activity_type}},
        "タイム": text_value(duration_text),
        "距離": {"number": number_value("distance", 2, 1000)},
        "標高": {"number": number_value("maxElevation", 1)},
        "獲得標高": {"number": number_value("elevationGain", 1)},
        "ケイデンス（平均）": {
            "number": number_value(
                "averageRunningCadenceInStepsPerMinute", 1
            )
        },
        "パワー（平均）": {"number": number_value("avgPower", 1)},
        "心拍数（最大）": {"number": number_value("maxHR")},
        "ペース（平均）": text_value(
            format_pace(new_activity.get("averageSpeed") or 0)
        ),
        "平均心拍": {"number": number_value("averageHR")},
        "消費カロリー": {"number": number_value("calories")},
        "GAP": text_value(
            format_pace(new_activity.get("averageGradeAdjustedSpeed") or 0)
        ),
        "Garmin Activity ID": text_value(new_activity.get("activityId")),
        "メモ": text_value(new_activity.get("description")),
    }

    update = {
        "page_id": existing_activity["id"],
        "properties": properties,
    }

    if icon_url:
        update["icon"] = {"type": "external", "external": {"url": icon_url}}

    notion_client.pages.update(**update)
def sync_activity_laps(
    garmin_client: GarminClient,
    notion_client: NotionClient,
    activity_database_id: str,
    activity_page_id: str,
    activity: dict,
) -> None:
    activity_id = activity.get("activityId")
    if not activity_id:
        return

    activity_db = notion_client.databases.retrieve(
        database_id=activity_database_id
    )
    print("Notionの列名と種類:", {name: prop.get("type") for name, prop in activity_db["properties"].items()})
    lap_relation = next(
        (
            prop for name, prop in activity_db["properties"].items()
            if prop.get("type") == "relation" and "1km" in name
        ),
        None,
    )
    if not lap_relation:
        raise ValueError("アクティビティDBのラップDBリレーションが見つかりません")

    lap_database_id = lap_relation["relation"]["database_id"]
    lap_response = garmin_client.get_activity_laps(activity_id)
    laps = lap_response.get("lapDTOs", [])

    for index, lap in enumerate(laps, start=1):
        lap_number = lap.get("lapIndex") or index
        garmin_activity_id = str(activity_id)

        existing = notion_client.databases.query(
            database_id=lap_database_id,
            filter={
                "and": [
                    {
                        "property": "Garmin Activity ID",
                        "rich_text": {"equals": garmin_activity_id},
                    },
                    {
                        "property": "ラップ番号",
                        "number": {"equals": lap_number},
                    },
                ]
            },
        )["results"]

        def lap_number_value(*keys):
            for key in keys:
                value = lap.get(key)
                if value is not None:
                    return round(float(value), 1)
            return None

        duration = str(timedelta(seconds=int(lap.get("duration") or 0)))
        speed = lap.get("averageSpeed") or 0
        cadence = lap_number_value(
            "averageRunCadence",
            "averageBikeCadence",
            "averageRunningCadenceInStepsPerMinute",
        )

        properties = {
            "ラップ名": {
                "title": [{"text": {"content": f"{lap_number} km"}}]
            },
            "Garmin Activity ID": {
                "rich_text": [{"text": {"content": garmin_activity_id}}]
            },
            "Activity Name": {"relation": [{"id": activity_page_id}]},
            "ラップ番号": {"number": lap_number},
            "ラップ距離": {
                "number": round(float(lap.get("distance") or 0) / 1000, 2)
            },
            "ラップタイム": {
                "rich_text": [{"text": {"content": duration}}]
            },
            "ラップペース": {
                "rich_text": [{
                    "text": {"content": format_pace(speed)}
                }]
            },
            "ラップ平均ケイデンス": {"number": cadence},
            "ラップ平均パワー": {
                "number": lap_number_value("averagePower")
            },
            "ラップ平均心拍": {
                "number": lap_number_value("averageHR")
            },
            "ラップ標高差": {
                "number": lap_number_value("elevationGain")
            },
            "日付": {
                "date": {
                    "start": (
                        datetime.strptime(
                            lap.get("startTimeGMT") or activity["startTimeGMT"],
                            "%Y-%m-%d %H:%M:%S",
                        )
                        .replace(tzinfo=UTC)
                        .isoformat()
                    )
                }
            },
        }

        if existing:
            notion_client.pages.update(
                page_id=existing[0]["id"],
                properties=properties,
            )
        else:
            notion_client.pages.create(
                parent={"database_id": lap_database_id},
                properties=properties,
            )
def main():
    load_dotenv()

    garmin_client, garmin_configuration = get_garmin_client()
    notion_client, notion_dbs = get_notion_client()
    database_id = notion_dbs.activities

    activities = get_all_activities(
        garmin_client,
        garmin_configuration.activity_fetch_limit,
    )

    for activity in activities:
        activity_date_raw = activity.get("startTimeGMT")
        activity_date = (
            datetime.strptime(activity_date_raw, "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=UTC)
        )

        activity_name = format_entertainment(
            activity.get("activityName", "Unnamed Activity")
        )
        activity_type, _ = format_activity_type(
            activity.get("activityType", {}).get("typeKey", "Unknown"),
            activity_name,
        )

        if activity_type not in {"Running", "Trail Running", "Cycling", "Hiking"}:
            continue

        existing_activity = activity_exists(
            notion_client,
            database_id,
            activity_date,
            activity_type,
            activity_name,
        )

        if existing_activity:
            if activity_needs_update(existing_activity, activity):
                update_activity(notion_client, existing_activity, activity)
            activity_page_id = existing_activity["id"]
        else:
            activity_page_id = create_activity(
                notion_client,
                database_id,
                activity,
            )

        sync_activity_laps(
            garmin_client,
            notion_client,
            database_id,
            activity_page_id,
            activity,
        )


if __name__ == "__main__":
    main()
