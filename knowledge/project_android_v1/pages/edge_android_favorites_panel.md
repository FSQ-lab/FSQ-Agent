# Favorites Panel

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_favorites_panel",
  "name": "Favorites Panel",
  "identifiers": [
    {"name": "Favorites title visible", "description": "The Favorites title is visible after selecting Favorites from the overflow menu."},
    {"name": "Bookmark view switcher visible", "description": "The panel exposes the bookmark view switcher container."}
  ],
  "images": [],
  "elements": [
    {
      "name": "Favorites title and container",
      "role": "panel marker",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Favorites']", "confidence": "high", "notes": "Used to verify the Favorites panel in both open cycles."},
        {"strategy": "id", "selector": "com.microsoft.emmx:id/bookmark_view_switcher", "confidence": "high", "notes": "Panel container used in the first Favorites assertion."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Verifies that the Favorites panel is open."}}
      ]
    },
    {
      "name": "Close button",
      "role": "button",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/close_button", "confidence": "high", "notes": "Closes the panel and returns to NTP."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_new_tab_page", "description": "Closes Favorites and returns to the New Tab Page."}},
        {"operation": "press_key_back", "result": {"type": "navigate", "to_page_id": "edge_android_new_tab_page", "description": "Android Back key also returns from Favorites to the New Tab Page."}}
      ]
    }
  ]
}
```