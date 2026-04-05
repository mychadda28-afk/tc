"""
Telegram Web Number Checker - GitHub Actions Optimized
Runs in cloud with environment variables
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Get settings from environment or use defaults
BATCH_START = int(os.getenv('BATCH_START', '0'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '1000'))
WORKERS = int(os.getenv('WORKERS', '10'))

# Output files
TELEGRAM_NUMBERS = 'has_telegram.txt'
NO_TELEGRAM_NUMBERS = 'no_telegram.txt'
ERROR_NUMBERS = 'check_errors.txt'

# Stats
stats = {
    'total': 0,
    'checked': 0,
    'has_telegram': 0,
    'no_telegram': 0,
    'errors': 0,
    'start_time': 0
}

def setup_headless_browser():
    """Setup headless Chrome for GitHub Actions"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Use webdriver-manager for automatic driver setup
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def check_number_web(phone_number, worker_id=0):
    """Check single number - detects 5-digit (Telegram) vs 6-digit (Phone) OTP"""
    driver = None
    try:
        driver = setup_headless_browser()
        driver.get('https://web.telegram.org/a/')
        
        time.sleep(2)
        
        # Find phone input
        try:
            phone_input = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="tel"], input[name="phone"], input.input-field-input'))
            )
        except TimeoutException:
            phone_input = driver.find_element(By.CSS_SELECTOR, 'input')
        
        # Enter phone number
        phone_input.clear()
        phone_input.send_keys(phone_number)
        time.sleep(0.5)
        
        # Submit
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"], button.btn-primary, button')
            next_button.click()
        except:
            from selenium.webdriver.common.keys import Keys
            phone_input.send_keys(Keys.RETURN)
        
        time.sleep(2)
        
        # Check OTP input field
        try:
            code_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="tel"], input[inputmode="numeric"], input.code-input')
            
            if code_inputs:
                for inp in code_inputs:
                    maxlength = inp.get_attribute('maxlength')
                    
                    # 5 digits = Telegram
                    if maxlength == '5':
                        result = 'HAS_TELEGRAM'
                        stats['has_telegram'] += 1
                        with open(TELEGRAM_NUMBERS, 'a', encoding='utf-8') as f:
                            f.write(phone_number + '\n')
                        print(f"[W{worker_id}] 🔴 TELEGRAM: {phone_number}")
                        break
                    
                    # 6 digits = Phone (no Telegram)
                    elif maxlength == '6':
                        result = 'NO_TELEGRAM'
                        stats['no_telegram'] += 1
                        with open(NO_TELEGRAM_NUMBERS, 'a', encoding='utf-8') as f:
                            f.write(phone_number + '\n')
                        print(f"[W{worker_id}] 🟢 AVAILABLE: {phone_number}")
                        break
                else:
                    # Fallback
                    page_text = driver.page_source.lower()
                    if 'telegram' in page_text or 'app' in page_text:
                        result = 'HAS_TELEGRAM'
                        stats['has_telegram'] += 1
                        with open(TELEGRAM_NUMBERS, 'a', encoding='utf-8') as f:
                            f.write(phone_number + '\n')
                        print(f"[W{worker_id}] 🔴 TELEGRAM: {phone_number}")
                    else:
                        result = 'NO_TELEGRAM'
                        stats['no_telegram'] += 1
                        with open(NO_TELEGRAM_NUMBERS, 'a', encoding='utf-8') as f:
                            f.write(phone_number + '\n')
                        print(f"[W{worker_id}] 🟢 AVAILABLE: {phone_number}")
            else:
                page_text = driver.page_source.lower()
                if 'invalid' in page_text or 'error' in page_text:
                    result = 'INVALID'
                    stats['errors'] += 1
                    with open(ERROR_NUMBERS, 'a', encoding='utf-8') as f:
                        f.write(f"{phone_number} - INVALID\n")
                    print(f"[W{worker_id}] ⚠️ INVALID: {phone_number}")
                else:
                    result = 'UNKNOWN'
                    stats['errors'] += 1
                    with open(ERROR_NUMBERS, 'a', encoding='utf-8') as f:
                        f.write(f"{phone_number} - UNKNOWN\n")
                    print(f"[W{worker_id}] ⚠️ UNKNOWN: {phone_number}")
        
        except Exception:
            page_text = driver.page_source.lower()
            if 'telegram' in page_text or '5' in page_text:
                result = 'HAS_TELEGRAM'
                stats['has_telegram'] += 1
                with open(TELEGRAM_NUMBERS, 'a', encoding='utf-8') as f:
                    f.write(phone_number + '\n')
                print(f"[W{worker_id}] 🔴 TELEGRAM: {phone_number}")
            else:
                result = 'NO_TELEGRAM'
                stats['no_telegram'] += 1
                with open(NO_TELEGRAM_NUMBERS, 'a', encoding='utf-8') as f:
                    f.write(phone_number + '\n')
                print(f"[W{worker_id}] 🟢 AVAILABLE: {phone_number}")
        
        stats['checked'] += 1
        return {'phone': phone_number, 'status': result}
        
    except Exception as e:
        stats['errors'] += 1
        error_msg = str(e)[:50]
        with open(ERROR_NUMBERS, 'a', encoding='utf-8') as f:
            f.write(f"{phone_number} - {error_msg}\n")
        print(f"[W{worker_id}] ❌ ERROR: {phone_number}")
        return {'phone': phone_number, 'status': 'ERROR'}
    
    finally:
        if driver:
            driver.quit()

