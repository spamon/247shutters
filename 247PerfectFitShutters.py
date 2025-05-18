import re
from playwright.sync_api import Playwright, sync_playwright, expect
import time
import csv
import pandas as pd
from collections import defaultdict


def run(playwright: Playwright) -> None:
    # Use headless for maximum speed
    browser = playwright.chromium.launch(
        headless=True,  # Changed back to headless for speed
        args=['--disable-web-security', '--disable-dev-shm-usage']
    )

    context = browser.new_context()

    # Block images, CSS, and fonts for faster loading
    context.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}",
                  lambda route: route.abort())

    page = context.new_page()

    print("Loading page...")
    page.goto(
        "https://www.247blinds.co.uk/sierra-ice-white-perfect-fit-shutter-blind",
        wait_until="domcontentloaded"
    )

    print("Handling popups...")
    # Handle cookie consent
    try:
        page.get_by_role("button", name="Allow Selected").click(timeout=3000)
        print("Clicked cookie consent")
    except:
        print("No cookie popup found")

    # Handle signup popup - use the exact same method as the original working code
    try:
        # Wait for iframe to appear
        print("Looking for signup popup...")
        page.wait_for_selector(
            "iframe[title=\"Sign Up via Text for Offers\"]", timeout=3000)
        print("Found signup iframe")

        # Use the exact same method as the original code
        iframe = page.locator(
            "iframe[title=\"Sign Up via Text for Offers\"]").content_frame
        iframe.get_by_test_id("dismissbutton2").click()
        print("Dismissed signup popup")
    except Exception as e:
        print(f"No signup popup found or couldn't dismiss: {e}")

        # Alternative: try to remove the overlay completely
        try:
            page.evaluate("""
                const overlay = document.getElementById('attentive_overlay');
                if (overlay) {
                    overlay.remove();
                    console.log('Removed attentive overlay');
                }
            """)
            print("Removed overlay via JavaScript")
        except:
            print("Couldn't remove overlay")

    # Wait a bit for things to settle
    page.wait_for_timeout(2000)

    # Wait for form to be ready and ensure it's visible
    print("Waiting for form elements...")
    try:
        page.wait_for_selector("#input-custom-Width",
                               state="visible", timeout=5000)
        page.wait_for_selector("#input-custom-Drop",
                               state="visible", timeout=5000)

        # Ensure page is fully loaded and stable before proceeding
        print("Making sure page is stable...")
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(3000)  # Extra wait to ensure everything is ready
    except Exception as e:
        print(f"Warning: Form elements not found initially: {e}")
        print("Trying to refresh the page...")
        page.reload()
        page.wait_for_selector("#input-custom-Width",
                               state="visible", timeout=10000)
        page.wait_for_selector("#input-custom-Drop",
                               state="visible", timeout=10000)

    # Scroll to make sure form is in view
    page.locator("#input-custom-Width").scroll_into_view_if_needed()

    # Get references to input elements once
    width_input = page.locator("#input-custom-Width")
    drop_input = page.locator("#input-custom-Drop")
    price_button = page.get_by_role("button", name="Get Price")

    current_width = None

    # Dictionary to store all prices {(width, drop): price}
    price_data = {}

    print("Starting price collection...")
    start_time = time.time()
    total_combinations = 0

    # Loop through width values from 30 to 300 in increments of 10
    for width in range(30, 301, 10):
        # Only update width if it's different from current
        if current_width != width:
            print(f"Setting width to {width}...")
            # Make sure element is in view and clickable
            width_input.scroll_into_view_if_needed()
            width_input.click(force=True)  # Force click to bypass overlays
            width_input.press("Control+a")  # Select all
            width_input.fill(str(width))
            current_width = width

        # Loop through drop values from 30 to 210 in increments of 10
        for drop in range(30, 211, 10):
            total_combinations += 1
            print(f"Processing {width}x{drop}...")

            # Update drop
            drop_input.scroll_into_view_if_needed()
            drop_input.click(force=True)  # Force click
            drop_input.press("Control+a")  # Select all
            drop_input.fill(str(drop))

            # Get price
            price_button.scroll_into_view_if_needed()
            price_button.click(force=True)  # Force click

            # Wait for price to appear
            try:
                # Wait for level2-area to update with a price
                page.wait_for_function(
                    """() => {
                        const area = document.querySelector('#level2-area');
                        return area && area.textContent.includes('£');
                    }""",
                    timeout=3000
                )

                # Extract price
                price_area = page.locator("#level2-area")
                price_text = price_area.text_content()

                # Find price with regex
                price_match = re.search(r'£(\d+\.\d+)', price_text)
                if price_match:
                    # Extract just the number
                    price_value = float(price_match.group(1))
                    price_data[(width, drop)] = price_value
                    print(f"{width}x{drop}: £{price_value}")
                else:
                    print(
                        f"{width}x{drop}: No price found in: {price_text[:50]}...")
                    # Store None for missing prices
                    price_data[(width, drop)] = None

            except:
                print(f"{width}x{drop}: Timeout waiting for price")
                price_data[(width, drop)] = None  # Store None for errors

    elapsed_time = time.time() - start_time
    avg_time = elapsed_time / total_combinations if total_combinations > 0 else 0
    print(
        f"\nCompleted {total_combinations} combinations in {elapsed_time:.2f}s")
    print(f"Average time per combination: {avg_time:.3f}s")

    # Create price matrix and save to CSV
    print("\nCreating price matrix...")

    # Get all unique widths and drops
    widths = sorted(list(set(w for w, d in price_data.keys())))
    drops = sorted(list(set(d for w, d in price_data.keys())))

    # Create the price matrix
    matrix_data = []

    # Header row (widths)
    header = ['Drop/Width'] + [f'{w}cm' for w in widths]
    matrix_data.append(header)

    # Data rows
    for drop in drops:
        row = [f'{drop}cm']
        for width in widths:
            price = price_data.get((width, drop))
            if price is not None:
                row.append(f'£{price:.2f}')
            else:
                row.append('N/A')
        matrix_data.append(row)

    # Save to CSV
    filename = f'blinds_price_matrix_{int(time.time())}.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(matrix_data)

    print(f"Price matrix saved to: {filename}")

    # Also create a detailed CSV with all data
    detailed_filename = f'blinds_detailed_prices_{int(time.time())}.csv'
    with open(detailed_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Width (cm)', 'Drop (cm)', 'Price (£)'])
        for (width, drop), price in sorted(price_data.items()):
            if price is not None:
                writer.writerow([width, drop, f'{price:.2f}'])
            else:
                writer.writerow([width, drop, 'N/A'])

    print(f"Detailed prices saved to: {detailed_filename}")
    print(
        f"\nTotal prices found: {sum(1 for p in price_data.values() if p is not None)}")
    print(
        f"Missing prices: {sum(1 for p in price_data.values() if p is None)}")

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
