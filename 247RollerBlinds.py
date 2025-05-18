import re
from playwright.sync_api import Playwright, sync_playwright, expect
import time
import csv


def run(playwright: Playwright) -> None:
    # Use headless mode for maximum speed
    browser = playwright.chromium.launch(
        headless=True,
        args=['--disable-dev-shm-usage']
    )

    context = browser.new_context()

    # Block non-essential resources for speed
    context.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2}",
                  lambda route: route.abort())

    page = context.new_page()

    print("Loading page...")
    page.goto(
        "https://www.247blinds.co.uk/andromeda-breeze-white-vertical-blind",
        wait_until="domcontentloaded"
    )

    print("Handling popups...")
    # Handle cookie consent
    try:
        page.get_by_role("button", name="Allow Selected").click(timeout=3000)
        print("Clicked cookie consent")
    except:
        print("No cookie popup found")

    # Handle signup popup
    try:
        page.locator("iframe[title=\"Sign Up via Text for Offers\"]").content_frame.get_by_test_id(
            "dismissbutton2").click()
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

    # Wait for form to be ready with more patience
    print("Waiting for form...")
    try:
        page.wait_for_selector("#input-custom-Width",
                               state="visible", timeout=10000)
        page.wait_for_selector("#input-custom-Drop",
                               state="visible", timeout=10000)
        # Wait for page to stabilize
        page.wait_for_timeout(3000)
    except Exception as e:
        print(f"Warning: Form elements not immediately visible: {e}")
        print("Trying to refresh the page...")
        page.reload()
        page.wait_for_timeout(5000)
        page.wait_for_selector("#input-custom-Width",
                               state="visible", timeout=15000)
        page.wait_for_selector("#input-custom-Drop",
                               state="visible", timeout=15000)

    # Get references to input elements once (for speed)
    width_input = page.locator("#input-custom-Width")
    drop_input = page.locator("#input-custom-Drop")
    price_button = page.get_by_role("button", name="Get Price")

    # Dictionary to store prices
    price_data = {}

    # Define width and drop ranges
    widths = range(41, 211, 10)  # 41, 51, 61, ..., 201
    drops = range(41, 181, 10)   # 41, 51, 61, ..., 171

    print("Starting price collection...")
    start_time = time.time()
    total_combinations = 0
    current_width = None

    # Loop through all combinations
    for width in widths:
        # Only update width when it changes (optimization)
        if current_width != width:
            print(f"Setting width to {width}...")
            width_input.click()
            width_input.press("Control+a")
            width_input.fill(str(width))
            current_width = width

        for drop in drops:
            total_combinations += 1
            print(f"Processing {width}x{drop}...")

            # Enter drop value
            drop_input.click()
            drop_input.press("Control+a")
            drop_input.fill(str(drop))

            # Get price
            price_button.click()

            # Wait for price to appear with retries
            max_retries = 3  # Increased from 2 to 3
            retry_count = 0
            got_price = False

            # Use longer timeouts for first few combinations
            # First few combinations
            is_early_combination = (width == 41 and drop <= 61)
            # 5s for early ones, 2s for others
            timeout = 5000 if is_early_combination else 2000
            # Longer waits for early combinations
            wait_time = 1500 if is_early_combination else 500

            while retry_count < max_retries and not got_price:
                try:
                    # Wait for level2-area to update with a price
                    page.wait_for_function(
                        """() => {
                            const area = document.querySelector('#level2-area');
                            return area && area.textContent.includes('£');
                        }""",
                        timeout=timeout  # Use dynamic timeout based on combination
                    )

                    # Check for specific price element with class .price
                    price_element = page.locator("#level2-area .price").first

                    try:
                        # Use the .price element if available
                        price_text = price_element.text_content().strip()
                        price_match = re.search(r'£(\d+\.\d+)', price_text)
                        if price_match:
                            price_value = float(price_match.group(1))
                            price_data[(width, drop)] = price_value
                            print(f"{width}x{drop}: {price_text}")
                            got_price = True
                        else:
                            # If for some reason .price element doesn't contain a price
                            retry_count += 1
                            if retry_count < max_retries:
                                print(
                                    f"  No price found in .price, retrying... ({retry_count}/{max_retries})")
                                price_button.click()
                                # Dynamic wait time
                                page.wait_for_timeout(wait_time)
                            else:
                                # Fallback to the second price element
                                price_elements = page.locator(
                                    "text=/£[0-9]+\\.[0-9]+/").all()
                                if len(price_elements) > 1:
                                    price_text = price_elements[1].text_content(
                                    ).strip()
                                    price_match = re.search(
                                        r'£(\d+\.\d+)', price_text)
                                    if price_match:
                                        price_value = float(
                                            price_match.group(1))
                                        price_data[(width, drop)] = price_value
                                        print(
                                            f"{width}x{drop}: {price_text} (fallback)")
                                        got_price = True
                                    else:
                                        print(
                                            f"{width}x{drop}: No price found")
                                        price_data[(width, drop)] = None
                                        got_price = True
                                else:
                                    print(
                                        f"{width}x{drop}: No price elements found")
                                    price_data[(width, drop)] = None
                                    got_price = True
                    except Exception as e:
                        # Fallback to the second price element if .price selector fails
                        retry_count += 1
                        if retry_count < max_retries:
                            print(
                                f"  Error getting price, retrying... ({retry_count}/{max_retries})")
                            price_button.click()
                            # Dynamic wait time
                            page.wait_for_timeout(wait_time)
                        else:
                            # Last attempt with fallback
                            price_elements = page.locator(
                                "text=/£[0-9]+\\.[0-9]+/").all()
                            if len(price_elements) > 1:
                                price_text = price_elements[1].text_content(
                                ).strip()
                                price_match = re.search(
                                    r'£(\d+\.\d+)', price_text)
                                if price_match:
                                    price_value = float(price_match.group(1))
                                    price_data[(width, drop)] = price_value
                                    print(
                                        f"{width}x{drop}: {price_text} (fallback)")
                                    got_price = True
                                else:
                                    print(
                                        f"{width}x{drop}: No valid price in element")
                                    price_data[(width, drop)] = None
                                    got_price = True
                            else:
                                print(f"{width}x{drop}: Error: {e}")
                                price_data[(width, drop)] = None
                                got_price = True

                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(
                            f"  Error waiting for price, retrying... ({retry_count}/{max_retries})")
                        price_button.click()
                        # Even longer wait on error
                        page.wait_for_timeout(wait_time * 2)
                    else:
                        print(
                            f"{width}x{drop}: Failed after {max_retries} attempts: {e}")
                        price_data[(width, drop)] = None
                        got_price = True

    elapsed_time = time.time() - start_time
    avg_time = elapsed_time / total_combinations if total_combinations > 0 else 0
    print(
        f"\nCompleted {total_combinations} combinations in {elapsed_time:.2f}s")
    print(f"Average time per combination: {avg_time:.3f}s")

    # Create price matrix and save to CSV
    print("\nCreating price matrix...")

    # Get all unique widths and drops
    all_widths = sorted(list(set(w for w, d in price_data.keys())))
    all_drops = sorted(list(set(d for w, d in price_data.keys())))

    # Create the price matrix
    matrix_data = []

    # Header row (widths)
    header = ['Drop/Width'] + [f'{w}cm' for w in all_widths]
    matrix_data.append(header)

    # Data rows
    for drop in all_drops:
        row = [f'{drop}cm']
        for width in all_widths:
            price = price_data.get((width, drop))
            if price is not None:
                row.append(f'£{price:.2f}')
            else:
                row.append('N/A')
        matrix_data.append(row)

    # Save to CSV
    filename = f'florenza_roller_blind_prices_{int(time.time())}.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(matrix_data)

    print(f"Price matrix saved to: {filename}")

    # Also create a detailed CSV with all data
    detailed_filename = f'florenza_detailed_prices_{int(time.time())}.csv'
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
