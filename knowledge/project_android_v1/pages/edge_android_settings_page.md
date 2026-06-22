# Settings Page

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_settings_page",
  "name": "Settings Page",
  "identifiers": [
    {"name": "Settings title visible", "description": "The Settings page title is visible after selecting Settings from the overflow menu."},
    {"name": "Settings list entries visible", "description": "The page exposes L1 settings entries such as Search, Appearance and layout, Tabs, Accessibility, Languages, Site settings, and About Microsoft Edge."}
  ],
  "images": [],
  "elements": [
    {
      "name": "Settings title",
      "role": "text",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Settings']", "confidence": "high", "notes": "Used to verify Settings opened from overflow menu."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Confirms the Settings page is open."}}
      ]
    },
    {
      "name": "Navigate up",
      "role": "button",
      "reference_locators": [
        {"strategy": "accessibility id", "selector": "Navigate up", "confidence": "high", "notes": "Returns from Settings to the New Tab Page when used at the Settings root."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_new_tab_page", "description": "Leaves Settings and returns to the New Tab Page."}},
        {"operation": "press_key_back", "result": {"type": "navigate", "to_page_id": "edge_android_new_tab_page", "description": "Android Back can also return from Settings to the New Tab Page."}}
      ]
    },
    {
      "name": "Search settings entry",
      "role": "list item",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Search']", "confidence": "high", "notes": "Used before opening Search engine settings."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_settings_subpage", "description": "Opens the Search settings subpage."}}
      ]
    },
    {
      "name": "Search engine entry",
      "role": "list item",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Search engine']", "confidence": "high", "notes": "Available from the Search settings subpage."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_search_engine_page", "description": "Opens the Search engine selection page."}}
      ]
    },
    {
      "name": "Common settings section",
      "role": "list item",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Microsoft password manager']", "confidence": "medium", "notes": "Settings list entry from the upper settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Payment methods']", "confidence": "medium", "notes": "Settings list entry from the upper settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Personal info']", "confidence": "medium", "notes": "Settings list entry from the upper settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Privacy and security']", "confidence": "medium", "notes": "Settings list entry from the upper settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Appearance and layout']", "confidence": "medium", "notes": "Settings list entry from the middle settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='New tab page']", "confidence": "medium", "notes": "May require vertical scroll in Settings."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Tabs']", "confidence": "medium", "notes": "Settings list entry from the middle settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Accessibility']", "confidence": "medium", "notes": "Settings list entry from the middle settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Languages']", "confidence": "medium", "notes": "May require vertical scroll in Settings."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Site settings']", "confidence": "medium", "notes": "May require vertical scroll in Settings."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Notifications']", "confidence": "medium", "notes": "May require vertical scroll in Settings."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='About Microsoft Edge']", "confidence": "medium", "notes": "May require vertical scroll in Settings."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_settings_subpage", "description": "Opens the selected Settings L1 subpage. Use the entry text as the expected subpage title."}}
      ]
    },
    {
      "name": "Set as default browser entry",
      "role": "list item",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Set as default browser' and contains(@resource-id, 'android:id/title')]", "confidence": "medium", "notes": "Opens a system confirmation dialog when Android default-browser settings are available."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "open_dialog", "to_page_id": "edge_android_settings_subpage", "description": "Opens the Set Edge as default browser dialog; Cancel returns to Settings."}}
      ]
    }
  ]
}
```