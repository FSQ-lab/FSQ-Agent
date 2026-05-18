# InPrivate Page

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_inprivate_page",
  "name": "InPrivate Page",
  "identifiers": [
    {"name": "Browse InPrivate text visible", "description": "The InPrivate landing page shows Browse InPrivate after opening a New InPrivate tab."}
  ],
  "images": [],
  "elements": [
    {
      "name": "Browse InPrivate title",
      "role": "text",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Browse InPrivate']", "confidence": "high", "notes": "Verified after tapping New InPrivate Tab from overflow menu."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Confirms the InPrivate page opened."}}
      ]
    },
    {
      "name": "Exit InPrivate mode",
      "role": "button",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.Button[@text='Exit InPrivate mode']", "confidence": "high", "notes": "Successful flow returned from InPrivate to the normal New Tab Page."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_new_tab_page", "description": "Exits InPrivate mode and returns to the normal New Tab Page."}}
      ]
    }
  ]
}
```