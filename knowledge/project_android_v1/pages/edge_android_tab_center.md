# Tab Center

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_tab_center",
  "name": "Tab Center",
  "identifiers": [
    {
      "name": "Standard tabs count visible",
      "description": "The tab center exposes content descriptions such as 4 standard tabs or 3 standard tabs."
    },
    {
      "name": "Tab center menu visible",
      "description": "The tab center can expose a menu button for clear-all-tabs actions."
    }
  ],
  "images": [],
  "elements": [
    {
      "name": "Tab center menu button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/menu_button",
          "confidence": "high",
          "notes": "Used before selecting Clear all tabs."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "state_change",
            "to_page_id": "edge_android_tab_center",
            "description": "Opens tab-center settings/actions menu."
          }
        }
      ]
    },
    {
      "name": "Clear all tabs",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/close_all_tabs_menu_id",
          "confidence": "high",
          "notes": "Used with positive_button confirmation before opening a new tab from empty state."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "open_dialog",
            "to_page_id": "edge_android_tab_center",
            "description": "Starts close-all-tabs confirmation flow."
          }
        }
      ]
    },
    {
      "name": "Confirm close all tabs",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/positive_button",
          "confidence": "high",
          "notes": "Confirms Close all tabs and groups."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "state_change",
            "to_page_id": "edge_android_tab_center",
            "description": "Clears tabs and shows the empty-state new tab button."
          }
        }
      ]
    },
    {
      "name": "Open a new tab empty-state button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/empty_state_button",
          "confidence": "high",
          "notes": "Used after clearing all tabs."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_new_tab_page",
            "description": "Opens a new tab from empty tab center."
          }
        }
      ]
    },
    {
      "name": "Tab count label",
      "role": "text",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "android:id/text1",
          "confidence": "medium",
          "notes": "Used to verify counts such as 1 and 2 after adding tabs."
        },
        {
          "strategy": "xpath",
          "selector": "//android.widget.LinearLayout[@content-desc='4 standard tabs']",
          "confidence": "medium",
          "notes": "Used to verify four tab thumbnails before closing one tab."
        },
        {
          "strategy": "xpath",
          "selector": "//android.widget.LinearLayout[@content-desc='3 standard tabs']",
          "confidence": "medium",
          "notes": "Used to verify three tab thumbnails after closing one tab."
        }
      ],
      "operations": [
        {
          "operation": "verify_count",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Verifies current standard-tab count."
          }
        }
      ]
    },
    {
      "name": "Close tab thumbnail button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.ImageView[@resource-id='com.microsoft.emmx:id/action_button' and @content-desc='Close Google tab']",
          "confidence": "medium",
          "notes": "Observed for closing the Google tab in a four-tab state. The content-desc is tab-title dependent."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "state_change",
            "to_page_id": "edge_android_tab_center",
            "description": "Closes a single tab thumbnail and decreases the standard-tab count after a short wait."
          }
        }
      ]
    }
  ]
}
```