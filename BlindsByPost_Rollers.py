import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

driver = webdriver.Chrome()
driver.get(
    "https://www.blindsbypost.co.uk/roller-blinds/tradechoice-brilliant-white-roller-blinds/")

# Dismiss newsletter popup if it appears
try:
    no_thanks = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(), 'No, thanks')]"))
    )
    no_thanks.click()
except Exception:
    pass

# Range settings
width_start, width_end, width_step = 250, 2500, 100
drop_start, drop_end, drop_step = 250, 3000, 100

widths = list(range(width_start, width_end + 1, width_step))
drops = list(range(drop_start, drop_end + 1, drop_step))

# Prepare matrix: first row is ["Drop/Width", width1, width2, ...]
matrix = [["Drop/Width"] + widths]

# Initial input and button click
width_element = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "input[placeholder='250 - 2500 mm']"))
)
drop_element = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "input[placeholder='250 - 3008 mm']"))
)
width_element.clear()
width_element.send_keys(str(widths[0]))
drop_element.clear()
drop_element.send_keys(str(drops[0]))
time.sleep(1)
instant_price = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable(
        (By.CSS_SELECTOR, ".tc-container.cpf-element.tc-cell.cpf-type-header.tcwidth.tcwidth-100.get-instant-price-div.fullwidth-div"))
)
instant_price.click()
time.sleep(1)

# Loop and collect prices
for drop in drops:
    row = [drop]  # Start each row with the drop value
    for width in widths:
        # Update width and drop
        width_element = driver.find_element(
            By.CSS_SELECTOR, "input[placeholder='250 - 2500 mm']")
        width_element.clear()
        width_element.send_keys(str(width))
        time.sleep(0.4)

        drop_element = driver.find_element(
            By.CSS_SELECTOR, "input[placeholder='250 - 3008 mm']")
        drop_element.clear()
        drop_element.send_keys(str(drop))
        time.sleep(0.8)

        price_elem = driver.find_element(
            By.CSS_SELECTOR, ".cus-discount-price")
        price_text = price_elem.text.strip()
        row.append(price_text)
        print(f"Width: {width}, Drop: {drop} => Price: {price_text}")

    matrix.append(row)

# Write to CSV
with open("price_matrix.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(matrix)

print("Saved all results to price_matrix.csv")
driver.quit()
