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

        fields = {
            "体重 (kg)": "weight",
            "BMI": "bmi",
            "体脂肪率 (%)": "bodyFat",
            "骨格筋量 (kg)": "muscleMass",
            "骨量 (kg)": "boneMass",
            "体水分率 (%)": "bodyWater",
        }

        for notion_name, garmin_name in fields.items():
            value = record.get(garmin_name)
            if value is not None:
                properties[notion_name] = {"number": value}

        notion.pages.create(
            parent={"database_id": databases.body_composition},
            properties=properties,
        )

    print(f"{len(records)}件の体組成データをNotionに登録しました。")


if __name__ == "__main__":
    main()
