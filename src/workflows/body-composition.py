from datetime import date, timedelta

from src.helpers._get_garmin_client import get_garmin_client
from src.helpers._get_notion_client import get_notion_client


def main():
    garmin, _ = get_garmin_client()
    notion, databases = get_notion_client()

    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    data = garmin.get_body_composition(
        start_date.isoformat(),
        end_date.isoformat(),
    )

    records = data.get("dateWeightList", [])
    if not records:
        print("体組成データは見つかりませんでした。")
        return

    fields = {
        "体重 (kg)": "weight",
        "BMI": "bmi",
        "体脂肪率 (%)": "bodyFat",
        "骨格筋量 (kg)": "muscleMass",
        "骨量 (kg)": "boneMass",
        "体水分率 (%)": "bodyWater",
    }

    saved_count = 0

    for record in records:
        record_date = record.get("calendarDate") or record.get("date")
        if not record_date:
            continue

        properties = {
            "測定記録": {
                "title": [{"text": {"content": f"体組成 {record_date}"}}]
            },
            "Date": {"date": {"start": record_date}},
            "測定機器": {"select": {"name": "Garmin Index S2"}},
        }

        for notion_name, garmin_name in fields.items():
            value = record.get(garmin_name)
            if value is None:
                continue

            if notion_name in ("体重 (kg)", "骨格筋量 (kg)", "骨量 (kg)"):
                value = value / 1000

            properties[notion_name] = {"number": round(value, 3)}

        result = notion.databases.query(
            database_id=databases.body_composition,
            filter={
                "property": "Date",
                "date": {"equals": record_date},
            },
        )

        if result["results"]:
            notion.pages.update(
                page_id=result["results"][0]["id"],
                properties=properties,
            )
        else:
            notion.pages.create(
                parent={"database_id": databases.body_composition},
                properties=properties,
            )

        saved_count += 1

    print(f"{saved_count}件の体組成データをNotionに登録・更新しました。")


if __name__ == "__main__":
    main()
