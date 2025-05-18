import re
from playwright.sync_api import Playwright, sync_playwright, expect
import time
import csv


def run(playwright: Playwright) -> None:
    # Try to make it go faster by adding headless mode and optimizing waits
    browser = playwright.chromium.launch(
        headless=True,  # Faster in headless mode
        args=['--disable-dev-shm-usage', '--start-maximized']
    )

    # Add a timeout for the whole process
    max_runtime = 60 * 10  # 10 minutes max
    end_time = time.time() + max_runtime

    context = browser.new_context(
        viewport={"width": 1920, "height": 1080}  # Set a large viewport
    )
    page = context.new_page()

    print("Loading page...")
    page.goto("https://www.blindsbypost.co.uk/perfect-fit-blinds/perfect-fit-shutters/cotton-white-perfect-fit-shutter/")

    # Handle cookie popup
    try:
        print("Handling cookie popup...")
        page.get_by_role("button", name="Close dialog").click()
    except Exception as e:
        print(f"No cookie dialog found or couldn't close it: {e}")

    # Wait a bit to make sure elements load
    page.wait_for_timeout(2000)

    # Dictionary to store prices
    price_data = {}

    # Define width and drop ranges
    widths = range(201, 1801, 100)  # 201, 301, 401, ..., 1701
    drops = range(229, 2401, 100)   # 229, 329, 429, ..., 2301

    print("Starting price collection...")
    start_time = time.time()
    total_combinations = 0

    # First combination - Initialize with first width and drop and click "GET INSTANT PRICE"
    first_width = widths[0]
    first_drop = drops[0]

    print(f"Setting initial width: {first_width}")
    page.get_by_placeholder("- 1800 mm").click()
    page.get_by_placeholder("- 1800 mm").fill(str(first_width))

    print(f"Setting initial drop: {first_drop}")
    page.get_by_placeholder("- 2400 mm").click()
    page.get_by_placeholder("- 2400 mm").fill(str(first_drop))

    print("Clicking GET INSTANT PRICE button...")
    page.get_by_text("GET INSTANT PRICE").click()

    print("Waiting for price calculation...")
    page.wait_for_timeout(2000)

    # Scroll down to make sure price is visible
    page.evaluate("window.scrollBy(0, 350)")

    # Define the main_price_index based on your knowledge
    main_price_index = 3  # The 4th element (0-indexed)

    # Optimized function to get the price using the known index
    def get_main_price():
        try:
            # Make sure we're scrolled to see the price
            page.evaluate("window.scrollBy(0, 350)")

            elements = page.locator("text=/£[0-9]+\\.[0-9]+/").all()

            # Check if we have enough elements and use the known index
            if len(elements) > main_price_index:
                text = elements[main_price_index].text_content().strip()
                match = re.search(r'£(\d+\.\d+)', text)
                if match:
                    return float(match.group(1))

            # Fallback: Look for any price element with a reasonable value
            for el in elements:
                text = el.text_content().strip()
                match = re.search(r'£(\d+\.\d+)', text)
                if match:
                    price = float(match.group(1))
                    if 20 <= price <= 200:
                        return price

            return None
        except Exception as e:
            print(f"  Error getting price: {e}")
            return None

    # Get the price for the first combination
    first_price = get_main_price()
    if first_price is not None:
        price_data[(first_width, first_drop)] = first_price
        print(f"{first_width}x{first_drop}: £{first_price}")
        total_combinations += 1
    else:
        print(f"{first_width}x{first_drop}: No price found")

    # Optimized function to update dimensions and get price
    def get_price_for_dimensions(width, drop):
        # Update width using keyboard shortcut for efficiency
        width_field = page.get_by_placeholder("- 1800 mm")
        width_field.click()
        page.keyboard.press("Control+a")
        width_field.fill(str(width))

        # Update drop using keyboard shortcut for efficiency
        drop_field = page.get_by_placeholder("- 2400 mm")
        drop_field.click()
        page.keyboard.press("Control+a")
        drop_field.fill(str(drop))

        # Press Tab to ensure the field loses focus and triggers the update
        page.keyboard.press("Tab")

        # Use a shorter wait time and check for price
        page.wait_for_timeout(400)  # Wait for price to update

        # Make sure we're scrolled to see the price
        page.evaluate("window.scrollBy(0, 350)")

        price_value = get_main_price()
        if price_value is not None:
            return price_value

        # If price not found, try again with a small delay
        page.wait_for_timeout(600)
        return get_main_price()

    # Loop through all widths first to minimize width changes
    current_width = first_width
    for width in widths:
        # Skip the first width as we've already processed its first drop
        if width == first_width:
            # For the first width, process remaining drops
            for drop in drops:
                # Skip the first drop as it's already processed
                if drop == first_drop:
                    continue

                total_combinations += 1
                print(f"Processing {width}x{drop}...")

                price_value = get_price_for_dimensions(width, drop)

                if price_value is not None:
                    price_data[(width, drop)] = price_value
                    print(f"{width}x{drop}: £{price_value}")
                else:
                    print(f"{width}x{drop}: No price found")
                    price_data[(width, drop)] = None
        else:
            # For all other widths, process all drops
            for drop in drops:
                # Check if we're approaching the time limit
                if time.time() > end_time:
                    print("Reached maximum runtime, saving results so far...")
                    break

                total_combinations += 1
                print(f"Processing {width}x{drop}...")

                price_value = get_price_for_dimensions(width, drop)

                if price_value is not None:
                    price_data[(width, drop)] = price_value
                    print(f"{width}x{drop}: £{price_value}")
                else:
                    print(f"{width}x{drop}: No price found")
                    price_data[(width, drop)] = None

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
    header = ['Drop/Width'] + [f'{w}mm' for w in all_widths]
    matrix_data.append(header)

    # Data rows
    for drop in all_drops:
        row = [f'{drop}mm']
        for width in all_widths:
            price = price_data.get((width, drop))
            if price is not None:
                row.append(f'£{price:.2f}')
            else:
                row.append('N/A')
        matrix_data.append(row)

    # Save to CSV
    filename = f'blindsbypost_perfect_fit_prices_{int(time.time())}.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerows(matrix_data)

    print(f"Price matrix saved to: {filename}")

    # Also create a detailed CSV with all data
    detailed_filename = f'blindsbypost_detailed_prices_{int(time.time())}.csv'
    with open(detailed_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Width (mm)', 'Drop (mm)', 'Price (£)'])
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
