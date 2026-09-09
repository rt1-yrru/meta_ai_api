"""Playwright browser backend — pure Python, no Node.js needed."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .exceptions import BrowserNotInstalledError, ConnectionError
from .utils import DEFAULT_UA, is_media_url, logger

try:
    from playwright.sync_api import sync_playwright, Browser, Page
except ImportError:
    sync_playwright = None
    Browser = None
    Page = None


class PlaywrightBackend:
    """Browser automation backend using Playwright (pure Python)."""

    def __init__(self, cookies: dict, headed: bool = False,
                 session_name: str = "metaai", user_agent: str = DEFAULT_UA):
        self.cookies = cookies
        self.headed = headed
        self.session_name = session_name
        self.user_agent = user_agent
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._ready = False

    def _check_installed(self):
        if sync_playwright is None:
            raise BrowserNotInstalledError(
                "Playwright is not installed. Install it with:\n"
                "  pip install metaai-sdk[playwright]\n"
                "  playwright install chromium\n"
                "  playwright install-deps  # Linux/Colab only"
            )

    def setup(self) -> None:
        """Start browser and inject cookies."""
        print("DEBUG: 1. Checking installed...")
        self._check_installed()

        print("DEBUG: 2. Starting Playwright engine...")
        self._playwright = sync_playwright().start()

        print("DEBUG: 3. Launching Chrome...")
        self._browser = self._playwright.chromium.launch(
            channel="chrome",  # Uses system Google Chrome.
            headless=not self.headed,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        print("DEBUG: 4. Chrome launched successfully!")

        print("DEBUG: 5. Creating context & adding cookies...")
        context = self._browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1280, "height": 720},
        )

        # Set cookies
        cookie_list = []
        for name, value in self.cookies.items():
            cookie_list.append({
                "name": name,
                "value": value,
                "domain": ".meta.ai",
                "path": "/",
            })
        context.add_cookies(cookie_list)

        print("DEBUG: 6. Opening Meta.ai...")
        self._page = context.new_page()
        self._page.goto("https://www.meta.ai/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        print("DEBUG: 7. Page loaded. Dismissing overlays...")

        # Dismiss any cookie consent / overlay dialogs
        self._dismiss_overlays()

        # Reload to apply cookies
        print("DEBUG: 8. Reloading page...")
        self._page.reload(wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        self._dismiss_overlays()

        self._ready = True
        print("DEBUG: 9. Playwright backend ready!")
        logger.info("Playwright backend ready")

    def _dismiss_overlays(self):
        """Dismiss cookie consent, dialogs, and overlays that might block the input."""
        try:
            # Removed "Connect" so it doesn't click the Google Calendar app buttons!
            for text in ["Dismiss", "Accept all", "Accept", "Got it", "Close", "OK", "Not now", "Maybe later", "Skip"]:
                try:
                    btn = self._page.query_selector(f'button:has-text("{text}")')
                    if btn and btn.is_visible():
                        btn.click()
                        time.sleep(1)
                        logger.info(f"Dismissed overlay: {text}")
                except Exception:
                    pass
        except Exception:
            pass

    def send_message(self, prompt: str, timeout: int = 120,
                     thinking_mode: bool = False) -> Dict[str, Any]:
        """Send a prompt and return media URLs + text response."""
        if not self._ready:
            self.setup()

        if thinking_mode:
            self._switch_mode("Thinking")
        else:
            self._switch_mode("Instant")

        # Dismiss any overlays that appeared
        self._dismiss_overlays()

        # Find and fill the input — try multiple selectors
        typed = False
        selectors = [
            'textarea[data-testid="composer-input"]',
            'div[data-testid="composer-input"] [contenteditable]',
            'textarea[placeholder*="Ask Meta"]',
            '[role="textbox"]',
            'textarea',
        ]

        for selector in selectors:
            try:
                el = self._page.query_selector(selector)
                if el:
                    # Scroll into view
                    el.scroll_into_view_if_needed(timeout=5000)
                    time.sleep(0.5)
                    # Try clicking
                    el.click(timeout=5000)
                    time.sleep(0.3)
                    
                    # Use Playwright's native fill() to ensure React state updates
                    el.fill(prompt)
                    time.sleep(0.5)
                    self._page.keyboard.press("Enter")
                    typed = True
                    logger.info(f"Typed prompt using selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue

        if not typed:
            # Last resort: use JavaScript to find and fill the input
            try:
                self._page.evaluate(f"""
                    () => {{
                        const ta = document.querySelector('textarea[data-testid="composer-input"]');
                        if (ta) {{
                            ta.focus();
                            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
                            nativeInputValueSetter.call(ta, {json.dumps(prompt)});
                            ta.dispatchEvent(new Event('input', {{bubbles: true}}));
                        }}
                    }}
                """)
                time.sleep(0.5)
                self._page.keyboard.press("Enter")
                typed = True
                logger.info("Typed prompt using JavaScript fallback")
            except Exception as e:
                raise ConnectionError(f"Could not find chat input: {e}")

        # Record existing image URLs before waiting for response
        existing_urls: Set[str] = set()
        try:
            elements = self._page.query_selector_all('img[src], video[src], source[src], a[href]')
            for el in elements:
                src = el.get_attribute("src") or el.get_attribute("href") or ""
                if src and "fbcdn" in src:
                    existing_urls.add(src)
        except Exception:
            pass

        # Wait for response — only collect NEW URLs
        urls, text = self._wait_for_response(timeout, existing_urls)
        conv_id = self._get_conversation_id()

        return {"urls": urls, "text": text, "conversation_id": conv_id}

    def _switch_mode(self, mode_name: str) -> None:
        """Switch between Instant and Thinking modes."""
        try:
            mode_button = self._page.query_selector('button:has-text("Instant"), button:has-text("Thinking")')
            if mode_button and mode_button.is_visible():
                mode_button.click()
                time.sleep(1)
                mode_item = self._page.query_selector(f'[role="menuitemcheckbox"]:has-text("{mode_name}")')
                if mode_item:
                    mode_item.click()
                    time.sleep(1)
        except Exception as e:
            logger.debug(f"Failed to switch mode: {e}")

    def _wait_for_response(self, timeout: int, existing_urls: Optional[Set[str]] = None) -> Tuple[List[str], str]:
        """Wait for either media URLs or text response. Only collect NEW URLs."""
        urls: Set[str] = set()
        last_text = ""
        text_stable_count = 0
        start = time.time()
        existing = existing_urls or set()

        while time.time() - start < timeout:
            time.sleep(2)

            # Check for NEW media URLs only
            try:
                elements = self._page.query_selector_all('img[src], video[src], source[src], a[href]')
                for el in elements:
                    src = el.get_attribute("src") or el.get_attribute("href") or ""
                    if src and "fbcdn" in src and is_media_url(src) and src not in existing:
                        urls.add(src)
            except Exception:
                pass

            if urls:
                time.sleep(3)
                return sorted(urls), self._extract_text()

            # Check for text response
            try:
                text = self._page.evaluate("""
                    () => {
                        let selectors = [
                            '[class*="assistant-message"]',
                            '[data-testid*="assistant"]',
                            '[data-testid*="response"]',
                            'div[role="article"] div[dir="auto"]'
                        ];
                        for (let sel of selectors) {
                            let msgs = document.querySelectorAll(sel);
                            if (msgs.length > 0) {
                                let text = msgs[msgs.length - 1].textContent?.trim();
                                if (text) return text;
                            }
                        }
                        
                        // NUCLEAR FALLBACK: Get all text blocks, return the last one that isn't a button/input
                        let elements = document.querySelectorAll('div[dir="auto"], span[dir="auto"]');
                        for (let i = elements.length - 1; i >= 0; i--) {
                            let text = elements[i].textContent?.trim();
                            if (text && elements[i].closest('button, input, textarea, [role="textbox"]') === null) {
                                return text;
                            }
                        }
                        return '';
                    }
                """)
                if text:
                    print(f"DEBUG: Found text: {text[:50]}...")  # <--- THIS WILL SHOW US WHAT IT FOUND
                    if text == last_text:
                        text_stable_count += 1
                        if text_stable_count >= 2:
                            return [], text
                    else:
                        text_stable_count = 0
                        last_text = text
            except Exception as e:
                print(f"DEBUG: text evaluation failed: {e}")
                pass

        return sorted(urls), last_text

    def _extract_text(self) -> str:
        try:
            return self._page.evaluate("""
                () => {
                    let selectors = [
                        '[class*="assistant-message"]',
                        '[data-testid*="assistant"]',
                        '[data-testid*="response"]',
                        'div[role="article"] div[dir="auto"]'
                    ];
                    for (let sel of selectors) {
                        let msgs = document.querySelectorAll(sel);
                        if (msgs.length > 0) {
                            let text = msgs[msgs.length - 1].textContent?.trim();
                            if (text) return text;
                        }
                    }
                    
                    // NUCLEAR FALLBACK
                    let elements = document.querySelectorAll('div[dir="auto"], span[dir="auto"]');
                    for (let i = elements.length - 1; i >= 0; i--) {
                        let text = elements[i].textContent?.trim();
                        if (text && elements[i].closest('button, input, textarea, [role="textbox"]') === null) {
                            return text;
                        }
                    }
                    return '';
                }
            """)
        except Exception:
            return ""

    def _get_conversation_id(self) -> str:
        try:
            url = self._page.url
            m = re.search(r'/prompt/([0-9a-f-]+)', url)
            if m:
                return m.group(1)
        except Exception:
            pass
        return ""

    def list_conversations(self) -> List[dict]:
        """Get all conversations from the sidebar."""
        try:
            convs = self._page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href*="/prompt/"]'));
                    return links.map(a => ({
                        title: a.textContent?.trim(),
                        url: a.href
                    })).filter(c => c.title);
                }
            """)
            result = []
            for c in convs:
                if isinstance(c, dict):
                    result.append({
                        "id": c.get("url", "").split("/prompt/")[-1] if "/prompt/" in c.get("url", "") else "",
                        "title": c.get("title", ""),
                        "url": c.get("url", ""),
                    })
            return result
        except Exception:
            return []

    def use_as_reference(self, image_url: str, prompt: str, timeout: int = 120) -> Dict[str, Any]:
        """Use an existing image as a reference for a new generation."""
        try:
            ref_button = self._page.query_selector('button[aria-label="Use as reference"]')
            if ref_button:
                ref_button.click()
                time.sleep(2)

            self._dismiss_overlays()
            for selector in ['textarea[data-testid="composer-input"]', '[role="textbox"]', 'textarea']:
                try:
                    el = self._page.query_selector(selector)
                    if el:
                        el.click(timeout=5000)
                        el.fill(prompt)
                        time.sleep(0.5)
                        self._page.keyboard.press("Enter")
                        break
                except Exception:
                    continue

            # Capture existing URLs before waiting for new generation
            existing_urls: Set[str] = set()
            try:
                elements = self._page.query_selector_all('img[src], video[src], source[src], a[href]')
                for el in elements:
                    src = el.get_attribute("src") or el.get_attribute("href") or ""
                    if src and "fbcdn" in src:
                        existing_urls.add(src)
            except Exception:
                pass

            urls, text = self._wait_for_response(timeout, existing_urls)
            return {"urls": urls, "text": text, "conversation_id": self._get_conversation_id()}
        except Exception as e:
            return {"urls": [], "text": "", "conversation_id": "", "error": str(e)}

    def new_chat(self) -> None:
        """Start a new chat conversation."""
        try:
            link = self._page.query_selector('a:has-text("New chat")')
            if link:
                link.click()
                time.sleep(2)
        except Exception as e:
            logger.warning(f"Failed to start new chat: {e}. Messages may append to previous chat.")

    def close(self) -> None:
        try:
            if self._page:
                self._page.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")
        self._ready = False
