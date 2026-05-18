# Overflow Menu

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_overflow_menu",
  "name": "Overflow Menu",
  "identifiers": [
    {
      "name": "Menu entries visible",
      "description": "The overflow menu exposes text entries such as Downloads, Favorites, History, Settings, New InPrivate Tab, Exit browser, and All menu."
    },
    {
      "name": "Opened from NTP browser menu",
      "description": "Successful flows open this page by tapping the bottom overflow button on the NTP or from a returned NTP state."
    }
  ],
  "images": [
    {
      "path": "../assets/images/screenshot_1778749768612.png",
      "description": "Observed overflow menu after tapping the browser menu during a Downloads run."
    }
  ],
  "elements": [
    {
      "name": "Downloads",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='Downloads']",
          "confidence": "high",
          "notes": "Used in two successful open/return cycles."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_downloads_panel",
            "description": "Opens the Downloads hub panel."
          }
        }
      ]
    },
    {
      "name": "Favorites",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='Favorites']",
          "confidence": "high",
          "notes": "Used in two successful Favorites panel cycles."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_favorites_panel",
            "description": "Opens the Favorites hub panel."
          }
        }
      ]
    },
    {
      "name": "History",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='History']",
          "confidence": "high",
          "notes": "Used in two successful History panel cycles."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_history_panel",
            "description": "Opens the History hub panel."
          }
        }
      ]
    },
    {
      "name": "Settings",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='Settings']",
          "confidence": "high",
          "notes": "Used in settings access, settings subpage, and search-engine configuration runs."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_settings_page",
            "description": "Opens the Settings page."
          }
        }
      ]
    },
    {
      "name": "New InPrivate Tab",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='New InPrivate Tab']",
          "confidence": "high",
          "notes": "Observed in the successful InPrivate flow."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": "edge_android_inprivate_page",
            "description": "Opens a New InPrivate tab."
          }
        }
      ]
    },
    {
      "name": "Exit browser",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='Exit browser']",
          "confidence": "medium",
          "notes": "Requires horizontal menu-page swipe before selection in the observed run."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "open_dialog",
            "to_page_id": "edge_android_exit_confirmation_dialog",
            "description": "Opens the Exit Microsoft Edge confirmation dialog."
          }
        }
      ]
    },
    {
      "name": "All menu",
      "role": "menu item",
      "reference_locators": [
        {
          "strategy": "xpath",
          "selector": "//android.widget.TextView[@text='All menu']",
          "confidence": "low",
          "notes": "Observed in a failed run; include as a weak planning hint only."
        }
      ],
      "operations": [
        {
          "operation": "tap",
          "result": {
            "type": "navigate",
            "to_page_id": null,
            "description": "May open an All Menu panel. This path was not confirmed by a successful run."
          }
        }
      ]
    }
  ]
}
```