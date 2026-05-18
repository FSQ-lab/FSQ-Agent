# Account And Rewards Panel

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_account_rewards_panel",
  "name": "Account And Rewards Panel",
  "identifiers": [
    {"name": "Signed-in account entry visible", "description": "The NTP can expose a signed-in account image before opening account options."},
    {"name": "Rewards entry visible", "description": "The account panel can expose Microsoft Rewards entry after tapping the account image."}
  ],
  "images": [],
  "elements": [
    {
      "name": "Signed-in account entry",
      "role": "button",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/edge_account_image_view", "confidence": "high", "notes": "Verified on NTP before opening Rewards flow."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "state_change", "to_page_id": "edge_android_account_rewards_panel", "description": "Opens the account panel from the New Tab Page."}}
      ]
    },
    {
      "name": "Microsoft Rewards entry",
      "role": "button",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/rewards_entry", "confidence": "high", "notes": "Tapped to open the Rewards page from account panel."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_account_rewards_panel", "description": "Opens the Microsoft Rewards page. The title bar is used as the page-open marker."}}
      ]
    },
    {
      "name": "Rewards title bar",
      "role": "container",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/title_bar", "confidence": "high", "notes": "Verified after opening Microsoft Rewards."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Confirms the Microsoft Rewards page opened normally."}}
      ]
    }
  ]
}
```