# Downloads Panel

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_downloads_panel",
  "name": "Downloads Panel",
  "identifiers": [
    {"name": "Downloads title visible", "description": "The panel title text contains Downloads after choosing Downloads from the overflow menu."},
    {"name": "Hub view pager visible", "description": "The Downloads hub panel exposes the shared hub view pager container."}
  ],
  "images": [
    {"path": "../assets/images/screenshot_1778749776960.png", "description": "Downloads panel after opening it from the overflow menu."}
  ],
  "elements": [
    {
      "name": "Downloads title and container",
      "role": "panel marker",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Downloads']", "confidence": "high", "notes": "Primary title locator for the Downloads panel."},
        {"strategy": "id", "selector": "com.microsoft.emmx:id/hub_view_pager", "confidence": "medium", "notes": "Shared hub panel container verified after opening Downloads."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Verifies that the Downloads panel is open."}}
      ]
    },
    {
      "name": "Close button",
      "role": "button",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/close_button", "confidence": "high", "notes": "Tapping this returned to the NTP in the first Downloads cycle."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_new_tab_page", "description": "Closes the Downloads panel and returns to the New Tab Page."}},
        {"operation": "press_key_back", "result": {"type": "navigate", "to_page_id": "edge_android_new_tab_page", "description": "Android Back key also returns from Downloads to the New Tab Page."}}
      ]
    }
  ]
}
```