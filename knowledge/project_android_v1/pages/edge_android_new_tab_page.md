# New Tab Page

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_new_tab_page",
  "name": "New Tab Page",
  "identifiers": [
    {
      "name": "Account menu visible",
      "description": "The New Tab Page exposes an Account menu entry. Successful runs repeatedly used this as the first stable NTP marker."
    },
    {
      "name": "NTP scroll view visible",
      "description": "The main New Tab Page container is visible after returning from hub panels or dialogs."
    },
    {
      "name": "Search box visible",
      "description": "The NTP search box/address entry is available for search and URL entry flows."
    }
  ],
  "images": [
    {
      "path": "../assets/images/screenshot_1778749755004.png",
      "description": "Observed NTP at the start of an overflow-menu Downloads run."
    },
    {
      "path": "../assets/images/screenshot_1778749824996.png",
      "description": "Observed NTP after returning from the Downloads panel with Android Back."
    }
  ],
  "elements": [
    {
      "name": "Account menu",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "accessibility id",
          "selector": "Account menu",
          "confidence": "high",
          "notes": "Used as the common NTP readiness marker across successful Android runs."
        }
      ],
      "operations": [
        {
          "operation": "verify_visible",
          "result": {
            "type": "verify",
            "to_page_id": null,
            "description": "Confirms the browser is on or has returned to the New Tab Page."
          }
        },
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_account_rewards_panel",
            "description": "Opens the account area; a signed-in account can expose Microsoft Rewards."
          }
        }
      ]
    },
    {
      "name": "Browser menu",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/overflow_button_bottom",
          "confidence": "high",
          "notes": "Bottom toolbar overflow button used in menu, hub, settings, InPrivate, and exit-browser runs."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_overflow_menu",
            "description": "Opens the browser overflow menu from the bottom toolbar."
          }
        }
      ]
    },
    {
      "name": "Search box",
      "role": "text field entry point",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/search_box_text",
          "confidence": "high",
          "notes": "Used to enter the omnibox/ZIP state from the NTP in top and bottom omnibox runs."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_omnibox_zip",
            "description": "Focuses the omnibox and opens the ZIP suggestions page."
          }
        }
      ]
    },
    {
      "name": "Tab center button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/tab_center_button",
          "confidence": "high",
          "notes": "Used to enter tab center before clearing tabs and closing a tab thumbnail."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_tab_center",
            "description": "Opens the tab center."
          }
        }
      ]
    },
    {
      "name": "Add new tab button",
      "role": "button",
      "reference_locators": [
        {
          "strategy": "id",
          "selector": "com.microsoft.emmx:id/edge_bottom_bar_plus_button",
          "confidence": "high",
          "notes": "Observed after loading pages and used to create another NTP tab."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_new_tab_page",
            "description": "Creates a new tab and opens a fresh New Tab Page."
          }
        }
      ]
    }
  ]
}
```