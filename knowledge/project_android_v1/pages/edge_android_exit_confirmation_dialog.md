# Exit Browser Confirmation Dialog

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_exit_confirmation_dialog",
  "name": "Exit Browser Confirmation Dialog",
  "identifiers": [
    {"name": "Exit Microsoft Edge prompt visible", "description": "The confirmation dialog shows Exit Microsoft Edge? after choosing Exit browser."}
  ],
  "images": [],
  "elements": [
    {
      "name": "Dialog title",
      "role": "text",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Exit Microsoft Edge?']", "confidence": "high", "notes": "Verified after selecting Exit browser from overflow menu."}
      ],
      "operations": [
        {"operation": "verify_visible", "result": {"type": "verify", "to_page_id": null, "description": "Confirms the exit confirmation dialog is open."}}
      ]
    },
    {
      "name": "Cancel",
      "role": "button",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.Button[@text='Cancel']", "confidence": "high", "notes": "Cancel button closes the dialog and returns to the New Tab Page."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "close_dialog", "to_page_id": "edge_android_new_tab_page", "description": "Dismisses the exit dialog and returns to the New Tab Page."}}
      ]
    }
  ]
}
```