def check_numbers_parallel(numbers, workers=10):
    """Check numbers in parallel"""
    
    # Clear old files
    for f in [TELEGRAM_NUMBERS, NO_TELEGRAM_NUMBERS, ERROR_NUMBERS]:
        if os.path.exists(f):
            os.remove(f)
    
    stats['total'] = len(numbers)
    stats['start_time'] = time.time()
    
    results = []
    
    print(f"\n{'='*80}")
    print(f"🚀 GitHub Actions - Telegram Checker")
    print(f"{'='*80}")
    print(f"📊 Batch: {BATCH_START} to {BATCH_START + len(numbers)}")
    print(f"⚡ Workers: {workers}")
    print(f"📱 Numbers: {len(numbers)}\n")
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_number = {
            executor.submit(check_number_web, number, i % workers): number 
            for i, number in enumerate(numbers)
        }
        
        for future in as_completed(future_to_number):
            try:
                result = future.result()
                results.append(result)
                
                if stats['checked'] % 50 == 0:
                    elapsed = time.time() - stats['start_time']
                    speed = stats['checked'] / elapsed if elapsed > 0 else 0
                    print(f"\n[{stats['checked']}/{stats['total']}] Speed: {speed:.1f}/s | "
                          f"🔴 {stats['has_telegram']} | 🟢 {stats['no_telegram']} | ⚠️ {stats['errors']}")
                    
            except Exception as e:
                print(f"❌ Task failed: {str(e)[:50]}")
    
    # Summary
    elapsed = time.time() - stats['start_time']
    
    print(f"\n{'='*80}")
    print(f"✅ COMPLETED!")
    print(f"{'='*80}")
    print(f"⏱️  Time: {elapsed:.2f}s ({elapsed/60:.1f} min)")
    print(f"⚡ Speed: {len(numbers)/elapsed:.2f} numbers/sec")
    print(f"🔴 Telegram: {stats['has_telegram']}")
    print(f"🟢 Available: {stats['no_telegram']}")
    print(f"⚠️  Errors: {stats['errors']}\n")
    
    # Save JSON
    summary = {
        'timestamp': datetime.now().isoformat(),
        'batch_start': BATCH_START,
        'batch_size': BATCH_SIZE,
        'total_checked': len(numbers),
        'time_taken_seconds': elapsed,
        'speed_per_second': len(numbers)/elapsed,
        'has_telegram': stats['has_telegram'],
        'available': stats['no_telegram'],
        'errors': stats['errors'],
        'results': results
    }
    
    with open('web_check_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

def main():
    """Main function for GitHub Actions"""
    
    # Read numbers file
    input_file = 'togo bne - 0403 5.txt'
    
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        print("Available files:")
        for f in os.listdir('.'):
            if f.endswith('.txt'):
                print(f"  - {f}")
        return
    
    # Read all numbers
    with open(input_file, 'r', encoding='utf-8') as f:
        all_numbers = [line.strip() for line in f if line.strip()]
    
    # Add + prefix
    all_numbers = ['+' + num if not num.startswith('+') else num for num in all_numbers]
    
    # Get batch
    end_index = min(BATCH_START + BATCH_SIZE, len(all_numbers))
    numbers = all_numbers[BATCH_START:end_index]
    
    print(f"Total numbers in file: {len(all_numbers)}")
    print(f"Processing batch: {BATCH_START} to {end_index}")
    print(f"Batch size: {len(numbers)}")
    
    if not numbers:
        print("❌ No numbers to check in this batch")
        return
    
    # Run
    check_numbers_parallel(numbers, workers=WORKERS)

if __name__ == "__main__":
    main()
