#!/usr/bin/env python3
"""
Workday Form Scraper with Authentication State
Author: Web Automation Engineer
Date: 2023-11-15
Description: 
Automates login, navigation, and form extraction from Workday portals.
Saves authentication state to avoid repeated logins.
"""

import os
import json
import asyncio
from collections import deque
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables from .env file
load_dotenv()

# Configuration constants
DEFAULT_START_PATH = "/myaccount/home"
AUTH_STATE_FILE = "workday_auth_state.json"
OUTPUT_FILE = "workday_forms.json"

async def login(page):
    """
    Authenticates into Workday using credentials from environment variables.
    Uses Playwright's robust selectors to handle Workday's login form.
    """
    # Navigate to Workday tenant URL
    tenant_url = os.getenv('WORKDAY_TENANT_URL')
    print(f"🌐 Navigating to Workday tenant: {tenant_url}")
    await page.goto(tenant_url)
    
    # Fill credentials and submit - using multiple possible selectors for robustness
    email_selectors = [
        'input[data-automation-id="email"]',
        'input[type="email"]',
        'input[name="username"]'
    ]
    
    password_selectors = [
        'input[data-automation-id="password"]',
        'input[type="password"]',
        'input[name="password"]'
    ]
    
    submit_selectors = [
        'button[data-automation-id="signInSubmitButton"]',
        'button[type="submit"]',
        'button:has-text("Sign In")'
    ]
    
    # Try different selector combinations
    logged_in = False
    for email_sel in email_selectors:
        for password_sel in password_selectors:
            for submit_sel in submit_selectors:
                try:
                    await page.fill(email_sel, os.getenv('WORKDAY_USERNAME'))
                    await page.fill(password_sel, os.getenv('WORKDAY_PASSWORD'))
                    await page.click(submit_sel)
                    
                    # Wait for successful login (detect dashboard element)
                    try:
                        await page.wait_for_selector('.WDSC-Dashboard', timeout=10000)
                        logged_in = True
                        print("🔓 Login successful")
                        break
                    except:
                        continue
                except:
                    continue
            if logged_in:
                break
        if logged_in:
            break
    
    if not logged_in:
        raise Exception("❌ Login failed - check credentials or page structure")
    
    # Handle potential multi-factor authentication prompt
    try:
        mfa_prompt = await page.query_selector('text="Send Me a Push"')
        if mfa_prompt:
            print("⚠️ MFA required - please complete authentication in browser")
            # Wait for MFA completion (extend timeout)
            await page.wait_for_selector('.WDSC-Dashboard', timeout=120000)
    except:
        pass

