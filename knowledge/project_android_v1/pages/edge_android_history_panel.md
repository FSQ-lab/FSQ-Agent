# History Panel

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_history_panel",
  "name": "History Panel",
  "identifiers": [
    {"name": "History hint text visible", "description": "The panel contains hint text with History after selecting History from overflow menu."},
    {"name": "Hub view pager visible", "description": "The History panel uses the shared hub view pager container."}
  ],
  "images": [],
  "elements": [
    {
      "name": "History title or hint",
      "role": "panel marker",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/hint_text", "confidence": "high", "notes": "Primary title locator for the History panel."},
        {"strategy": "id", "selector": "com.microsoft.emmx:id/hub_view_pager", "confidence": "medium", "notes": "Shared hub container verified after opening History."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Verifies that the History panel is open."}}
      ]
    },
    {
      "name": "Close button",
      "role": "button",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/close_button", "confidence": "high", "notes": "Closes the History panel and returns to NTP."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_new_tab_page", "description": "Closes History and returns to the New Tab Page."}},
        {"operation": "press_key_back", "result": {"type": "navigate", "to_page_id": "edge_android_new_tab_page", "description": "Android Back key also returns from History to the New Tab Page."}}
      ]
    }
  ]
}
```