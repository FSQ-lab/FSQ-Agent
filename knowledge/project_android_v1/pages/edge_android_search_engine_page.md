# Search Engine Settings Page

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_search_engine_page",
  "name": "Search Engine Settings Page",
  "identifiers": [
    {"name": "Search engine options visible", "description": "The page shows options such as Google and Bing for the default search engine."},
    {"name": "Selected engine summary visible on return", "description": "After choosing an engine and navigating back, the Search settings page summary can show Google or Bing."}
  ],
  "images": [],
  "elements": [
    {
      "name": "Google search engine option",
      "role": "radio option",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Google']", "confidence": "high", "notes": "Tapped in the successful third-party search-engine run."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "state_change", "to_page_id": "edge_android_search_engine_page", "description": "Sets Google as the search engine."}}
      ]
    },
    {
      "name": "Bing search engine option",
      "role": "radio option",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@text='Bing']", "confidence": "high", "notes": "Tapped to restore Bing at the end of the successful run."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "state_change", "to_page_id": "edge_android_search_engine_page", "description": "Sets Bing as the search engine."}}
      ]
    },
    {
      "name": "Navigate back to Search settings",
      "role": "system key",
      "reference_locators": [],
      "operations": [
        {"operation": "press_key_back", "result": {"type": "navigate", "to_page_id": "edge_android_settings_subpage", "description": "Returns to the Search settings subpage where the selected engine summary can be verified."}}
      ]
    },
    {
      "name": "Selected engine summary",
      "role": "text",
      "reference_locators": [
        {"strategy": "xpath", "selector": "//android.widget.TextView[@resource-id='android:id/summary' and @text='Google']", "confidence": "medium", "notes": "Verified after choosing Google."},
        {"strategy": "xpath", "selector": "//android.widget.TextView[@resource-id='android:id/summary' and @text='Bing']", "confidence": "medium", "notes": "Verified after restoring Bing."}
      ],
      "operations": [
        {"operation": "verify_text", "result": {"type": "verify", "to_page_id": null, "description": "Confirms the selected search engine summary."}}
      ]
    }
  ]
}
```