async def crawl_application_flow(start_path, page):
    """
    Crawls through Workday application pages using BFS algorithm.
    Returns list of all discovered form elements.
    """
    visited = set()
    queue = deque([start_path])
    all_form_elements = []
    base_url = os.getenv('WORKDAY_TENANT_URL')
    
    # Counter for progress tracking
    page_count = 0
    
    while queue:
        current_path = queue.popleft()
        if current_path in visited:
            continue
            
        full_url = f"{base_url}{current_path}"
        print(f"📄 Page {page_count+1}: Navigating to {full_url}")
        
        try:
            await page.goto(full_url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Extract form elements from current page
            page_elements = await extract_form_elements(page)
            all_form_elements.extend(page_elements)
            print(f"  ✓ Found {len(page_elements)} form elements")
            
            # Find new links to crawl
            new_links = await discover_application_links(page)
            for link in new_links:
                if link not in visited:
                    queue.append(link)
            
            visited.add(current_path)
            page_count += 1
            
        except Exception as e:
            print(f"  ⚠️ Error processing {current_path}: {str(e)}")
    
    return all_form_elements

async def discover_application_links(page):
    """
    Finds all relevant application links in current page.
    Filters out non-application and external links.
    """
    application_links = []
    
    # Get all links on page
    all_links = await page.query_selector_all('a[href]')
    
    for link in all_links:
        try:
            href = await link.get_attribute('href')
            if href and href.startswith('/') and not href.startswith('//'):
                # Normalize URL path
                path = href.split('?')[0]  # Remove query parameters
                
                # Filter for application-specific paths
                if any(segment in path for segment in [
                    '/myaccount/', 
                    '/application/', 
                    '/careers/',
                    '/job/',
                    '/review/',
                    '/eeo/'
                ]):
                    if path not in application_links:
                        application_links.append(path)
        except:
            continue
    
    print(f"  🔗 Found {len(application_links)} application links on this page")
    return application_links

async def extract_form_elements(page):
    """
    Extracts and classifies form elements from current page.
    Returns structured data for each form control.
    """
    form_elements = []
    
    # Find all form containers - Workday-specific class
    form_containers = await page.query_selector_all('.WDSC-FormField')
    
    # Alternative selectors if primary not found
    if not form_containers:
        form_containers = await page.query_selector_all('div[data-automation-id="formField"]')
    
    print(f"  🔍 Scanning {len(form_containers)} form containers")
    
    for container in form_containers:
        try:
            # Skip hidden/invisible elements
            if not await container.is_visible():
                continue
                
            # Determine control type
            control_type = await identify_control_type(container)
            
            # Skip unsupported types
            if not control_type:
                continue
                
            # Extract common properties
            element_data = {
                "label": await extract_label(container),
                "id_of_input_component": await extract_identifier(container, control_type),
                "required": await is_required(container),
                "type_of_input": control_type,
                "options": [],
                "user_data_select_values": []
            }
            
            # Handle options-based elements
            if control_type in ("select", "multiselect", "radio", "checkbox"):
                element_data["options"] = await extract_options(container, control_type)
                element_data["user_data_select_values"] = generate_sample_values(
                    control_type, 
                    element_data["options"]
                )
            
            # Special handling for date fields
            elif control_type == "date":
                element_data["options"] = ["MM", "DD", "YYYY"]
                element_data["user_data_select_values"] = ["01", "15", "2023"]
            
            # Special handling for file uploads
            elif control_type == "file":
                element_data["user_data_select_values"] = ["resume.pdf"]
            
            form_elements.append(element_data)
            
        except Exception as e:
            # Skip elements that cause errors but continue processing others
            # print(f"  ⚠️ Element extraction error: {str(e)}")
            pass
    
    return form_elements

async def identify_control_type(element):
    """
    Determines the type of form control using Workday-specific attributes.
    Handles various UI patterns found in Workday applications.
    """
    # Check for text inputs
    if await element.query_selector('input[type="text"]'):
        return "text"
    
    # Check for textareas
    if await element.query_selector('textarea'):
        return "textarea"
    
    # Check for file inputs
    if await element.query_selector('input[type="file"]'):
        return "file"
    
    # Check for dropdowns/comboboxes
    combobox = await element.query_selector('div[role="combobox"]')
    if combobox:
        # Determine if multiselect or single select
        if await combobox.get_attribute('aria-multiselectable') == "true":
            return "multiselect"
        
        # Check for type-ahead functionality
        input_inside = await combobox.query_selector('input[type="text"]')
        if input_inside:
            return "typeahead"
        return "select"
    
    # Check for radio groups
    if await element.query_selector('div[data-automation-id="radioButtonGroup"]'):
        return "radio"
    
    # Check for checkboxes
    if await element.query_selector('div[data-automation-id="checkboxGroup"]'):
        return "checkbox"
    
    # Check for date pickers
    if await element.query_selector('div[data-automation-id="dateWidget"]'):
        return "date"
    
    # Check for date fields by label
    label = await extract_label(element)
    if label and any(term in label.lower() for term in ["date", "dob", "birth"]):
        return "date"
    
    # Fallback to input type detection
    input_elem = await element.query_selector('input')
    if input_elem:
        input_type = await input_elem.get_attribute('type')
        if input_type in ["text", "email", "tel", "number"]:
            return "text"
        if input_type == "file":
            return "file"
    
    return None

async def extract_label(element):
    """
    Extracts the human-readable label for a form element.
    Handles various label patterns in Workday.
    """
    # Try multiple selector strategies
    label_selectors = [
        '[data-automation-id="label"]',
        'label',
        '.WDSC-Label',
        '.gwt-Label',
        '.css-1w6j2w'
    ]
    
    for selector in label_selectors:
        label_element = await element.query_selector(selector)
        if label_element:
            label_text = (await label_element.inner_text()).strip()
            # Clean up label text
            label_text = label_text.replace('*', '').replace(':', '').strip()
            if label_text:
                return label_text
    
    # Fallback to aria-label
    aria_label = await element.get_attribute('aria-label')
    if aria_label:
        return aria_label.strip()
    
    return "Unlabeled Field"

async def extract_identifier(element, control_type):
    """
    Gets unique identifier in priority order:
    1. data-automation-id
    2. id attribute
    3. name attribute
    4. Generates a unique ID based on label and type
    """
    # Try to get automation ID first
    automation_id = await element.get_attribute('data-automation-id')
    if automation_id:
        return automation_id
    
    # Try different selectors based on control type
    if control_type in ("text", "textarea", "file", "typeahead"):
        input_element = await element.query_selector('input, textarea')
        if input_element:
            element_id = await input_element.get_attribute('id')
            if element_id:
                return element_id
            
            name_attr = await input_element.get_attribute('name')
            if name_attr:
                return name_attr
    
    # For radio groups and checkboxes
    if control_type in ("radio", "checkbox"):
        first_option = await element.query_selector('input[type="radio"], input[type="checkbox"]')
        if first_option:
            return await first_option.get_attribute('name') or ""
    
    # Fallback: Generate ID from label
    label = await extract_label(element)
    if label:
        # Create slug from label
        slug = ''.join(c if c.isalnum() else '_' for c in label)
        return f"generated_{slug[:30]}"
    
    return "no_identifier_found"

async def is_required(element):
    """
    Checks if a form element is marked as required.
    Uses multiple indicators to determine requirement status.
    """
    # Check for explicit ARIA attribute
    if await element.query_selector('[aria-required="true"]'):
        return True
    
    # Check for required class
    if await element.query_selector('.WDSC-Required'):
        return True
    
    # Check for asterisk in label
    label_element = await element.query_selector('[data-automation-id="label"]')
    if label_element:
        label_text = await label_element.inner_text()
        if '*' in label_text:
            return True
    
    # Check for required text
    required_text = await element.query_selector('text="required"')
    if required_text:
        return True
    
    return False

async def extract_options(element, control_type):
    """
    Extracts available options for multi-choice controls.
    Handles lazy-loaded dropdowns and dynamic content.
    """
    options = []
    
    if control_type in ("select", "multiselect", "typeahead"):
        # Handle dropdown options
        try:
            # Click to open dropdown
            await element.click()
            await asyncio.sleep(0.5)  # Allow options to render
            
            # Get all visible options
            option_elements = await element.query_selector_all('div[role="option"]')
            
            for opt in option_elements:
                # Skip invisible options
                if not await opt.is_visible():
                    continue
                    
                option_text = (await opt.inner_text()).strip()
                if option_text:
                    options.append(option_text)
            
            # Close dropdown
            await element.press("Escape")
        except Exception as e:
            print(f"    ⚠️ Couldn't extract options: {str(e)}")
        
    elif control_type == "radio":
        # Extract radio options
        option_elements = await element.query_selector_all('[data-automation-id="radioLabel"]')
        options = [await opt.inner_text() for opt in option_elements]
        
    elif control_type == "checkbox":
        # Extract checkbox options
        option_elements = await element.query_selector_all('[data-automation-id="checkboxLabel"]')
        options = [await opt.inner_text() for opt in option_elements]
    
    # Filter empty options and return unique values
    return list(set(opt for opt in options if opt))

def generate_sample_values(control_type, options):
    """
    Generates sample values based on control type and available options.
    Uses intelligent selection for realistic data.
    """
    if not options:
        return []
    
    # Handle different control types
    if control_type in ("select", "radio", "typeahead"):
        # Prefer "No" for visa questions, "Yes" for authorization
        for opt in options:
            opt_lower = opt.lower()
            if "no" in opt_lower or "not" in opt_lower or "don't" in opt_lower:
                return [opt]
        return [options[0]]  # First option as fallback
    
    if control_type in ("multiselect", "checkbox"):
        # Select a single option for multiselects
        return [options[0]] if options else []
    
    return []

async def main():
    """
    Main execution flow:
    1. Setup browser with authentication state
    2. Login to Workday (if needed)
    3. Crawl application pages
    4. Extract form data
    5. Save results
    """
    print("🚀 Starting Workday Form Scraper")
    print("--------------------------------")
    
    async with async_playwright() as p:
        # Launch browser (headless=False for debugging)
        browser = await p.chromium.launch(headless=False)
        context = None
        
        # Check if we have saved authentication state
        if os.path.exists(AUTH_STATE_FILE):
            print("🔑 Loading authentication state from file")
            try:
                context = await browser.new_context(storage_state=AUTH_STATE_FILE)
                print("   ✓ Authentication state loaded")
            except Exception as e:
                print(f"   ⚠️ Error loading auth state: {str(e)}")
                print("   ⚠️ Proceeding with new session")
                context = await browser.new_context()
        else:
            context = await browser.new_context()
        
        page = await context.new_page()
        page.set_default_timeout(60000)  # 60-second timeout
        
        try:
            # Check if we're already logged in
            await page.goto(os.getenv('WORKDAY_TENANT_URL') + DEFAULT_START_PATH)
            
            # Detect if we need to login
            if await page.query_selector('input[data-automation-id="email"]'):
                print("🔐 Authentication required")
                await login(page)
                # Save authentication state for future runs
                await context.storage_state(path=AUTH_STATE_FILE)
                print(f"💾 Saved authentication state to {AUTH_STATE_FILE}")
            
            # Start crawling from home dashboard
            print("\n🔍 Starting application crawl")
            form_data = await crawl_application_flow(DEFAULT_START_PATH, page)
            
            # Save results
            with open(OUTPUT_FILE, 'w') as f:
                json.dump(form_data, f, indent=2)
                
            print(f"\n✅ Success! Extracted {len(form_data)} form elements")
            print(f"📁 Output saved to {OUTPUT_FILE}")
            
            # Print summary of findings
            control_counts = {}
            for item in form_data:
                ctype = item["type_of_input"]
                control_counts[ctype] = control_counts.get(ctype, 0) + 1
            
            print("\n📊 Extracted Control Types:")
            for ctype, count in control_counts.items():
                print(f"  {ctype.capitalize().ljust(12)}: {count}")
            
        except Exception as e:
            print(f"\n❌ Critical error: {str(e)}")
            # Save partial results if possible
            if 'form_data' in locals():
                with open('partial_' + OUTPUT_FILE, 'w') as f:
                    json.dump(form_data, f, indent=2)
                print("💾 Saved partial results to partial_workday_forms.json")
        finally:
            # Clean up
            await browser.close()
            print("\n🛑 Browser closed")

if __name__ == "__main__":
    asyncio.run(main())