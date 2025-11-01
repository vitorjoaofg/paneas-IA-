#!/usr/bin/env python3
"""
Playwright test for Speech Analytics feature on http://localhost:8765
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import time
import json


def test_speech_analytics():
    """Test the Speech Analytics feature"""

    test_transcript = """Operador: Bom dia, como posso ajudar? Cliente: Quero cancelar meu plano. Operador: Entendo, posso saber o motivo?"""

    results = {
        "success": False,
        "errors": [],
        "console_logs": [],
        "network_errors": [],
        "status_messages": [],
        "screenshots": []
    }

    with sync_playwright() as p:
        # Launch browser with console logging
        browser = p.chromium.launch(headless=True, slow_mo=500)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            record_video_dir="/home/jota/tools/paneas-col/test-videos"
        )
        page = context.new_page()

        # Set up console and network monitoring
        def on_console(msg):
            log_entry = {
                "type": msg.type,
                "text": msg.text,
                "location": msg.location
            }
            results["console_logs"].append(log_entry)
            print(f"[CONSOLE {msg.type}]: {msg.text}")

        def on_request_failed(request):
            error_entry = {
                "url": request.url,
                "method": request.method,
                "failure": request.failure
            }
            results["network_errors"].append(error_entry)
            print(f"[NETWORK ERROR]: {request.method} {request.url} - {request.failure}")

        page.on("console", on_console)
        page.on("requestfailed", on_request_failed)

        try:
            print("\n=== Starting Speech Analytics Test ===\n")

            # Step 1: Navigate to the page
            print("Step 1: Navigating to http://localhost:8765")
            page.goto("http://localhost:8765", wait_until="networkidle", timeout=30000)
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_01_initial.png")
            print("  -> Page loaded successfully")

            # Step 2: Enter password
            print("\nStep 2: Entering password")
            password_input = page.wait_for_selector('input[type="password"]', timeout=10000)
            password_input.fill("Paneas@321")
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_02_password_entered.png")
            print("  -> Password entered")

            # Submit password (look for button or form submit)
            submit_button = page.locator('button:has-text("Entrar"), button:has-text("Login"), button[type="submit"]').first
            if submit_button.is_visible():
                submit_button.click()
                print("  -> Password submitted")
                page.wait_for_load_state("networkidle")
                time.sleep(2)

            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_03_after_login.png")

            # Step 3: Click on "Playground" in navbar
            print("\nStep 3: Clicking on 'Playground' in navbar")
            playground_link = page.locator('nav a:has-text("Playground"), a:has-text("Playground")').first
            playground_link.click()
            print("  -> Clicked Playground")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_04_playground.png")

            # Step 4: Click on "Analytics" tab
            print("\nStep 4: Clicking on 'Analytics' tab")
            analytics_tab = page.locator('button:has-text("Analytics"), a:has-text("Analytics"), [role="tab"]:has-text("Analytics")').first
            analytics_tab.click()
            print("  -> Clicked Analytics tab")
            time.sleep(2)
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_05_analytics_tab.png")

            # Step 5 & 6: Paste text in transcript field
            print("\nStep 5-6: Pasting transcript text")

            # Wait for the analytics transcript field to be visible
            transcript_field = page.locator('#analyticsTranscript')
            transcript_field.wait_for(state="visible", timeout=10000)
            transcript_field.click()
            transcript_field.fill(test_transcript)
            print("  -> Transcript pasted successfully")

            time.sleep(1)
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_06_transcript_filled.png")

            # Step 7: Make sure "Sentimento" and "Emoção" are checked
            print("\nStep 7: Checking 'Sentimento' and 'Emoção' checkboxes")

            # Check sentiment checkbox
            sentiment_checkbox = page.locator('#analyticsSentiment')
            if not sentiment_checkbox.is_checked():
                sentiment_checkbox.check()
                print("  -> Checked 'Sentimento'")
            else:
                print("  -> 'Sentimento' already checked")

            # Check emotion checkbox
            emotion_checkbox = page.locator('#analyticsEmotion')
            if not emotion_checkbox.is_checked():
                emotion_checkbox.check()
                print("  -> Checked 'Emoção'")
            else:
                print("  -> 'Emoção' already checked")

            time.sleep(1)
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_07_checkboxes_checked.png")

            # Step 8: Click "Analisar" button
            print("\nStep 8: Clicking 'Analisar' button")
            analyze_button = page.locator('#analyticsSubmit')
            analyze_button.click()
            print("  -> Clicked 'Analisar' button")

            # Step 9: Wait for processing and capture results
            print("\nStep 9: Waiting for processing...")

            # Wait for either success or error indicators
            time.sleep(3)
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_08_processing.png")

            # Check for loading indicators
            loading_indicators = page.locator('[class*="loading"], [class*="spinner"], .progress').count()
            print(f"  -> Loading indicators found: {loading_indicators}")

            # Wait for completion (up to 60 seconds)
            max_wait = 60
            waited = 0
            while waited < max_wait:
                time.sleep(2)
                waited += 2

                # Check if loading is done
                loading_count = page.locator('[class*="loading"], [class*="spinner"]').count()
                if loading_count == 0:
                    print(f"  -> Processing completed after {waited} seconds")
                    break

                print(f"  -> Still processing... ({waited}s)")

            time.sleep(2)
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_09_results.png")

            # Step 10: Check for results, errors, or status messages
            print("\nStep 10: Checking for results and status messages...")

            # Look for error messages
            error_selectors = [
                '[class*="error"]',
                '[class*="alert-danger"]',
                '.error-message',
                '[role="alert"]'
            ]

            for selector in error_selectors:
                errors = page.locator(selector)
                count = errors.count()
                if count > 0:
                    for i in range(count):
                        error_text = errors.nth(i).text_content()
                        if error_text and error_text.strip():
                            results["errors"].append(error_text.strip())
                            print(f"  -> ERROR FOUND: {error_text.strip()}")

            # Look for success messages
            success_selectors = [
                '[class*="success"]',
                '[class*="alert-success"]',
                '.success-message'
            ]

            for selector in success_selectors:
                success_msgs = page.locator(selector)
                count = success_msgs.count()
                if count > 0:
                    for i in range(count):
                        msg_text = success_msgs.nth(i).text_content()
                        if msg_text and msg_text.strip():
                            results["status_messages"].append(msg_text.strip())
                            print(f"  -> SUCCESS MESSAGE: {msg_text.strip()}")
                            results["success"] = True

            # Look for results sections
            results_text = page.locator('body').text_content()
            if "sentiment" in results_text.lower() or "emoção" in results_text.lower():
                print("  -> Results appear to be displayed on page")
                results["success"] = True

            # Capture final page state
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_10_final.png")

            # Get all visible text content
            page_text = page.locator('body').inner_text()
            print("\n=== Page Content (last 1000 chars) ===")
            print(page_text[-1000:])

            print("\n=== Test Completed ===\n")

        except PlaywrightTimeoutError as e:
            error_msg = f"Timeout error: {str(e)}"
            results["errors"].append(error_msg)
            print(f"\n[ERROR] {error_msg}\n")
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_error.png")

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            results["errors"].append(error_msg)
            print(f"\n[ERROR] {error_msg}\n")
            page.screenshot(path="/home/jota/tools/paneas-col/screenshot_error.png")

        finally:
            # Clean up
            time.sleep(2)
            context.close()
            browser.close()

    return results


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SPEECH ANALYTICS TEST REPORT")
    print("="*60 + "\n")

    results = test_speech_analytics()

    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    print(f"\nTest Success: {results['success']}")
    print(f"\nErrors Found: {len(results['errors'])}")
    for i, error in enumerate(results['errors'], 1):
        print(f"  {i}. {error}")

    print(f"\nStatus Messages: {len(results['status_messages'])}")
    for i, msg in enumerate(results['status_messages'], 1):
        print(f"  {i}. {msg}")

    print(f"\nConsole Logs: {len(results['console_logs'])}")
    for log in results['console_logs'][-10:]:  # Show last 10
        print(f"  [{log['type']}] {log['text']}")

    print(f"\nNetwork Errors: {len(results['network_errors'])}")
    for i, error in enumerate(results['network_errors'], 1):
        print(f"  {i}. {error['method']} {error['url']}")

    # Save results to JSON
    with open("/home/jota/tools/paneas-col/test_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*60)
    print("Screenshots and results saved to:")
    print("  - /home/jota/tools/paneas-col/screenshot_*.png")
    print("  - /home/jota/tools/paneas-col/test_results.json")
    print("="*60 + "\n")
