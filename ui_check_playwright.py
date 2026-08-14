from playwright.sync_api import sync_playwright, TimeoutError
import sys

URL = "http://localhost:8506"

def run_check():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Opening {URL}")
        page.goto(URL, timeout=60000)

        try:
            # Wait for sidebar to render
            page.wait_for_selector("text=Select stops to include", timeout=20000)

            # Open the Search & Add Stop expander if present
            try:
                exp = page.locator('text=Search & Add Stop')
                if exp.count() > 0:
                    exp.first.click()
            except Exception:
                pass

            # Type into the search box (placeholder text used in app)
            inp = page.locator('input[placeholder="e.g. \'Bristol, UK\' or \'Yosemite Valley\'"]')
            if inp.count() == 0:
                # try a generic input
                inp = page.locator('textarea, input').first
            inp.click()
            inp.fill('Bristol, UK')

            # Click Add button
            page.click('button:has-text("Add")')

            # Wait for the new stop name to appear in the reorder list
            page.wait_for_selector('text=Bristol', timeout=15000)
            print('Add stop: OK')

            # Try to click the first up/down/remove buttons
            up_button = page.locator('button:has-text("↑")').first
            down_button = page.locator('button:has-text("↓")').first
            remove_button = page.locator('button:has-text("✕")').first

            # Click down (if exists)
            if down_button.count() > 0:
                down_button.click()
                print('Clicked Down: OK')

            # Click up (if exists)
            if up_button.count() > 0:
                up_button.click()
                print('Clicked Up: OK')

            # Click remove
            if remove_button.count() > 0:
                remove_button.click()
                print('Clicked Remove: OK')

            print('UI check completed successfully')
            browser.close()
            return 0
        except TimeoutError as e:
            print('Timeout waiting for UI elements:', e)
            browser.close()
            return 2
        except Exception as ex:
            print('Error during UI check:', ex)
            try:
                browser.close()
            except Exception:
                pass
            return 1

if __name__ == '__main__':
    sys.exit(run_check())
