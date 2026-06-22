# Settings Subpage

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_settings_subpage",
  "name": "Settings Subpage",
  "identifiers": [
    {"name": "Subpage title matches selected section", "description": "The title usually matches the selected Settings L1 entry, such as Microsoft password manager, Payment methods, Personal info, Privacy and security, Search, Appearance and layout, New tab page, Tabs, Accessibility, Languages, Site settings, Notifications, or About Microsoft Edge."},
    {"name": "Navigate up visible", "description": "Settings subpages expose Navigate up to return to the Settings root."}
  ],
  "images": [],
  "elements": [
    {
      "name": "Subpage title",
      "role": "text",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Microsoft password manager']", "confidence": "medium", "notes": "Settings subpage title from the upper settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Payment methods']", "confidence": "medium", "notes": "Settings subpage title from the upper settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Personal info']", "confidence": "medium", "notes": "Settings subpage title from the upper settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Privacy and security']", "confidence": "medium", "notes": "Settings subpage title from the upper settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Search']", "confidence": "medium", "notes": "Settings subpage title from the middle settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Appearance and layout']", "confidence": "medium", "notes": "Settings subpage title from the middle settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='New tab page']", "confidence": "medium", "notes": "Settings subpage title from the middle settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[contains(@text,'Tabs')]", "confidence": "medium", "notes": "Settings subpage title from the middle settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Accessibility']", "confidence": "medium", "notes": "Settings subpage title from the middle settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Languages']", "confidence": "medium", "notes": "Settings subpage title from the lower settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Site settings']", "confidence": "medium", "notes": "Settings subpage title from the lower settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Notifications']", "confidence": "medium", "notes": "Settings subpage title from the lower settings section."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='About Microsoft Edge']", "confidence": "medium", "notes": "Settings subpage title from the lower settings section."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Verifies that the chosen Settings subpage opened."}}
      ]
    },
    {
      "name": "Navigate up",
      "role": "button",
      "reference_locators": [
        {"strategy": "accessibility id", "selector": "Navigate up", "confidence": "high", "notes": "Used after every verified Settings subpage to return to the Settings root."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_settings_page", "description": "Returns from a Settings subpage to the Settings root."}}
      ]
    },
    {
      "name": "Set default browser dialog cancel",
      "role": "button",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[contains(@text, 'Set Edge') and contains(@text, 'as your default browser app?')]", "confidence": "medium", "notes": "Dialog title after tapping Set as default browser."},
        {"strategy": "xpath", "selector": "//android.widget.Button[@text='Cancel']", "confidence": "medium", "notes": "Cancel dismisses the default-browser dialog."}
      ],
      "operations": [
        {"operation": "tap_cancel", "result": {"type": "close_dialog", "to_page_id": "edge_android_settings_page", "description": "Cancels the default-browser dialog and returns to Settings."}}
      ]
    }
  ]
}
```