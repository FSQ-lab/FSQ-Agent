# Loaded Web Page

```json
{
  "schema_version": "page_knowledge_page_v1",
  "page_id": "edge_android_web_page",
  "name": "Loaded Web Page",
  "identifiers": [
    {"name": "URL bar contains loaded target", "description": "After submitting a URL or keyword, the URL bar can confirm the loaded target or search engine domain."},
    {"name": "WebView visible", "description": "Loaded web content exposes an Android WebView."},
    {"name": "Page can scroll", "description": "Page content can be verified after vertical scroll gestures."}
  ],
  "images": [],
  "elements": [
    {
      "name": "URL bar",
      "role": "text field",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/url_bar", "confidence": "high", "notes": "Used to verify bing.com, chinatravel.com, google.com, developer.wikimedia.org, and keyword search results."}
      ],
      "operations": [
        {"operation": "verify_contains_text", "result": {"type": "verify", "to_page_id": null, "description": "Confirms the current loaded page or search provider from URL-bar text."}},
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_omnibox_zip", "description": "Refocuses the address bar and returns to editable omnibox suggestions."}},
        {"operation": "long_press", "result": {"type": "open_dialog", "to_page_id": null, "description": "May open address-bar layout controls such as Move address bar to top/bottom."}}
      ]
    },
    {
      "name": "Refresh button",
      "role": "button",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/refresh_button", "confidence": "high", "notes": "Refresh button locator for bottom-toolbar web pages; verify WebView content afterward."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "state_change", "to_page_id": "edge_android_web_page", "description": "Reloads the current web page."}}
      ]
    },
    {
      "name": "WebView",
      "role": "web content",
      "reference_locators": [
        {"strategy": "class name", "selector": "android.webkit.WebView", "confidence": "high", "notes": "Used to verify a web page after reload and after scroll."}
      ],
      "operations": [
        {"operation": "scroll_vertical", "result": {"type": "state_change", "to_page_id": "edge_android_web_page", "description": "Scrolls page content; address-bar controls may hide or reappear depending on direction."}}
      ]
    },
    {
      "name": "Go back",
      "role": "button",
      "reference_locators": [
        {"strategy": "accessibility id", "selector": "Go back", "confidence": "high", "notes": "Bottom toolbar back button returned from a linked page to the previous URL state."}
      ],
      "operations": [
        {"operation": "tap", "result": {"type": "navigate", "to_page_id": "edge_android_web_page", "description": "Navigates to the previous web page state."}}
      ]
    },
    {
      "name": "Control container",
      "role": "toolbar container",
      "reference_locators": [
        {"strategy": "id", "selector": "com.microsoft.emmx:id/control_container", "confidence": "medium", "notes": "Can disappear after scrolling according to toolbar behavior."}
      ],
      "operations": [
        {"operation": "verify_not_visible_after_scroll", "result": {"type": "verify", "to_page_id": null, "description": "Confirms toolbar hide behavior after repeated scroll gestures."}}
      ]
    }
  ]
}
```