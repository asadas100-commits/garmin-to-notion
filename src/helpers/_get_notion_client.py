import os
import time
from dataclasses import dataclass

from notion_client import Client
from notion_client.errors import APIErrorCode, APIResponseError


class RateLimitedNotionClient(Client):
    def request(self, path, method, query=None, body=None, auth=None):
        for attempt in range(6):
            # Notionへの問い合わせを最大で毎秒2回程度に抑える
            time.sleep(0.5)

            try:
                return super().request(
                    path,
                    method,
                    query=query,
                    body=body,
                    auth=auth,
                )
            except APIResponseError as error:
                if error.code != APIErrorCode.RateLimited or attempt == 5:
                    raise

                retry_after = error.headers.get("Retry-After")
                try:
                    wait_seconds = max(
                        0,
                        float(retry_after) if retry_after else 2**attempt,
                    )
                except ValueError:
                    wait_seconds = 2**attempt

                print(
                    f"Notion rate limit reached; "
                    f"retrying in {wait_seconds:g} seconds..."
                )
                time.sleep(wait_seconds)


@dataclass(frozen=True)
class NotionDatabases:
    activities: str
    personal_records: str
    sleep: str
    daily_steps: str


def get_notion_client() -> tuple[Client, NotionDatabases]:
    print("Initializing Notion client...")

    notion_databases = NotionDatabases(
        activities=os.getenv("NOTION_DB_ID"),
        personal_records=os.getenv("NOTION_PR_DB_ID"),
        sleep=os.getenv("NOTION_SLEEP_DB_ID"),
        daily_steps=os.getenv("NOTION_STEPS_DB_ID"),
    )

    notion_token = os.getenv("NOTION_TOKEN")
    notion_client = RateLimitedNotionClient(auth=notion_token)

    print("Notion client initialized.")

    return notion_client, notion_databases
